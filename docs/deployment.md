# Deployment Guide

## 1) Deployment Architecture
- Frontend: **Vercel** (Next.js app at `app/frontend`)
- Backend: **Render** (FastAPI app at `app/backend/app/main.py`)
- Models: loaded from local repo path `models/` at runtime

## 2) Backend Deployment (Render)
Create a **Web Service** from this repo.

- Runtime: `Python`
- Python version: `3.11.9` (via root `runtime.txt`)
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

### Dependency Stability Note
`requirements.txt` is intentionally version-pinned for ML artifact compatibility.
Using very new major versions of NumPy/Pandas/scikit-learn/Transformers/Torch can break
serialized model artifacts or runtime loading behavior.

Current pinned runtime-critical stack:
- `numpy==2.4.4`
- `scikit-learn==1.8.0`
- `joblib==1.5.3`
- `pandas==3.0.2`

These are aligned with the URL artifact pickle metadata to avoid
`BitGenerator` and sklearn unpickle version mismatch errors.

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
- `url_v1_loaded`
- `url_v2_loaded`
- `email_model_ready`
- model path existence diagnostics
- model load errors (if artifacts are missing or incompatible)

If artifacts are missing in deployment, API still boots and `/health` shows missing-path details for troubleshooting.

## 9) Hugging Face Spaces Backend Deployment
Use Hugging Face Spaces when you want to host full backend inference in a Docker runtime.

### Create Space
1. Create a new Space in Hugging Face.
2. Select **SDK: Docker**.
3. Connect this repository (or push this repo contents to the Space repo).

### Docker Runtime
This repo includes:
- `Dockerfile` (root)
- `requirements-hf.txt` (HF-specific dependency set)

Container entrypoint:
```bash
uvicorn app.backend.app.main:app --host 0.0.0.0 --port 7860
```

Port:
- Exposed and served on `7860`

### Required Space Environment Variables
- `PORT=7860`
- `DEPLOYMENT_MODE=full`
- `CORS_ORIGINS=http://localhost:3000,https://<your-vercel-domain>`
- `DEPLOYMENT_ALLOW_ALL_CORS=true` (recommended only for initial testing)

Optional:
- `FRONTEND_ORIGIN=https://<your-vercel-domain>`

### Health URL
After deploy, check:
```text
https://<your-space-subdomain>.hf.space/health
```

### Frontend (Vercel) API Base
Set in Vercel:
```text
NEXT_PUBLIC_API_BASE=https://<your-space-subdomain>.hf.space
```

### Important Compatibility Note
`requirements-hf.txt` is aligned to URL artifact serialization versions:
- `scikit-learn==1.8.0`
- `joblib==1.5.3`
- `numpy==2.4.4`

This avoids runtime crashes such as:
- `AttributeError: 'LogisticRegression' object has no attribute 'multi_class'`

CPU torch is pinned via:
- `torch==2.2.2+cpu`
- `--extra-index-url https://download.pytorch.org/whl/cpu`

If the email transformer stack has incompatibilities with `numpy==2.x` on a given build image, backend startup still continues and `/health` exposes exact email model load errors while URL detection remains available.
URL prediction runtime errors are also surfaced in `/health` under:
- `url_last_predict_error`
- `url_last_v1_predict_error`
- `url_last_v2_predict_error`

### Quick Local Smoke Check
```bash
python scripts/smoke_load_models.py
```

This validates:
- backend import
- URL model load status
- email model load status
- `/health` diagnostics snapshot
