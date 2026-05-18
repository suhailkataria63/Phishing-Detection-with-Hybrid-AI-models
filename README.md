# Phishing Detection with Hybrid AI Models

Advanced phishing detection system that predicts whether an input is:
- `phishing` (malicious / fake login / credential theft)
- `legitimate`

The system supports three detection modes:
- URL Detection
- Email Detection
- Joint Detection (Email + URL)

## Concept
We use a hybrid strategy so detection remains strong even when one signal is weak.

Signal layers:
- URL-based signals: lexical patterns, suspicious paths, typosquat/lookalike cues
- Domain/host signals: trusted-domain checks, IP-host detection, redirect/lure patterns
- Content/NLP signals: email-text classifier and language cues

Model layers:
- Traditional ML models for URL and engineered features
- Transformer-based email classifier (DistilBERT text-only frozen encoder)
- Rule-assisted ensemble logic for transparent joint scoring

## Dataset Sources
URL-side datasets used/planned:
- PhiUSIIL Phishing URL Dataset (modern tabular URL features)
- `phishtank_online_valid.json` (phishing URLs)
- `top-1m.csv` (Tranco top domains for legitimate/reputable reference)
- UCI Phishing Websites dataset (baseline comparison)
- Kaggle phishing vs legitimate URL datasets (rapid prototyping/augmentation)

Email-side datasets used:
- Enron (`data/raw/enron/emails.csv`)
- Nazario (`data/raw/nazario/nazario.csv`)
- SpamAssassin archives (`data/raw/spamassassin/*.tar.bz2`)

## Repository Base
```text
phish-detector/
```

Key paths:
- Backend: `app/backend`
- Frontend: `app/frontend`
- Data: `data/`
- Models: `models/`
- Pipelines: `pipelines/`
- Reports: `reports/`
- Docs: `docs/`

## Current Product Capabilities
- URL phishing inference with explainable reasons
- Email phishing inference with calibrated risk scoring
- Joint email+URL inference with strategy selection (`baseline` / `optimized`)
- Batch-style analysis datasets and evaluation tooling
- Health diagnostics for model availability and load errors

## Local Run
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

## Deployment
- Render + Vercel setup details: [`docs/deployment.md`](docs/deployment.md)
- Hugging Face Spaces (Docker) backend deployment is also documented there.

## Notes
- This project is intentionally explainability-focused for analyst workflows.
- Joint detection is designed to be transparent, with rule metadata surfaced in responses.
