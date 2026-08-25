"""Blog endpoints.

Public (no auth):
  GET    /api/v1/blog/posts          — Paginated, filterable blog posts
  GET    /api/v1/blog/posts/:slug    — Single post by slug
  GET    /api/v1/blog/categories     — All categories
  GET    /api/v1/blog/authors/:id    — Single author

Admin (require_admin):
  POST   /api/v1/blog/admin/posts          — Create post
  PATCH  /api/v1/blog/admin/posts/:slug    — Update post
  DELETE /api/v1/blog/admin/posts/:slug    — Delete post
"""
from __future__ import annotations


import json
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.dependencies import get_db
from backend.dependencies_security import require_admin
from backend.errors import ErrorCode
from backend.db import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blog", tags=["blog"])
admin_router = APIRouter(prefix="/blog/admin", tags=["blog-admin"])


# ── Helpers ─────────────────────────────────────────────────────────


def _slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    slug = re.sub(r'[^\w\s-]', '', text.lower().strip())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


def _compute_reading_time(content: str) -> int:
    """Estimate reading time in minutes (200 words/min)."""
    text = re.sub(r'<[^>]+>', '', content)  # strip HTML
    words = len(text.split())
    return max(1, round(words / 200))


def _unique_slug(db: DatabaseManager, base_slug: str, exclude_id: Optional[int] = None) -> str:
    """Ensure slug uniqueness by appending -2, -3, etc."""
    slug = base_slug
    counter = 1
    while True:
        query = "SELECT id FROM blog_posts WHERE slug = ?"
        params: List[Any] = [slug]
        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)
        existing = db.execute(query, tuple(params)).fetchone()
        if not existing:
            return slug
        counter += 1
        slug = f"{base_slug}-{counter}"


def _post_to_dict(row: dict) -> dict:
    """Convert a blog_posts DB row to a flat API response dict with denormalized fields."""
    result = dict(row)

    # Parse tags JSON array
    if isinstance(result.get("tags"), str):
        try:
            result["tags"] = json.loads(result["tags"])
        except (json.JSONDecodeError, TypeError):
            result["tags"] = []

    # Convert integer booleans
    result["published"] = bool(result.get("published", 0))

    return result


def _enrich_post(db: DatabaseManager, post: dict) -> dict:
    """JOIN author name/avatar and category name into a flat post dict."""
    # Fetch author
    author_id = post.get("author_id")
    if author_id:
        author = db.execute(
            "SELECT name, avatar_url FROM blog_authors WHERE id = ?", (author_id,)
        ).fetchone()
        if author:
            post["author_name"] = author["name"]
            post["author_avatar"] = author["avatar_url"]

    # Fetch category name
    cat_id = post.get("category_id")
    if cat_id:
        cat = db.execute(
            "SELECT name FROM blog_categories WHERE id = ?", (cat_id,)
        ).fetchone()
        if cat:
            post["category"] = cat["name"]

    return post


# ═══════════════════════════════════════════════════════════════════
# Public endpoints
# ═══════════════════════════════════════════════════════════════════


@router.get("/posts")
def list_posts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    category: Optional[str] = Query(None, description="Category slug"),
    tag: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: DatabaseManager = Depends(get_db),
):
    """Return paginated blog posts with optional filters."""
    conditions = ["p.published = 1"]
    params: list = []

    if category:
        conditions.append("c.slug = ?")
        params.append(category)

    if tag:
        conditions.append("p.tags LIKE ?")
        params.append(f'%"{tag}"%')

    if search:
        conditions.append("(p.title LIKE ? OR p.excerpt LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = " AND ".join(conditions)

    # Count total
    count_row = db.execute(
        f"SELECT COUNT(*) FROM blog_posts p "
        f"LEFT JOIN blog_categories c ON c.id = p.category_id "
        f"WHERE {where}",
        tuple(params),
    ).fetchone()
    total = count_row[0] if count_row else 0

    # Fetch page
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT p.id, p.title, p.slug, p.excerpt, p.featured_image, "
        f"p.reading_time_minutes, p.published_at, p.tags, "
        f"p.category_id, p.author_id, p.seo_title, p.seo_description "
        f"FROM blog_posts p "
        f"LEFT JOIN blog_categories c ON c.id = p.category_id "
        f"WHERE {where} "
        f"ORDER BY p.published_at DESC LIMIT ? OFFSET ?",
        tuple(params) + (page_size, offset),
    ).fetchall()

    items = []
    for row in rows:
        post = _post_to_dict(dict(row))
        post = _enrich_post(db, post)
        items.append(post)

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/posts/{slug}")
def get_post(
    slug: str,
    db: DatabaseManager = Depends(get_db),
):
    """Return a single published blog post by slug."""
    row = db.execute(
        "SELECT id, title, slug, excerpt, content, featured_image, "
        "reading_time_minutes, published_at, tags, "
        "category_id, author_id, seo_title, seo_description, created_at, updated_at "
        "FROM blog_posts WHERE slug = ? AND published = 1",
        (slug,),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Post not found.",
            },
        )

    post = _post_to_dict(dict(row))
    post = _enrich_post(db, post)
    return post


