import os
from pathlib import Path

# Prevent noisy loky physical-core detection warnings on macOS environments.
if not os.environ.get("LOKY_MAX_CPU_COUNT"):
    logical = os.cpu_count() or 1
    os.environ["LOKY_MAX_CPU_COUNT"] = str(max(1, logical - 1))

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, roc_auc_score

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "dataset_v1.csv"

OUT_PATH = PROJECT_ROOT / "models" / "url_model_v2_ngrams.joblib"
REPORT_PATH = PROJECT_ROOT / "reports" / "url_model_v2_ngrams_report.txt"


def main():
    df = pd.read_csv(DATA_PATH)
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)

    X = df["url"].astype(str)
    y = df["label"].astype(int)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    vec = TfidfVectorizer(
        analyzer="char",
        ngram_range=(3, 5),
        min_df=2,
        max_features=250_000,
    )

    clf = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
    )

    Xtr = vec.fit_transform(X_train)
    Xte = vec.transform(X_test)

    clf.fit(Xtr, y_train)
    proba = clf.predict_proba(Xte)[:, 1]

    auc = roc_auc_score(y_test, proba)
    rep = classification_report(y_test, (proba >= 0.5).astype(int), digits=4)

    bundle = {
        "version": "url_model_v2_ngrams",
        "vectorizer": vec,
        "model": clf,
        "ngram_range": (3, 5),
    }

    joblib.dump(bundle, OUT_PATH)

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(f"ROC-AUC: {auc:.6f}\n\n{rep}\n", encoding="utf-8")

    print("Saved model:", OUT_PATH)
    print("Saved report:", REPORT_PATH)
    print("ROC-AUC:", auc)


if __name__ == "__main__":
    main()
