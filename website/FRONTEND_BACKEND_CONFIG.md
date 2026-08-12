# Operion Frontend & Backend Configuration

## Ports & URLs — DO NOT GUESS

| Component | URL / Port | How to run |
|-----------|-----------|------------|
| **Backend API** | `https://api.operionerp.xyz` | Deployed separately (see Calculator logistica repo) |
| **Frontend (production-like)** | `http://localhost:8080` | `node serve.js` from `operion-website/` |
| **Frontend (Vite dev server)** | `http://localhost:5173` | `npm run dev` from `operion-website/` |
| **Backend (local dev)** | `http://127.0.0.1:8000` | `python main.py` from `Calculator logistica/` |

## The ONE rule

**The website's `VITE_API_URL` always points to `https://api.operionerp.xyz`.**  
Never set it to `http://127.0.0.1:8000` or `http://localhost:8000`.  
The backend API server is **not** the frontend's dev-server buddy — it's a separate deployed service.

The desktop app (`Calculator logistica/client/`) uses `OPERION_API_URL` from its own `.env` to talk to the same backend. The website uses `VITE_API_URL`. They're independent variables for independent UIs sharing the same backend.

## CORS

The backend allows these origins (configured in `backend/main.py`):

**Development** (when `OPERION_ENV=development`):
- `http://localhost:8080` — serve.js
- `http://127.0.0.1:8080`
- `http://localhost:5173` — Vite dev server
- `http://127.0.0.1:5173`
- `http://localhost:8000` — local backend docs/playground
- `http://127.0.0.1:8000`

**Production** (when `OPERION_ENV=production`):
- `https://operionerp.xyz`
- `https://app.operionerp.xyz`
- `https://api.operionerp.xyz`

## JWT Secret

The frontend verifies JWT signatures locally using `VITE_JWT_SECRET`.  
The backend signs JWTs using `OPERION_JWT_SECRET_KEY`.

**These must match.** The default fallback in the frontend code is `"change-me-to-a-random-secret-key"` — that's a placeholder and will NOT match production.

To fix: set `VITE_JWT_SECRET` in `operion-website/.env` to the same value as the backend's `OPERION_JWT_SECRET_KEY`.

## Login flow

```
Browser                    Backend (api.operionerp.xyz)
  │                              │
  │  POST /api/v1/auth/token     │
  │  (username + password form)  │
  │─────────────────────────────>│
  │                              │
  │  ── Admin check ──           │
  │  email matches admin_email?  │
  │  bcrypt.verify(password,     │
  │    admin_password_hash)      │
  │                              │
  │  access_token + refresh_tok  │
  │<─────────────────────────────│
  │                              │
  │  verifyJwt(access_token)     │
  │  decode claims → set user    │
```

The desktop app (`client/auth.py`) and the website (`src/api/endpoints.ts`) use the **same** endpoint with the **same** form-encoded body. No difference.

## If login still fails

1. Check that the backend at `api.operionerp.xyz` has `OPERION_ADMIN_EMAIL` and `OPERION_ADMIN_PASSWORD_HASH` set in its environment.
2. Check that `VITE_JWT_SECRET` matches the backend's `OPERION_JWT_SECRET_KEY`.
3. Check that you're typing the **plaintext password** (not the hash from admin.env).
