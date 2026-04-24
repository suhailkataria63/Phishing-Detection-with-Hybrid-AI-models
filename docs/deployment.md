# Deployment Guide

## 1) Deployment Architecture
- Frontend: **Vercel** (Next.js app at `app/frontend`)
- Backend: **Render** (FastAPI app at `app/backend/app/main.py`)
- Models: loaded from local repo path `models/` at runtime

## 2) Backend Deployment (Render)
Create a **Web Service** from this repo.

- Runtime: `Python`
- Build command:
```bash
pip install -r requirements.txt
```
- Start command:
```bash
uvicorn app.backend.app.main:app --host 0.0.0.0 --port $PORT
```
- Health check path:
```text
/health
```

Render config is included in [`render.yaml`](../render.yaml).

### Required Render Environment Variables
- `CORS_ORIGINS`
  - Example: `http://localhost:3000,https://your-frontend.vercel.app`
- `FRONTEND_ORIGIN` (optional helper if you prefer single origin)
  - Example: `https://your-frontend.vercel.app`

### Backend Entrypoint Confirmation
FastAPI app object is defined in:
- `app/backend/app/main.py` as `app`

So the correct start target is:
- `app.backend.app.main:app`

## 3) Frontend Deployment (Vercel)
Create Vercel project from same repo.

- Root Directory: `app/frontend`
- Framework preset: Next.js
- Build command: default (`next build`)
- Install command: default (`npm install`)

### Required Vercel Environment Variable
- `NEXT_PUBLIC_API_BASE`
  - Example: `https://your-render-service.onrender.com`

Frontend already reads `NEXT_PUBLIC_API_BASE` with local fallback to `http://localhost:8000`.

## 4) CORS Setup
Backend supports flexible origin config via settings:
- `CORS_ORIGINS` (comma-separated)
- `FRONTEND_ORIGIN` (single)
- legacy `CORS_ALLOW_ORIGINS` still supported

Recommended:
```text
CORS_ORIGINS=http://localhost:3000,https://your-frontend.vercel.app
```

## 5) Model Artifact Warning (Important)
GitHub rejects files >100MB.

Check model artifact sizes locally:
```bash
find models -type f -exec ls -lh {} \; | sort -k5 -h
```

Current notable file:
- `models/email/email_transformer_model.pt` (~254MB)

Recommendations:
- Keep oversized experimental files out of git history.
- Use Git LFS or external artifact storage for large checkpoints.
- Keep only required runtime artifacts in repo for deployment.

## 6) Local Development Commands
Backend:
```bash
cd /path/to/phish-detector
uvicorn app.backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:
```bash
cd /path/to/phish-detector/app/frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Health check:
```bash
curl http://localhost:8000/health
```

## 7) Post-Deployment Smoke Tests
1. Open backend health endpoint:
- `https://<render-service>.onrender.com/health`

2. Test URL detection:
- Frontend URL mode should return verdict + reasons

3. Test Email detection:
- Email mode should return risk score + recommendation

4. Test Joint detection:
- Joint mode should return final score, per-URL data, and optimization metadata

5. Test Batch mode (if enabled in UI):
- Upload CSV and confirm result table + export behavior

## 8) Notes on Model Availability
`/health` now reports:
- `url_model_loaded`
- `email_model_ready`
- model path existence diagnostics

If artifacts are missing in deployment, API still boots and `/health` shows missing-path details for troubleshooting.
