"""Marketing content endpoints — all return hardcoded data.

GET /customer-stories          — List stories
GET /customer-stories/:slug    — Single story
GET /careers/jobs              — List jobs
GET /careers/jobs/:id          — Single job
GET /press/releases            — Press releases
GET /press/releases/:slug      — Single release
GET /press/kit                 — Press kit
GET /partners                  — List partners
GET /partners/:id              — Single partner
"""
from __future__ import annotations


from fastapi import APIRouter, HTTPException

router = APIRouter(tags=["marketing"])


_HARDCODED_STORIES = [
    {"id": "cs-1", "title": "TransLogistica Cuts Costs by 30%", "slug": "translogistica-cost-reduction", "excerpt": "How a Romanian fleet operator transformed their operations.", "content": "<p>Full case study content here.</p>", "company_name": "TransLogistica SRL", "industry": "Transportation", "company_size": "50-200", "featured": True, "published_at": "2026-06-15"},
]

_HARDCODED_JOBS = [
    {"id": "job-1", "title": "Senior Full Stack Developer", "department": "Engineering", "location": "Bucharest / Remote", "type": "full-time", "description": "Build the next generation of logistics software.", "requirements": ["5+ years experience", "TypeScript, React, Python", "Experience with logistics systems is a plus"], "posted_at": "2026-07-01"},
]

_HARDCODED_PRESS_RELEASES = [
    {"id": "pr-1", "title": "Operion Launches AI Co-Pilot for Logistics", "slug": "operion-launches-ai-copilot", "excerpt": "New AI-powered assistant transforms logistics operations.", "content": "<p>Full press release here.</p>", "published_at": "2026-06-01", "category": "product"},
]

_HARDCODED_PRESS_KIT = {
    "logos": [{"name": "Operion Logo SVG", "url": "#", "type": "svg"}, {"name": "Operion Logo PNG", "url": "#", "type": "png"}],
    "brand_colors": [{"name": "Primary Blue", "hex": "#2563EB"}, {"name": "Dark", "hex": "#0F172A"}],
    "downloads": [{"name": "Brand Assets ZIP", "url": "#"}],
}

_HARDCODED_PARTNERS = [
    {"id": "partner-1", "name": "TransEu", "logo_url": "#", "type": "technology", "description": "European transport network integration partner.", "website_url": "https://transeu.example.com", "featured": True},
    {"id": "partner-2", "name": "MapFlow", "logo_url": "#", "type": "technology", "description": "Advanced mapping and route optimization.", "website_url": "https://mapflow.example.com", "featured": False},
]


@router.get("/customer-stories")
def list_stories():
    return _HARDCODED_STORIES

@router.get("/customer-stories/{slug}")
def get_story(slug: str):
    for s in _HARDCODED_STORIES:
        if s["slug"] == slug:
            return s
    raise HTTPException(404, "Story not found")

@router.get("/careers/jobs")
def list_jobs():
    return _HARDCODED_JOBS

@router.get("/careers/jobs/{job_id}")
def get_job(job_id: str):
    for j in _HARDCODED_JOBS:
        if j["id"] == job_id:
            return j
    raise HTTPException(404, "Job not found")

@router.get("/press/releases")
def list_press():
    return _HARDCODED_PRESS_RELEASES

@router.get("/press/releases/{slug}")
def get_press_release(slug: str):
    for p in _HARDCODED_PRESS_RELEASES:
        if p["slug"] == slug:
            return p
    raise HTTPException(404, "Press release not found")

@router.get("/press/kit")
def get_press_kit():
    return _HARDCODED_PRESS_KIT

@router.get("/partners")
def list_partners():
    return _HARDCODED_PARTNERS

@router.get("/partners/{partner_id}")
def get_partner(partner_id: str):
    for p in _HARDCODED_PARTNERS:
        if p["id"] == partner_id:
            return p
    raise HTTPException(404, "Partner not found")
