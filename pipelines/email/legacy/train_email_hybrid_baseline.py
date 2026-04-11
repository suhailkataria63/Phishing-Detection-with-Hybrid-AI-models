#!/usr/bin/env python3

import os
import pandas as pd
from joblib import dump

from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler

from sklearn.linear_model import LogisticRegression

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, confusion_matrix


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

DATA = os.path.join(ROOT, "data/processed/email_dataset_v2_features.csv")
MODEL_OUT = os.path.join(ROOT, "models/email_hybrid_baseline.joblib")



TEXT_COLUMN = "text"

NUMERIC_COLUMNS = [
"url_count",
"has_ip_url",
"avg_url_length",
"suspicious_tld_count",
"shortener_count",
"exclamation_count",
"digit_ratio",
"capital_ratio",
"body_length"
]



def main():

    df = pd.read_csv(DATA)

    df = df[df["label"].isin([0,1])].copy()

    X = df[[TEXT_COLUMN] + NUMERIC_COLUMNS]
    y = df["label"]


    X_train, X_test, y_train, y_test = train_test_split(
        X, y,
        test_size=0.2,
        random_state=1337,
        stratify=y
    )


    preprocessor = ColumnTransformer(

        transformers=[

            (
                "text",
                TfidfVectorizer(
                    max_features=80000,
                    ngram_range=(1,2),
                    lowercase=True,
                    strip_accents="unicode",
                    sublinear_tf=True
                ),
                TEXT_COLUMN
            ),

            (
                "numeric",
                StandardScaler(),
                NUMERIC_COLUMNS
            )

        ]

    )


    model = Pipeline(

        steps=[
            ("preprocessor", preprocessor),

            ("classifier",
                LogisticRegression(
                    solver="liblinear",
                    max_iter=2000,
                    class_weight="balanced"
                )
            )
        ]

    )


    model.fit(X_train, y_train)


    preds = model.predict(X_test)
    probs = model.predict_proba(X_test)[:,1]


    print("Accuracy:", accuracy_score(y_test,preds))
    print("Precision:", precision_score(y_test,preds))
    print("Recall:", recall_score(y_test,preds))
    print("F1:", f1_score(y_test,preds))
    print("ROC-AUC:", roc_auc_score(y_test,probs))


    print("Confusion Matrix")
    print(confusion_matrix(y_test,preds))


    dump(model, MODEL_OUT)


if __name__ == "__main__":
    main()
