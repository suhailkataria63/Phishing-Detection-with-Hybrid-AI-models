import joblib
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parents[4]   # .../phish-detector

V2_PATH = PROJECT_ROOT / "models" / "url" / "url_model_v2_ngrams.joblib"


class URLModelV2Ngrams:
    """
    v2 model: TF-IDF char n-grams + Logistic Regression.
    This is a string-pattern model (not feature-engineered).
    """

    def __init__(self):
        self.bundle = None
        self.vectorizer = None
        self.model = None
        self.version = "url_model_v2_ngrams"

    def load(self):
        if not V2_PATH.exists():
            raise FileNotFoundError(f"V2 model not found: {V2_PATH}")

        bundle = joblib.load(V2_PATH)
        if not isinstance(bundle, dict):
            raise TypeError(f"Expected dict bundle in v2 joblib, got: {type(bundle)}")

        self.bundle = bundle
        self.vectorizer = bundle.get("vectorizer")
        self.model = bundle.get("model")
        self.version = bundle.get("version", self.version)

        if self.vectorizer is None or self.model is None:
            raise ValueError("V2 bundle missing vectorizer/model")

        if not hasattr(self.model, "predict_proba"):
            raise TypeError("V2 model has no predict_proba()")

    def predict_proba(self, url: str) -> float:
        if self.model is None or self.vectorizer is None:
            raise RuntimeError("V2 model not loaded")

        X = self.vectorizer.transform([str(url)])
        return float(self.model.predict_proba(X)[0][1])
