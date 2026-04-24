Advanced Phishing Detection using hybrid AI models - concept : We’ll build a system that takes a URL (and optionally page content/email text) and predicts: -Phishing (malicious / fake login / credential theft) -Legitimate We’ll use a hybrid approach: -URL-based signals (fast, works even if website blocks us) -Domain/host signals (WHOIS age, HTTPS, redirects, etc. if available) -Content/NLP signals (optional but impressive: page title/text patterns) Then we’ll combine these signals with: -Traditional ML (Random Forest / XGBoost / Logistic Regression) -and optionally a light Deep Learning classifier for text/content (if we include it) datasets : -PhiUSIIL Phishing URL Dataset (tabular, large, modern; UCI + Kaggle mirrors). -phishtank_online_valid(phishing URLs) -top-1m.csv(tranco dataset for legitmate URls) -UCI Phishing Websites dataset (classic features; good for comparison/baselines). -Kaggle “phishing and legitimate urls” style datasets for quick prototyping. repo base : phish-detector/

## Deployment (Render + Vercel)
- Backend (Render): FastAPI service using `uvicorn app.backend.app.main:app --host 0.0.0.0 --port $PORT`
- Frontend (Vercel): Next.js app with Root Directory `app/frontend`
- Frontend env var: `NEXT_PUBLIC_API_BASE=https://<your-render-service>.onrender.com`

Local run:
```bash
# backend
uvicorn app.backend.app.main:app --reload --host 0.0.0.0 --port 8000

# frontend (new terminal)
cd app/frontend
npm install
NEXT_PUBLIC_API_BASE=http://localhost:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Detailed deployment steps: [`docs/deployment.md`](docs/deployment.md)
