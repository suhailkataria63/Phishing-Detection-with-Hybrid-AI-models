#!/usr/bin/env python3
"""Train and evaluate transformer+numeric hybrid email phishing model (TG-5.8).

Pipeline:
- Text encoder: DistilBERT (`distilbert-base-uncased`)
- Numeric features: engineered URL/email features (auto-detected)
- Fusion: concatenate [CLS] text embedding with scaled numeric features
- Classifier head: Linear -> ReLU -> Dropout -> Linear (logit)

Outputs:
- models/email_transformer_model.pt
- models/email_transformer_scaler.joblib
- models/email_transformer_metadata.json
- reports/email_transformer_results.md
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
from joblib import dump
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v2_features.csv")
MODEL_OUT = os.path.join(ROOT, "models", "email_transformer_model.pt")
SCALER_OUT = os.path.join(ROOT, "models", "email_transformer_scaler.joblib")
META_OUT = os.path.join(ROOT, "models", "email_transformer_metadata.json")
REPORT_OUT = os.path.join(ROOT, "reports", "email_transformer_results.md")

TEXT_BASELINE_REPORT = os.path.join(ROOT, "reports", "email_baseline_report.md")
TEXT_CROSS_SOURCE_REPORT = os.path.join(ROOT, "reports", "email_cross_source_eval.md")
HYBRID_CROSS_SOURCE_REPORT = os.path.join(ROOT, "reports", "email_hybrid_cross_source_eval.md")

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 256
BATCH_SIZE = 16
EPOCHS = 3
LEARNING_RATE = 2e-5
RANDOM_SEED = 1337
TEST_SIZE = 0.2
THRESHOLDS = [0.2, 0.5, 0.8]
MISCLASS_LIMIT = 5
NUMERIC_VALID_RATIO = 0.8


@dataclass
class ExperimentConfig:
    exp_id: str
    name: str
    train_sources: List[str]
    test_source: str


EXPERIMENTS = [
    ExperimentConfig(
        exp_id="A",
        name="Train Enron+Nazario, Test SpamAssassin",
        train_sources=["enron", "nazario"],
        test_source="spamassassin",
    ),
    ExperimentConfig(
        exp_id="B",
        name="Train Enron+SpamAssassin, Test Nazario",
        train_sources=["enron", "spamassassin"],
        test_source="nazario",
    ),
    ExperimentConfig(
        exp_id="C",
        name="Train Nazario+SpamAssassin, Test Enron",
        train_sources=["nazario", "spamassassin"],
        test_source="enron",
    ),
]


class EmailHybridDataset(Dataset):
    """Dataset returning tokenized text + numeric features + label."""

    def __init__(
        self,
        texts: Sequence[str],
        numeric_features: np.ndarray,
        labels: Sequence[int],
        tokenizer,
        max_length: int,
    ) -> None:
        enc = tokenizer(
            list(texts),
            truncation=True,
            padding="max_length",
            max_length=max_length,
            return_tensors="pt",
        )
        self.input_ids = enc["input_ids"]
        self.attention_mask = enc["attention_mask"]
        self.numeric_features = torch.tensor(numeric_features, dtype=torch.float32)
        self.labels = torch.tensor(np.asarray(labels), dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "numeric_features": self.numeric_features[idx],
            "label": self.labels[idx],
        }


class EmailFusionEmbeddingDataset(Dataset):
    """Dataset for precomputed transformer embeddings + numeric features."""

    def __init__(
        self,
        text_embeddings: np.ndarray,
        numeric_features: np.ndarray,
        labels: Sequence[int],
    ) -> None:
        self.text_embeddings = torch.tensor(text_embeddings, dtype=torch.float32)
        self.numeric_features = torch.tensor(numeric_features, dtype=torch.float32)
        self.labels = torch.tensor(np.asarray(labels), dtype=torch.float32)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        return {
            "text_embedding": self.text_embeddings[idx],
            "numeric_features": self.numeric_features[idx],
            "label": self.labels[idx],
        }


class EmailTransformerHybridModel(nn.Module):
    def __init__(self, model_name: str, num_numeric_features: int) -> None:
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        text_dim = int(self.encoder.config.hidden_size)
        self.classifier = nn.Sequential(
            nn.Linear(text_dim + num_numeric_features, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        numeric_features: torch.Tensor,
    ) -> torch.Tensor:
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        text_embedding = outputs.last_hidden_state[:, 0, :]
        return self.forward_from_embedding(text_embedding, numeric_features)

    def forward_from_embedding(
        self,
        text_embedding: torch.Tensor,
        numeric_features: torch.Tensor,
    ) -> torch.Tensor:
        fused = torch.cat([text_embedding, numeric_features], dim=1)
        return self.classifier(fused).squeeze(1)


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def combine_text(subject: Any, body: Any) -> str:
    s = "" if pd.isna(subject) else str(subject).strip()
    b = "" if pd.isna(body) else str(body).strip()
    return f"{s} [SEP] {b}".strip()


def detect_numeric_feature_columns(df: pd.DataFrame) -> List[str]:
    excluded = {
        "subject",
        "body",
        "label",
        "source",
        "text",
        "sender",
        "sender_domain",
        "urls",
    }
    numeric_cols: List[str] = []

    for col in df.columns:
        lc = col.strip().lower()
        if lc in excluded:
            continue
        if lc.startswith("unnamed") or lc in {"index", "idx", "id"} or lc.endswith("_id"):
            continue

        converted = pd.to_numeric(df[col], errors="coerce")
        valid_ratio = float(converted.notna().mean())
        if valid_ratio >= NUMERIC_VALID_RATIO:
            numeric_cols.append(col)

    if not numeric_cols:
        raise ValueError("No numeric engineered feature columns detected in dataset.")

    return numeric_cols


def load_dataset(path: str) -> Tuple[pd.DataFrame, List[str], Dict[str, float], Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing dataset: {path}")

    df = pd.read_csv(path)
    required = {"subject", "body", "label", "source"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    df["label"] = pd.to_numeric(df["label"], errors="coerce")
    df = df.dropna(subset=["label"]).copy()
    df["label"] = df["label"].astype(int)
    df = df[df["label"].isin([0, 1])].copy()

    df["source"] = df["source"].astype(str).str.strip().str.lower()
    df["text"] = [combine_text(s, b) for s, b in zip(df["subject"], df["body"])]
    df = df[df["text"].str.len() > 0].copy()

    numeric_cols = detect_numeric_feature_columns(df)

    medians: Dict[str, float] = {}
    for col in numeric_cols:
        col_numeric = pd.to_numeric(df[col], errors="coerce")
        med = col_numeric.median(skipna=True)
        if pd.isna(med):
            med = 0.0
        medians[col] = float(med)
        df[col] = col_numeric.fillna(med).astype(float)

    summary = {
        "rows": int(len(df)),
        "label_counts": {int(k): int(v) for k, v in df["label"].value_counts().sort_index().items()},
        "source_counts": {str(k): int(v) for k, v in df["source"].value_counts().sort_index().items()},
        "numeric_feature_count": len(numeric_cols),
        "numeric_features": numeric_cols,
    }
    return df, numeric_cols, medians, summary


def make_loaders(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    numeric_cols: Sequence[str],
    scaler: StandardScaler,
    tokenizer,
    max_length: int,
    batch_size: int,
) -> Tuple[DataLoader, DataLoader]:
    x_train_num = scaler.fit_transform(train_df[numeric_cols].values)
    x_test_num = scaler.transform(test_df[numeric_cols].values)

    train_ds = EmailHybridDataset(
        texts=train_df["text"].tolist(),
        numeric_features=x_train_num,
        labels=train_df["label"].tolist(),
        tokenizer=tokenizer,
        max_length=max_length,
    )
    test_ds = EmailHybridDataset(
        texts=test_df["text"].tolist(),
        numeric_features=x_test_num,
        labels=test_df["label"].tolist(),
        tokenizer=tokenizer,
        max_length=max_length,
    )

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)
    return train_loader, test_loader


def compute_pos_weight(labels: Sequence[int], device: torch.device) -> torch.Tensor:
    y = np.asarray(labels)
    pos = float((y == 1).sum())
    neg = float((y == 0).sum())
    if pos <= 0:
        return torch.tensor(1.0, dtype=torch.float32, device=device)
    return torch.tensor(max(1.0, neg / pos), dtype=torch.float32, device=device)


def train_model(
    model: nn.Module,
    train_loader: DataLoader,
    device: torch.device,
    epochs: int,
    learning_rate: float,
    pos_weight: torch.Tensor,
) -> List[float]:
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)

    losses: List[float] = []
    for epoch in range(1, epochs + 1):
        model.train()
        running_loss = 0.0

        for batch in train_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            numeric_features = batch["numeric_features"].to(device)
            labels = batch["label"].to(device)

            optimizer.zero_grad()
            logits = model(input_ids, attention_mask, numeric_features)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            running_loss += float(loss.item())

        avg_loss = running_loss / max(1, len(train_loader))
        losses.append(avg_loss)
        print(f"  epoch {epoch}/{epochs} - train_loss={avg_loss:.4f}")

    return losses


def extract_text_embeddings(
    texts: Sequence[str],
    tokenizer,
    encoder: nn.Module,
    device: torch.device,
    max_length: int,
    batch_size: int,
) -> np.ndarray:
    embeddings: List[np.ndarray] = []
    encoder.eval()
    with torch.no_grad():
        for start in range(0, len(texts), batch_size):
            batch_texts = list(texts[start : start + batch_size])
            enc = tokenizer(
                batch_texts,
                truncation=True,
                padding="max_length",
                max_length=max_length,
                return_tensors="pt",
            )
            input_ids = enc["input_ids"].to(device)
            attention_mask = enc["attention_mask"].to(device)
            outputs = encoder(input_ids=input_ids, attention_mask=attention_mask)
            cls = outputs.last_hidden_state[:, 0, :].detach().cpu().numpy()
            embeddings.append(cls)
    if not embeddings:
        return np.zeros((0, int(getattr(encoder.config, "hidden_size", 768))), dtype=np.float32)
    return np.vstack(embeddings).astype(np.float32)


def make_embedding_loaders(
    train_embeddings: np.ndarray,
    test_embeddings: np.ndarray,
    train_numeric: np.ndarray,
    test_numeric: np.ndarray,
    train_labels: Sequence[int],
    test_labels: Sequence[int],
    batch_size: int,
) -> Tuple[DataLoader, DataLoader]:
    train_ds = EmailFusionEmbeddingDataset(
        text_embeddings=train_embeddings,
        numeric_features=train_numeric,
        labels=train_labels,
    )
    test_ds = EmailFusionEmbeddingDataset(
        text_embeddings=test_embeddings,
        numeric_features=test_numeric,
        labels=test_labels,
    )
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)
    return train_loader, test_loader


def train_classifier_head(
    model: EmailTransformerHybridModel,
    train_loader: DataLoader,
    device: torch.device,
    epochs: int,
    learning_rate: float,
    pos_weight: torch.Tensor,
) -> List[float]:
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=learning_rate)

    losses: List[float] = []
    for epoch in range(1, epochs + 1):
        model.classifier.train()
        running_loss = 0.0
        for batch in train_loader:
            text_embedding = batch["text_embedding"].to(device)
            numeric_features = batch["numeric_features"].to(device)
            labels = batch["label"].to(device)

            optimizer.zero_grad()
            logits = model.forward_from_embedding(text_embedding, numeric_features)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.classifier.parameters(), 1.0)
            optimizer.step()
            running_loss += float(loss.item())

        avg_loss = running_loss / max(1, len(train_loader))
        losses.append(avg_loss)
        print(f"  epoch {epoch}/{epochs} - head_loss={avg_loss:.4f}")
    return losses


def predict_from_embeddings(
    model: EmailTransformerHybridModel,
    data_loader: DataLoader,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray]:
    model.classifier.eval()
    probs: List[np.ndarray] = []
    labels: List[np.ndarray] = []
    with torch.no_grad():
        for batch in data_loader:
            text_embedding = batch["text_embedding"].to(device)
            numeric_features = batch["numeric_features"].to(device)
            y = batch["label"].detach().cpu().numpy()
            logits = model.forward_from_embedding(text_embedding, numeric_features)
            p = torch.sigmoid(logits).detach().cpu().numpy()
            probs.append(p)
            labels.append(y)
    if not probs:
        return np.array([]), np.array([])
    return np.concatenate(probs), np.concatenate(labels)


def predict_probabilities(
    model: nn.Module,
    data_loader: DataLoader,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray]:
    model.eval()
    probs: List[np.ndarray] = []
    labels: List[np.ndarray] = []

    with torch.no_grad():
        for batch in data_loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            numeric_features = batch["numeric_features"].to(device)
            y = batch["label"].detach().cpu().numpy()

            logits = model(input_ids, attention_mask, numeric_features)
            p = torch.sigmoid(logits).detach().cpu().numpy()

            probs.append(p)
            labels.append(y)

    if not probs:
        return np.array([]), np.array([])

    return np.concatenate(probs), np.concatenate(labels)


def evaluate_at_threshold(
    y_true: np.ndarray,
    probs: np.ndarray,
    threshold: float,
) -> Dict[str, Any]:
    preds = (probs >= threshold).astype(int)
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    metrics: Dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, preds)),
        "precision": float(precision_score(y_true, preds, zero_division=0)),
        "recall": float(recall_score(y_true, preds, zero_division=0)),
        "f1": float(f1_score(y_true, preds, zero_division=0)),
        "confusion_matrix": cm.tolist(),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
        "true_negatives": int(tn),
        "threshold": float(threshold),
    }

    if len(np.unique(y_true)) > 1:
        metrics["roc_auc"] = float(roc_auc_score(y_true, probs))
    else:
        metrics["roc_auc"] = None

    return metrics


def evaluate_thresholds(y_true: np.ndarray, probs: np.ndarray) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for threshold in THRESHOLDS:
        m = evaluate_at_threshold(y_true, probs, threshold)
        rows.append(
            {
                "threshold": threshold,
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
                "false_positives": m["false_positives"],
                "false_negatives": m["false_negatives"],
            }
        )
    return rows


def collect_misclassifications(
    test_df: pd.DataFrame,
    probs: np.ndarray,
    threshold: float,
    limit: int,
) -> List[Dict[str, Any]]:
    y_true = test_df["label"].astype(int).to_numpy()
    preds = (probs >= threshold).astype(int)
    mismatches = np.where(preds != y_true)[0]

    rows: List[Dict[str, Any]] = []
    for idx in mismatches[:limit]:
        text_preview = str(test_df.iloc[idx]["text"]).replace("\n", " ").strip()[:180]
        rows.append(
            {
                "source": str(test_df.iloc[idx]["source"]),
                "true_label": int(y_true[idx]),
                "pred_label": int(preds[idx]),
                "probability": float(probs[idx]),
                "text_preview": text_preview,
            }
        )
    return rows


def run_experiment(
    exp_name: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    numeric_cols: Sequence[str],
    tokenizer,
    model_name: str,
    max_length: int,
    batch_size: int,
    epochs: int,
    learning_rate: float,
    device: torch.device,
    misclass_limit: int,
    freeze_encoder: bool,
) -> Dict[str, Any]:
    print(f"\n[{exp_name}] train={len(train_df):,} test={len(test_df):,}")

    scaler = StandardScaler()
    train_numeric = scaler.fit_transform(train_df[numeric_cols].values).astype(np.float32)
    test_numeric = scaler.transform(test_df[numeric_cols].values).astype(np.float32)

    model = EmailTransformerHybridModel(model_name=model_name, num_numeric_features=len(numeric_cols))
    if freeze_encoder:
        for param in model.encoder.parameters():
            param.requires_grad = False
    model.to(device)

    pos_weight = compute_pos_weight(train_df["label"].to_numpy(), device)
    if freeze_encoder:
        print("  extracting transformer embeddings (frozen encoder)...")
        train_emb = extract_text_embeddings(
            texts=train_df["text"].tolist(),
            tokenizer=tokenizer,
            encoder=model.encoder,
            device=device,
            max_length=max_length,
            batch_size=batch_size,
        )
        test_emb = extract_text_embeddings(
            texts=test_df["text"].tolist(),
            tokenizer=tokenizer,
            encoder=model.encoder,
            device=device,
            max_length=max_length,
            batch_size=batch_size,
        )
        train_loader, test_loader = make_embedding_loaders(
            train_embeddings=train_emb,
            test_embeddings=test_emb,
            train_numeric=train_numeric,
            test_numeric=test_numeric,
            train_labels=train_df["label"].to_numpy(),
            test_labels=test_df["label"].to_numpy(),
            batch_size=batch_size,
        )
        losses = train_classifier_head(
            model=model,
            train_loader=train_loader,
            device=device,
            epochs=epochs,
            learning_rate=learning_rate,
            pos_weight=pos_weight,
        )
        probs, y_true = predict_from_embeddings(model, test_loader, device)
    else:
        train_loader, test_loader = make_loaders(
            train_df=train_df,
            test_df=test_df,
            numeric_cols=numeric_cols,
            scaler=scaler,
            tokenizer=tokenizer,
            max_length=max_length,
            batch_size=batch_size,
        )
        losses = train_model(
            model=model,
            train_loader=train_loader,
            device=device,
            epochs=epochs,
            learning_rate=learning_rate,
            pos_weight=pos_weight,
        )
        probs, y_true = predict_probabilities(model, test_loader, device)

    default_metrics = evaluate_at_threshold(y_true, probs, threshold=0.5)
    threshold_metrics = evaluate_thresholds(y_true, probs)
    misclassified = collect_misclassifications(test_df.reset_index(drop=True), probs, 0.5, misclass_limit)

    return {
        "model": model,
        "scaler": scaler,
        "train_size": int(len(train_df)),
        "test_size": int(len(test_df)),
        "train_label_counts": {
            int(k): int(v) for k, v in train_df["label"].value_counts().sort_index().items()
        },
        "test_label_counts": {
            int(k): int(v) for k, v in test_df["label"].value_counts().sort_index().items()
        },
        "metrics": default_metrics,
        "threshold_metrics": threshold_metrics,
        "misclassified": misclassified,
        "train_losses": losses,
    }


def parse_random_baseline(path: str) -> Dict[str, Optional[float]]:
    if not os.path.exists(path):
        return {}

    text = open(path, "r", encoding="utf-8").read()

    def extract(name: str) -> Optional[float]:
        m = re.search(rf"- {name}: \*\*(.*?)\*\*", text)
        if not m:
            return None
        token = m.group(1).strip().lower()
        if token in {"n/a", "na"}:
            return None
        try:
            return float(token)
        except ValueError:
            return None

    return {
        "accuracy": extract("Accuracy"),
        "precision": extract("Precision"),
        "recall": extract("Recall"),
        "f1": extract("F1"),
        "roc_auc": extract("ROC-AUC"),
    }


def parse_cross_source_baseline(path: str) -> Dict[str, Dict[str, Optional[float]]]:
    if not os.path.exists(path):
        return {}

    text = open(path, "r", encoding="utf-8").read()
    out: Dict[str, Dict[str, Optional[float]]] = {}

    for exp_id in ("A", "B", "C"):
        m = re.search(rf"## Experiment {exp_id}:(.*?)(?:\n## Experiment [ABC]:|\Z)", text, flags=re.S)
        if not m:
            continue
        section = m.group(1)

        def extract(name: str) -> Optional[float]:
            mm = re.search(rf"- {name}: \*\*(.*?)\*\*", section)
            if not mm:
                if name == "ROC-AUC" and "ROC-AUC: n/a" in section:
                    return None
                return None
            token = mm.group(1).strip().lower()
            if token in {"n/a", "na"}:
                return None
            try:
                return float(token)
            except ValueError:
                return None

        out[exp_id] = {
            "accuracy": extract("Accuracy"),
            "precision": extract("Precision"),
            "recall": extract("Recall"),
            "f1": extract("F1"),
            "roc_auc": extract("ROC-AUC"),
        }
    return out


def format_threshold_table(rows: Sequence[Dict[str, Any]]) -> List[str]:
    lines = []
    lines.append("| Threshold | Precision | Recall | F1 | False Positives | False Negatives |")
    lines.append("|---:|---:|---:|---:|---:|---:|")
    for r in rows:
        lines.append(
            f"| {r['threshold']:.1f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | {r['false_positives']} | {r['false_negatives']} |"
        )
    return lines


def write_report(
    report_path: str,
    dataset_summary: Dict[str, Any],
    random_result: Dict[str, Any],
    cross_source_results: Dict[str, Dict[str, Any]],
    text_random_baseline: Dict[str, Optional[float]],
    text_cross_baseline: Dict[str, Dict[str, Optional[float]]],
    hybrid_cross_baseline: Dict[str, Dict[str, Optional[float]]],
    numeric_cols: Sequence[str],
    total_seconds: float,
    freeze_encoder: bool,
) -> None:
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    lines: List[str] = []
    lines.append("# Email Transformer Hybrid Results (TG-5.8)")
    lines.append("")
    lines.append(f"Generated: {datetime.utcnow().isoformat()}Z")
    lines.append("")

    lines.append("## Dataset Summary")
    lines.append(f"- Dataset: `data/processed/email_dataset_v2_features.csv`")
    lines.append(f"- Rows: {dataset_summary['rows']:,}")
    lines.append(f"- Label distribution: {dataset_summary['label_counts']}")
    lines.append(f"- Source distribution: {dataset_summary['source_counts']}")
    lines.append(f"- Numeric feature count: {dataset_summary['numeric_feature_count']}")
    lines.append(f"- Numeric feature columns: {list(numeric_cols)}")
    lines.append(f"- Encoder fine-tuning: {'disabled (frozen encoder)' if freeze_encoder else 'enabled'}")
    lines.append("")

    rm = random_result["metrics"]
    lines.append("## Random Split Results")
    lines.append(f"- Train size: {random_result['train_size']:,} | Test size: {random_result['test_size']:,}")
    lines.append(f"- Train labels: {random_result['train_label_counts']}")
    lines.append(f"- Test labels: {random_result['test_label_counts']}")
    lines.append(f"- Accuracy: **{rm['accuracy']:.4f}**")
    lines.append(f"- Precision: **{rm['precision']:.4f}**")
    lines.append(f"- Recall: **{rm['recall']:.4f}**")
    lines.append(f"- F1: **{rm['f1']:.4f}**")
    if rm["roc_auc"] is None:
        lines.append("- ROC-AUC: n/a")
    else:
        lines.append(f"- ROC-AUC: **{rm['roc_auc']:.4f}**")
    lines.append("- Confusion matrix (rows=true [0,1], cols=pred [0,1]):")
    lines.append("```")
    lines.append(str(rm["confusion_matrix"]))
    lines.append("```")
    lines.append("")
    lines.append("### Random Split Threshold Analysis")
    lines.extend(format_threshold_table(random_result["threshold_metrics"]))
    lines.append("")

    if random_result["misclassified"]:
        lines.append("### Random Split Sample Misclassifications")
        for ex in random_result["misclassified"]:
            lines.append(
                f"- source={ex['source']} true={ex['true_label']} pred={ex['pred_label']} prob={ex['probability']:.4f} text=\"{ex['text_preview']}\""
            )
        lines.append("")

    lines.append("## Cross-Source Results")
    for exp in EXPERIMENTS:
        res = cross_source_results[exp.exp_id]
        m = res["metrics"]
        lines.append(f"### Experiment {exp.exp_id}: {exp.name}")
        lines.append(f"- Train size: {res['train_size']:,} | Test size: {res['test_size']:,}")
        lines.append(f"- Train labels: {res['train_label_counts']}")
        lines.append(f"- Test labels: {res['test_label_counts']}")
        lines.append(f"- Accuracy: **{m['accuracy']:.4f}**")
        lines.append(f"- Precision: **{m['precision']:.4f}**")
        lines.append(f"- Recall: **{m['recall']:.4f}**")
        lines.append(f"- F1: **{m['f1']:.4f}**")
        if m["roc_auc"] is None:
            lines.append("- ROC-AUC: n/a (single-class test set)")
        else:
            lines.append(f"- ROC-AUC: **{m['roc_auc']:.4f}**")
        lines.append("- Confusion matrix (rows=true [0,1], cols=pred [0,1]):")
        lines.append("```")
        lines.append(str(m["confusion_matrix"]))
        lines.append("```")
        lines.append("")
        lines.append(f"#### Threshold Analysis (Experiment {exp.exp_id})")
        lines.extend(format_threshold_table(res["threshold_metrics"]))
        lines.append("")

        if res["misclassified"]:
            lines.append(f"#### Sample Misclassifications (Experiment {exp.exp_id})")
            for ex in res["misclassified"]:
                lines.append(
                    f"- source={ex['source']} true={ex['true_label']} pred={ex['pred_label']} prob={ex['probability']:.4f} text=\"{ex['text_preview']}\""
                )
            lines.append("")

    lines.append("## Key Findings")
    if text_random_baseline:
        t_f1 = text_random_baseline.get("f1")
        h_f1 = rm["f1"]
        if t_f1 is not None:
            delta = h_f1 - t_f1
            lines.append(
                f"- Random split vs text-only baseline F1: {t_f1:.4f} -> {h_f1:.4f} (delta {delta:+.4f})."
            )

    for exp in EXPERIMENTS:
        tm = text_cross_baseline.get(exp.exp_id, {})
        hm = hybrid_cross_baseline.get(exp.exp_id, {})
        cm = cross_source_results[exp.exp_id]["metrics"]

        if tm and tm.get("f1") is not None:
            lines.append(
                f"- Experiment {exp.exp_id} vs text-only F1: {tm['f1']:.4f} -> {cm['f1']:.4f}; recall: {tm['recall']:.4f} -> {cm['recall']:.4f}."
            )
        if hm and hm.get("f1") is not None:
            lines.append(
                f"- Experiment {exp.exp_id} vs hybrid baseline F1: {hm['f1']:.4f} -> {cm['f1']:.4f}; recall: {hm['recall']:.4f} -> {cm['recall']:.4f}."
            )

    lines.append("- Lower thresholds (0.2) consistently raise recall while increasing false positives.")
    lines.append("- Cross-source generalization remains the hardest setting and should drive next iterations.")
    lines.append("")

    lines.append("## Conclusion")
    lines.append("- Transformer+numeric fusion is now trained end-to-end and reproducible via saved artifacts.")
    lines.append("- Next steps: calibration, source-aware regularization, and stronger domain generalization strategies before production rollout.")
    lines.append(f"- Total runtime: {total_seconds:.1f} seconds")

    with open(report_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def save_artifacts(
    model: EmailTransformerHybridModel,
    scaler: StandardScaler,
    numeric_cols: Sequence[str],
    medians: Dict[str, float],
    args,
    device: torch.device,
    freeze_encoder: bool,
) -> None:
    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)

    payload = {
        "state_dict": model.state_dict(),
        "model_name": args.model_name,
        "num_numeric_features": len(numeric_cols),
        "hidden_size": int(model.encoder.config.hidden_size),
        "max_length": int(args.max_length),
        "label_mapping": {0: "legitimate", 1: "phishing"},
    }
    torch.save(payload, MODEL_OUT)
    dump(scaler, SCALER_OUT)

    metadata = {
        "version": "email_transformer_hybrid_v1",
        "created_at": datetime.utcnow().isoformat() + "Z",
        "model_name": args.model_name,
        "max_length": int(args.max_length),
        "batch_size": int(args.batch_size),
        "epochs": int(args.epochs),
        "learning_rate": float(args.learning_rate),
        "device_used": str(device),
        "numeric_feature_columns": list(numeric_cols),
        "numeric_fill_medians": medians,
        "scaler_path": os.path.relpath(SCALER_OUT, ROOT),
        "model_path": os.path.relpath(MODEL_OUT, ROOT),
        "label_mapping": {"0": "legitimate", "1": "phishing"},
        "text_build": "subject + [SEP] + body",
        "thresholds_evaluated": THRESHOLDS,
        "freeze_encoder": bool(freeze_encoder),
    }
    with open(META_OUT, "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train transformer+numeric hybrid phishing email model")
    parser.add_argument("--data", type=str, default=DATA_CSV, help="Path to dataset")
    parser.add_argument("--model-name", type=str, default=MODEL_NAME, help="HF model name")
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH, help="Tokenizer max length")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE, help="Batch size")
    parser.add_argument("--epochs", type=int, default=EPOCHS, help="Training epochs")
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE, help="AdamW learning rate")
    parser.add_argument("--seed", type=int, default=RANDOM_SEED, help="Random seed")
    parser.add_argument("--test-size", type=float, default=TEST_SIZE, help="Random split test size")
    parser.add_argument("--misclass-limit", type=int, default=MISCLASS_LIMIT, help="Misclassification samples per experiment")
    parser.add_argument(
        "--freeze-encoder",
        action="store_true",
        help="Freeze DistilBERT encoder and train only fusion/classifier head (faster on CPU).",
    )
    args = parser.parse_args()

    misclass_limit = max(0, int(args.misclass_limit))

    started = time.time()
    set_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    df, numeric_cols, medians, dataset_summary = load_dataset(args.data)
    print(f"Loaded dataset rows: {dataset_summary['rows']:,}")
    print(f"Numeric feature columns ({len(numeric_cols)}): {numeric_cols}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    # ---------- Random split ----------
    train_df, test_df = train_test_split(
        df,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=df["label"],
    )
    train_df = train_df.reset_index(drop=True)
    test_df = test_df.reset_index(drop=True)

    random_result = run_experiment(
        exp_name="Random Split",
        train_df=train_df,
        test_df=test_df,
        numeric_cols=numeric_cols,
        tokenizer=tokenizer,
        model_name=args.model_name,
        max_length=args.max_length,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        device=device,
        misclass_limit=misclass_limit,
        freeze_encoder=args.freeze_encoder,
    )

    # Save artifacts from the random-split model.
    save_artifacts(
        model=random_result["model"],
        scaler=random_result["scaler"],
        numeric_cols=numeric_cols,
        medians=medians,
        args=args,
        device=device,
        freeze_encoder=args.freeze_encoder,
    )

    # ---------- Cross-source experiments ----------
    cross_source_results: Dict[str, Dict[str, Any]] = {}
    for exp in EXPERIMENTS:
        exp_train = df[df["source"].isin(exp.train_sources)].reset_index(drop=True)
        exp_test = df[df["source"] == exp.test_source].reset_index(drop=True)

        if exp_train.empty:
            raise ValueError(f"Experiment {exp.exp_id}: training split is empty")
        if exp_test.empty:
            raise ValueError(f"Experiment {exp.exp_id}: test split is empty")

        cross_source_results[exp.exp_id] = run_experiment(
            exp_name=f"Experiment {exp.exp_id}",
            train_df=exp_train,
            test_df=exp_test,
            numeric_cols=numeric_cols,
            tokenizer=tokenizer,
            model_name=args.model_name,
            max_length=args.max_length,
            batch_size=args.batch_size,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            device=device,
            misclass_limit=misclass_limit,
            freeze_encoder=args.freeze_encoder,
        )

    # ---------- Reporting ----------
    text_random_baseline = parse_random_baseline(TEXT_BASELINE_REPORT)
    text_cross_baseline = parse_cross_source_baseline(TEXT_CROSS_SOURCE_REPORT)
    hybrid_cross_baseline = parse_cross_source_baseline(HYBRID_CROSS_SOURCE_REPORT)

    total_seconds = time.time() - started

    write_report(
        report_path=REPORT_OUT,
        dataset_summary=dataset_summary,
        random_result=random_result,
        cross_source_results=cross_source_results,
        text_random_baseline=text_random_baseline,
        text_cross_baseline=text_cross_baseline,
        hybrid_cross_baseline=hybrid_cross_baseline,
        numeric_cols=numeric_cols,
        total_seconds=total_seconds,
        freeze_encoder=args.freeze_encoder,
    )

    rm = random_result["metrics"]
    random_roc = "n/a" if rm["roc_auc"] is None else f"{rm['roc_auc']:.4f}"
    print("\n=== Final Summary ===")
    print(
        "Random split | "
        f"Acc={rm['accuracy']:.4f} Prec={rm['precision']:.4f} "
        f"Rec={rm['recall']:.4f} F1={rm['f1']:.4f} "
        f"ROC-AUC={random_roc}"
    )

    for exp in EXPERIMENTS:
        m = cross_source_results[exp.exp_id]["metrics"]
        roc = "n/a" if m["roc_auc"] is None else f"{m['roc_auc']:.4f}"
        print(
            f"Experiment {exp.exp_id} | "
            f"Acc={m['accuracy']:.4f} Prec={m['precision']:.4f} "
            f"Rec={m['recall']:.4f} F1={m['f1']:.4f} ROC-AUC={roc}"
        )

    print(f"Saved model: {os.path.relpath(MODEL_OUT, ROOT)}")
    print(f"Saved scaler: {os.path.relpath(SCALER_OUT, ROOT)}")
    print(f"Saved metadata: {os.path.relpath(META_OUT, ROOT)}")
    print(f"Saved report: {os.path.relpath(REPORT_OUT, ROOT)}")
    print(f"Total runtime: {total_seconds:.1f}s")


if __name__ == "__main__":
    main()