@router.get("/categories")
def list_categories(
    db: DatabaseManager = Depends(get_db),
):
    """Return all blog categories with post counts."""
    rows = db.execute(
        "SELECT c.id, c.name, c.slug, c.description, "
        "COUNT(p.id) as post_count "
        "FROM blog_categories c "
        "LEFT JOIN blog_posts p ON p.category_id = c.id AND p.published = 1 "
        "GROUP BY c.id "
        "ORDER BY c.name",
    ).fetchall()

    return [dict(r) for r in rows]


@router.get("/authors/{author_id}")
def get_author(
    author_id: int,
    db: DatabaseManager = Depends(get_db),
):
    """Return a single blog author."""
    row = db.execute(
        "SELECT id, name, avatar_url, bio, role, created_at "
        "FROM blog_authors WHERE id = ?",
        (author_id,),
    ).fetchone()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Author not found.",
            },
        )

    return dict(row)


# ═══════════════════════════════════════════════════════════════════
# Admin endpoints (require_admin)
# ═══════════════════════════════════════════════════════════════════


@admin_router.post("/posts", status_code=201)
def create_post(
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
):
    """Create a new blog post."""
    title = data.get("title", "").strip()
    if not title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": ErrorCode.VALIDATION_ERROR.value,
                "detail": "title is required.",
            },
        )

    excerpt = data.get("excerpt", "")
    content = data.get("content", "")
    slug = data.get("slug") or _slugify(title)
    slug = _unique_slug(db, slug)

    tags = data.get("tags", [])
    if isinstance(tags, list):
        tags = json.dumps(tags)

    featured_image = data.get("featured_image")
    category_id = data.get("category_id")
    author_id = data.get("author_id")
    seo_title = data.get("seo_title")

    # If no seo_description provided, auto-generate from excerpt
    seo_description = data.get("seo_description") or excerpt[:160]

    reading_time = data.get("reading_time_minutes") or _compute_reading_time(content)

    published = 1 if data.get("published", False) else 0
    published_at = data.get("published_at") if published else None

    cursor = db.execute(
        "INSERT INTO blog_posts (title, slug, excerpt, content, category_id, author_id, "
        "tags, featured_image, reading_time_minutes, seo_title, seo_description, "
        "published, published_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (title, slug, excerpt, content, category_id, author_id,
         tags, featured_image, reading_time, seo_title, seo_description,
         published, published_at),
    )
    db.commit()

    # Return created post
    row = db.execute(
        "SELECT * FROM blog_posts WHERE id = ?",
        (cursor.lastrowid,),
    ).fetchone()

    post = _post_to_dict(dict(row))
    post = _enrich_post(db, post)
    return post


@admin_router.patch("/posts/{slug}")
def update_post(
    slug: str,
    data: Dict[str, Any],
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
):
    """Partially update a blog post."""
    # Verify post exists
    existing = db.execute(
        "SELECT id FROM blog_posts WHERE slug = ?", (slug,)
    ).fetchone()

    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Post not found.",
            },
        )

    post_id = existing["id"]
    update_fields: Dict[str, Any] = {}

    if "title" in data:
        update_fields["title"] = data["title"]
    if "excerpt" in data:
        update_fields["excerpt"] = data["excerpt"]
    if "content" in data:
        update_fields["content"] = data["content"]
        update_fields["reading_time_minutes"] = _compute_reading_time(data["content"])

    if "slug" in data and data["slug"] and data["slug"] != slug:
        new_slug = _unique_slug(db, data["slug"], exclude_id=post_id)
        update_fields["slug"] = new_slug

    if "category_id" in data:
        update_fields["category_id"] = data["category_id"]
    if "author_id" in data:
        update_fields["author_id"] = data["author_id"]
    if "tags" in data:
        tags = data["tags"]
        update_fields["tags"] = json.dumps(tags) if isinstance(tags, list) else tags
    if "featured_image" in data:
        update_fields["featured_image"] = data["featured_image"]
    if "seo_title" in data:
        update_fields["seo_title"] = data["seo_title"]
    if "seo_description" in data:
        update_fields["seo_description"] = data["seo_description"]

    if "published" in data:
        published = 1 if data["published"] else 0
        update_fields["published"] = published
        update_fields["published_at"] = data.get("published_at") if published else None

    if not update_fields:
        # Return existing post
        row = db.execute("SELECT * FROM blog_posts WHERE id = ?", (post_id,)).fetchone()
        post = _post_to_dict(dict(row))
        post = _enrich_post(db, post)
        return post

    set_clause = ", ".join(f"{k} = ?" for k in update_fields)
    values = tuple(update_fields.values()) + (post_id,)
    db.execute(
        f"UPDATE blog_posts SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    db.commit()

    # Return updated post
    row = db.execute("SELECT * FROM blog_posts WHERE id = ?", (post_id,)).fetchone()
    post = _post_to_dict(dict(row))
    post = _enrich_post(db, post)
    return post


@admin_router.delete("/posts/{slug}", status_code=204)
def delete_post(
    slug: str,
    current_user: Dict[str, Any] = Depends(require_admin),
    db: DatabaseManager = Depends(get_db),
):
    """Delete a blog post."""
    cursor = db.execute("DELETE FROM blog_posts WHERE slug = ?", (slug,))
    db.commit()

    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error_code": ErrorCode.NOT_FOUND.value,
                "detail": "Post not found.",
            },
        )

    return None  # 204 No Content
