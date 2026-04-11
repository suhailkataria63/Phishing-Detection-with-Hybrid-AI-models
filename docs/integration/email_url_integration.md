# Email + URL Integration Note

## 1. Architecture Chosen
- Existing app architecture is **Next.js frontend + FastAPI backend**.
- The least-disruptive integration was to **extend the existing FastAPI service** (instead of adding a second microservice).
- URL-only flow remains on legacy endpoint `/predict` for backward compatibility.
- New explicit endpoints were added under `/detect/*`.

## 2. How Email Inference Is Wired
- Backend module: `app/backend/app/ml/email_model.py`.
- Uses packaged TG-6.0 artifacts:
  - `models/email/email_final_model.pt`
  - `models/email/email_final_tokenizer/`
  - `models/email/email_final_metadata.json`
- Inference path:
  1. Build text as `subject + " [SEP] " + body`
  2. Tokenize with packaged tokenizer
  3. Run frozen DistilBERT encoder + trained classifier head
  4. Return score/label plus threshold interpretation and action guidance

## 3. Joint Scoring Logic
- Utilities:
  - `app/backend/app/utils/joint_scoring.py`
  - `app/backend/app/utils/joint_optimization.py`
- Input signals:
  - `email_score` from email model
  - `url_score` as max risk across analyzed URLs
- Base formula:
  - `final_score = 0.6 * email_score + 0.4 * max_url_score`
- Escalation guardrails:
  - If any URL score >= 0.9, final score is escalated (cannot be suppressed by low email score)
  - If no URLs are present and email score >= 0.9, final score is escalated
  - If both channels are high, final score escalates further
  - If multiple risky URLs exist, additional escalation is applied
- Output includes:
  - `final_score`, `final_label`, `risk_level`
  - channel scores
  - URL counts and explanation reasons

## 4. Endpoints
- Legacy (unchanged):
  - `POST /predict` (URL-only)
- New:
  - `POST /detect/url`
  - `POST /detect/email`
  - `POST /detect/joint`
- Compatibility aliases:
  - `POST /predict/email`
  - `POST /predict/joint`

## 5. Frontend Integration
- Single coherent mode selector in `app/frontend/app/page.tsx`:
  - URL Detection
  - Email Detection
  - Joint Detection
- Joint mode auto-extracts URLs from body and merges with manually provided URLs.
- If no URLs are found, joint mode still runs with email-only evidence and states this clearly.

## 6. How To Run

### Backend (FastAPI)
- Start backend from repo root (example):
  - `uvicorn backend.app.main:app --reload --port 8000`
  - Compatibility path `backend/` is symlinked to `app/backend/`.

### Frontend (Next.js)
- `cd app/frontend` (or `cd frontend` via compatibility symlink)
- `npm run dev`
- Open `http://localhost:3000`

## 7. Environment Variables
- Frontend:
  - `NEXT_PUBLIC_API_BASE` (default expected: `http://localhost:8000`)
- Backend:
  - `CORS_ALLOW_ORIGINS` (comma-separated; default includes localhost:3000)

## 8. Limitations / Future Improvements
- Joint fusion is rule-based and intentionally transparent (not a learned deep fusion model).
- URL analysis currently caps the number of URLs analyzed per request to prevent extreme latency.
- Potential next improvements:
  - calibrated per-mode thresholds per environment
  - richer email indicators (sender authentication signals)
  - asynchronous batch URL analysis for very long email bodies
