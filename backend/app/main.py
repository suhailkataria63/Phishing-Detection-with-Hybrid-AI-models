from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .schemas import PredictRequest, PredictResponse
from .config import settings
from app.ml.hybrid_url import HybridURLModel

app = FastAPI(title=settings.app_name)
url_model = HybridURLModel()


origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"status": "ok", "service": settings.app_name}

@app.on_event("startup")
def startup_event():
    url_model.load()

@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    return url_model.predict(req.url, enable_explain=req.enable_explain)
