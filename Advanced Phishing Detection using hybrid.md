Advanced Phishing Detection using hybrid AI models -
    concept :
                We’ll build a system that takes a URL (and optionally page content/email text) and predicts:
                -Phishing (malicious / fake login / credential theft)
                -Legitimate
                We’ll use a hybrid approach:
                -URL-based signals (fast, works even if website blocks us)
                -Domain/host signals (WHOIS age, HTTPS, redirects, etc. if available)
                -Content/NLP signals (optional but impressive: page title/text patterns)
                Then we’ll combine these signals with:
                -Traditional ML (Random Forest / XGBoost / Logistic Regression)
                -and optionally a light Deep Learning classifier for text/content (if we include it)
    datasets :
                -PhiUSIIL Phishing URL Dataset (tabular, large, modern; UCI + Kaggle mirrors).
                -phishtank_online_valid(phishing URLs)
                -top-1m.csv(tranco dataset for legitmate URls)
                -UCI Phishing Websites dataset (classic features; good for comparison/baselines).
                -Kaggle “phishing and legitimate urls” style datasets for quick prototyping.
    repo base :
                phish-detector/

                frontend/               # Next.js + Tailwind
                         src/
                            app/ or pages/
                                           components/
                                                      UrlInput.tsx
                                                      ResultCard.tsx
                                                      ProbabilityMeter.tsx
                                                      ReasonsList.tsx
                                                      ContextPanel.tsx
                            lib/
                                api.ts                # call backend
                                validators.ts         # URL validation


                backend/                # FastAPI
                        training/
                                    train_url_model.py
                                    evaluate.py
                                    feature_schema.json

                        main.py                 # FastAPI init + routes
                        schemas.py              # Pydantic request/response models
                        feature_extractor.py    # URL → features
                        model_loader.py         # load model artifacts
                        infer.py                # prediction pipeline
                        explain.py              # “reasons” logic (feature importance / SHAP-lite)
                        enrich_context.py       # optional WHOIS/DNS/redirect logic
                        cache.py                # sqlite cache for enrichment
                        config.py               # env vars, toggles

                models/                 # saved artifacts (model, schema)

                datasets/               # raw + processed (optional, or gitignored)

                docs/                   # diagrams, report images

                docker-compose.yml      # optional

                README.md

    workflow : 
                Next.js (client)  →  FastAPI /predict  →  feature extraction  →  model inference
                    ← JSON result (label, prob, reasons, optional context)

    url model 2 -
                URL string
                ↓
                Character n-gram tokenizer (3–5 chars)
                ↓
                TF-IDF weighting
                ↓
                Logistic Regression (balanced)
                ↓
                Probability score (0–1)
