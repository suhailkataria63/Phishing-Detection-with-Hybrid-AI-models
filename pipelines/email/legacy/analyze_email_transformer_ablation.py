#!/usr/bin/env python3
"""TG-5.9 transformer ablation for phishing email detection.

Variants:
- fusion_frozen
- fusion_unfrozen
- textonly_frozen
- textonly_unfrozen

Splits:
- random
- cross_source_a
- cross_source_b
- cross_source_c (flagged invalid if test split is single-class)

Outputs:
- reports/email_transformer_ablation_report.md
- reports/email_transformer_ablation_metrics.csv
- reports/email_transformer_thresholds.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
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

OUT_MD = os.path.join(ROOT, "reports", "email_transformer_ablation_report.md")
OUT_METRICS_CSV = os.path.join(ROOT, "reports", "email_transformer_ablation_metrics.csv")
OUT_THRESH_CSV = os.path.join(ROOT, "reports", "email_transformer_thresholds.csv")

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 256
BATCH_SIZE = 16
FROZEN_EPOCHS = 3
UNFROZEN_EPOCHS = 2
LEARNING_RATE = 2e-5
RANDOM_SEED = 1337
TEST_SIZE = 0.2
THRESHOLDS = [0.2, 0.5, 0.8]
NUMERIC_VALID_RATIO = 0.8


@dataclass
class VariantConfig:
    name: str
    use_numeric: bool
    freeze_encoder: bool
    epochs: int


@dataclass
class SplitConfig:
    key: str
    name: str
    train_sources: Optional[List[str]] = None
    test_source: Optional[str] = None


VARIANTS = [
    VariantConfig("fusion_frozen", use_numeric=True, freeze_encoder=True, epochs=FROZEN_EPOCHS),
    VariantConfig("fusion_unfrozen", use_numeric=True, freeze_encoder=False, epochs=UNFROZEN_EPOCHS),
    VariantConfig("textonly_frozen", use_numeric=False, freeze_encoder=True, epochs=FROZEN_EPOCHS),
    VariantConfig("textonly_unfrozen", use_numeric=False, freeze_encoder=False, epochs=UNFROZEN_EPOCHS),
]

SPLITS = [
    SplitConfig("random", "Random Stratified Split"),
    SplitConfig("cross_source_a", "Cross-Source A (Train Enron+Nazario, Test SpamAssassin)", ["enron", "nazario"], "spamassassin"),
    SplitConfig("cross_source_b", "Cross-Source B (Train Enron+SpamAssassin, Test Nazario)", ["enron", "spamassassin"], "nazario"),
    SplitConfig("cross_source_c", "Cross-Source C (Train Nazario+SpamAssassin, Test Enron)", ["nazario", "spamassassin"], "enron"),
]


class TokenizedFusionDataset(Dataset):
    def __init__(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        numeric_features: np.ndarray,
        labels: np.ndarray,
    ) -> None:
        self.input_ids = input_ids
        self.attention_mask = attention_mask
        self.numeric_features = torch.tensor(numeric_features, dtype=torch.float32)
        self.labels = torch.tensor(labels.astype(np.float32), dtype=torch.float32)

    def __len__(self) -> int:
        return int(self.labels.shape[0])

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        return {
            "input_ids": self.input_ids[idx],
            "attention_mask": self.attention_mask[idx],
            "numeric_features": self.numeric_features[idx],
            "label": self.labels[idx],
        }


class EmbeddingFusionDataset(Dataset):
    def __init__(self, embeddings: np.ndarray, numeric_features: np.ndarray, labels: np.ndarray) -> None:
        self.embeddings = torch.tensor(embeddings, dtype=torch.float32)
        self.numeric_features = torch.tensor(numeric_features, dtype=torch.float32)
        self.labels = torch.tensor(labels.astype(np.float32), dtype=torch.float32)

    def __len__(self) -> int:
        return int(self.labels.shape[0])

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        return {
            "text_embedding": self.embeddings[idx],
            "numeric_features": self.numeric_features[idx],
            "label": self.labels[idx],
        }


class DistilBertFusionModel(nn.Module):
    def __init__(self, model_name: str, num_numeric_features: int) -> None:
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        hidden = int(self.encoder.config.hidden_size)
        self.classifier = nn.Sequential(
            nn.Linear(hidden + num_numeric_features, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
        )

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor, numeric_features: torch.Tensor) -> torch.Tensor:
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        cls = outputs.last_hidden_state[:, 0, :]
        return self.forward_from_embedding(cls, numeric_features)

    def forward_from_embedding(self, text_embedding: torch.Tensor, numeric_features: torch.Tensor) -> torch.Tensor:
        fused = torch.cat([text_embedding, numeric_features], dim=1)
        logits = self.classifier(fused).squeeze(1)
        return logits


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

        numeric = pd.to_numeric(df[col], errors="coerce")
        if float(numeric.notna().mean()) >= NUMERIC_VALID_RATIO:
            numeric_cols.append(col)

    if not numeric_cols:
        raise ValueError("No numeric feature columns detected after exclusions.")

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

    numeric_cols = detect_numeric_feature_columns(df)

    medians: Dict[str, float] = {}
    for col in numeric_cols:
        x = pd.to_numeric(df[col], errors="coerce")
        med = x.median(skipna=True)
        if pd.isna(med):
            med = 0.0
        medians[col] = float(med)
        df[col] = x.fillna(med).astype(float)

    summary = {
        "rows": int(len(df)),
        "label_counts": {int(k): int(v) for k, v in df["label"].value_counts().sort_index().items()},
        "source_counts": {str(k): int(v) for k, v in df["source"].value_counts().sort_index().items()},
        "numeric_feature_count": len(numeric_cols),
        "numeric_features": list(numeric_cols),
    }
    return df, numeric_cols, medians, summary


def build_splits(df: pd.DataFrame, seed: int, test_size: float) -> Dict[str, Dict[str, Any]]:
    splits: Dict[str, Dict[str, Any]] = {}

    tr, te = train_test_split(
        df,
        test_size=test_size,
        random_state=seed,
        stratify=df["label"],
    )
    tr = tr.reset_index(drop=True)
    te = te.reset_index(drop=True)
    splits["random"] = {
        "name": "Random Stratified Split",
        "train_df": tr,
        "test_df": te,
    }

    for cfg in SPLITS:
        if cfg.key == "random":
            continue
        train_df = df[df["source"].isin(cfg.train_sources)].reset_index(drop=True)
        test_df = df[df["source"] == cfg.test_source].reset_index(drop=True)
        splits[cfg.key] = {
            "name": cfg.name,
            "train_df": train_df,
            "test_df": test_df,
        }

    annotate_split_validity(splits)
    return splits


def annotate_split_validity(splits: Dict[str, Dict[str, Any]]) -> None:
    for _, info in splits.items():
        train_df = info["train_df"]
        test_df = info["test_df"]
        train_counts = {int(k): int(v) for k, v in train_df["label"].value_counts().sort_index().items()}
        test_counts = {int(k): int(v) for k, v in test_df["label"].value_counts().sort_index().items()}
        info["train_label_counts"] = train_counts
        info["test_label_counts"] = test_counts
        info["valid_for_phishing_metrics"] = len(test_counts.keys()) > 1
        info["validity_note"] = (
            "valid"
            if info["valid_for_phishing_metrics"]
            else "invalid_single_class_test_set"
        )


def downsample_rows(df: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
    if max_rows <= 0 or len(df) <= max_rows:
        return df.reset_index(drop=True)
    if int(df["label"].nunique()) < 2:
        return df.sample(n=max_rows, random_state=seed).reset_index(drop=True)
    sampled, _ = train_test_split(
        df,
        train_size=max_rows,
        random_state=seed,
        stratify=df["label"],
    )
    return sampled.reset_index(drop=True)


def apply_split_row_caps(
    splits: Dict[str, Dict[str, Any]],
    max_train_rows: int,
    max_test_rows: int,
    seed: int,
) -> Dict[str, Dict[str, Any]]:
    if max_train_rows <= 0 and max_test_rows <= 0:
        annotate_split_validity(splits)
        return splits

    for key, info in splits.items():
        info_seed = seed + sum(ord(ch) for ch in key)
        info["train_df"] = downsample_rows(info["train_df"], max_train_rows, info_seed)
        info["test_df"] = downsample_rows(info["test_df"], max_test_rows, info_seed + 1)
    annotate_split_validity(splits)
    return splits


def tokenize_texts(tokenizer, texts: Sequence[str], max_length: int) -> Dict[str, torch.Tensor]:
    enc = tokenizer(
        list(texts),
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="pt",
    )
    return {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"]}


def make_numeric_matrices(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    numeric_cols: Sequence[str],
    use_numeric: bool,
) -> Tuple[np.ndarray, np.ndarray, Optional[StandardScaler], int]:
    if not use_numeric:
        return (
            np.zeros((len(train_df), 0), dtype=np.float32),
            np.zeros((len(test_df), 0), dtype=np.float32),
            None,
            0,
        )

    scaler = StandardScaler()
    train_num = scaler.fit_transform(train_df[list(numeric_cols)].values).astype(np.float32)
    test_num = scaler.transform(test_df[list(numeric_cols)].values).astype(np.float32)
    return train_num, test_num, scaler, train_num.shape[1]


def extract_embeddings(
    encoder: nn.Module,
    tokenized: Dict[str, torch.Tensor],
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    encoder.eval()
    out: List[np.ndarray] = []
    input_ids = tokenized["input_ids"]
    attention_mask = tokenized["attention_mask"]
    total_batches = int((input_ids.shape[0] + batch_size - 1) / batch_size)
    with torch.no_grad():
        for i in range(0, input_ids.shape[0], batch_size):
            ids = input_ids[i : i + batch_size].to(device)
            mask = attention_mask[i : i + batch_size].to(device)
            outputs = encoder(input_ids=ids, attention_mask=mask)
            cls = outputs.last_hidden_state[:, 0, :].detach().cpu().numpy()
            out.append(cls)
            batch_idx = int(i / batch_size) + 1
            if total_batches >= 10 and (batch_idx % 25 == 0 or batch_idx == total_batches):
                print(f"    embedding batch {batch_idx}/{total_batches}")
    if not out:
        return np.zeros((0, 768), dtype=np.float32)
    return np.vstack(out).astype(np.float32)


def compute_pos_weight(y_train: np.ndarray, device: torch.device) -> torch.Tensor:
    pos = float((y_train == 1).sum())
    neg = float((y_train == 0).sum())
    if pos <= 0:
        return torch.tensor(1.0, dtype=torch.float32, device=device)
    return torch.tensor(max(1.0, neg / pos), dtype=torch.float32, device=device)


def train_frozen_head(
    model: DistilBertFusionModel,
    train_embeddings: np.ndarray,
    train_numeric: np.ndarray,
    y_train: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    device: torch.device,
) -> List[float]:
    ds = EmbeddingFusionDataset(train_embeddings, train_numeric, y_train)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)

    pos_weight = compute_pos_weight(y_train, device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=lr)

    losses: List[float] = []
    for epoch in range(1, epochs + 1):
        model.classifier.train()
        total = 0.0
        for batch in loader:
            text_emb = batch["text_embedding"].to(device)
            num = batch["numeric_features"].to(device)
            y = batch["label"].to(device)

            optimizer.zero_grad()
            logits = model.forward_from_embedding(text_emb, num)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.classifier.parameters(), 1.0)
            optimizer.step()
            total += float(loss.item())

        avg = total / max(1, len(loader))
        losses.append(avg)
        print(f"    epoch {epoch}/{epochs} - loss={avg:.4f}")

    return losses


def predict_frozen_head(
    model: DistilBertFusionModel,
    test_embeddings: np.ndarray,
    test_numeric: np.ndarray,
    y_test: np.ndarray,
    batch_size: int,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray]:
    ds = EmbeddingFusionDataset(test_embeddings, test_numeric, y_test)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False)

    probs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    model.classifier.eval()
    with torch.no_grad():
        for batch in loader:
            text_emb = batch["text_embedding"].to(device)
            num = batch["numeric_features"].to(device)
            y = batch["label"].detach().cpu().numpy()
            logits = model.forward_from_embedding(text_emb, num)
            p = torch.sigmoid(logits).detach().cpu().numpy()
            probs.append(p)
            ys.append(y)

    return np.concatenate(probs), np.concatenate(ys)


def train_unfrozen(
    model: DistilBertFusionModel,
    tokenized_train: Dict[str, torch.Tensor],
    tokenized_test: Dict[str, torch.Tensor],
    train_numeric: np.ndarray,
    test_numeric: np.ndarray,
    y_train: np.ndarray,
    y_test: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    device: torch.device,
    max_batches_per_epoch: Optional[int],
) -> Tuple[List[float], np.ndarray, np.ndarray]:
    train_ds = TokenizedFusionDataset(
        input_ids=tokenized_train["input_ids"],
        attention_mask=tokenized_train["attention_mask"],
        numeric_features=train_numeric,
        labels=y_train,
    )
    test_ds = TokenizedFusionDataset(
        input_ids=tokenized_test["input_ids"],
        attention_mask=tokenized_test["attention_mask"],
        numeric_features=test_numeric,
        labels=y_test,
    )

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    pos_weight = compute_pos_weight(y_train, device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)

    losses: List[float] = []
    for epoch in range(1, epochs + 1):
        model.train()
        total = 0.0
        for step_idx, batch in enumerate(train_loader, start=1):
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            num = batch["numeric_features"].to(device)
            y = batch["label"].to(device)

            optimizer.zero_grad()
            logits = model(ids, mask, num)
            loss = criterion(logits, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total += float(loss.item())
            if max_batches_per_epoch is not None and step_idx >= max_batches_per_epoch:
                break

        denom = min(len(train_loader), max_batches_per_epoch) if max_batches_per_epoch else len(train_loader)
        avg = total / max(1, denom)
        losses.append(avg)
        print(f"    epoch {epoch}/{epochs} - loss={avg:.4f}")

    model.eval()
    probs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    with torch.no_grad():
        for batch in test_loader:
            ids = batch["input_ids"].to(device)
            mask = batch["attention_mask"].to(device)
            num = batch["numeric_features"].to(device)
            y = batch["label"].detach().cpu().numpy()
            logits = model(ids, mask, num)
            p = torch.sigmoid(logits).detach().cpu().numpy()
            probs.append(p)
            ys.append(y)

    return losses, np.concatenate(probs), np.concatenate(ys)


def compute_metrics(y_true: np.ndarray, probs: np.ndarray, threshold: float = 0.5) -> Dict[str, Any]:
    preds = (probs >= threshold).astype(int)
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()

    result: Dict[str, Any] = {
        "accuracy": float(accuracy_score(y_true, preds)),
        "precision": float(precision_score(y_true, preds, zero_division=0)),
        "recall": float(recall_score(y_true, preds, zero_division=0)),
        "f1": float(f1_score(y_true, preds, zero_division=0)),
        "confusion_matrix": cm.tolist(),
        "false_positives": int(fp),
        "false_negatives": int(fn),
    }

    if len(np.unique(y_true)) > 1:
        result["roc_auc"] = float(roc_auc_score(y_true, probs))
        pos = probs[y_true == 1]
        neg = probs[y_true == 0]
        result["mean_prob_pos"] = float(pos.mean()) if len(pos) else None
        result["mean_prob_neg"] = float(neg.mean()) if len(neg) else None
    else:
        result["roc_auc"] = None
        result["mean_prob_pos"] = None
        result["mean_prob_neg"] = float(probs.mean()) if len(probs) else None

    return result


def compute_threshold_rows(y_true: np.ndarray, probs: np.ndarray) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for thr in THRESHOLDS:
        m = compute_metrics(y_true, probs, threshold=thr)
        rows.append(
            {
                "threshold": float(thr),
                "precision": m["precision"],
                "recall": m["recall"],
                "f1": m["f1"],
                "false_positives": m["false_positives"],
                "false_negatives": m["false_negatives"],
            }
        )
    return rows


def run_variant_on_split(
    variant: VariantConfig,
    split_key: str,
    split_info: Dict[str, Any],
    numeric_cols: Sequence[str],
    tokenizer,
    model_name: str,
    max_length: int,
    batch_size: int,
    lr: float,
    device: torch.device,
    frozen_encoder_cache: Optional[AutoModel],
    max_unfrozen_batches_per_epoch: Optional[int],
) -> Dict[str, Any]:
    train_df = split_info["train_df"]
    test_df = split_info["test_df"]

    if not split_info["valid_for_phishing_metrics"]:
        return {
            "status": "invalid_split",
            "note": "Test split has one class only; phishing-class metrics are not comparable.",
            "train_size": int(len(train_df)),
            "test_size": int(len(test_df)),
            "train_label_counts": split_info["train_label_counts"],
            "test_label_counts": split_info["test_label_counts"],
            "metrics": None,
            "thresholds": [],
            "epochs_used": variant.epochs,
        }

    start = time.time()
    print(f"\n[{split_key}] variant={variant.name} (freeze={variant.freeze_encoder}, use_numeric={variant.use_numeric})")

    tokenized_train = tokenize_texts(tokenizer, train_df["text"].tolist(), max_length)
    tokenized_test = tokenize_texts(tokenizer, test_df["text"].tolist(), max_length)

    train_numeric, test_numeric, scaler, num_numeric = make_numeric_matrices(
        train_df=train_df,
        test_df=test_df,
        numeric_cols=numeric_cols,
        use_numeric=variant.use_numeric,
    )

    y_train = train_df["label"].astype(int).to_numpy()
    y_test = test_df["label"].astype(int).to_numpy()

    model = DistilBertFusionModel(model_name=model_name, num_numeric_features=num_numeric)
    model.to(device)

    if variant.freeze_encoder:
        if frozen_encoder_cache is None:
            raise RuntimeError("Frozen encoder cache is required for frozen variants.")
        model.encoder = frozen_encoder_cache
        for p in model.encoder.parameters():
            p.requires_grad = False

        print("  extracting frozen CLS embeddings...")
        train_emb = extract_embeddings(model.encoder, tokenized_train, device, batch_size)
        test_emb = extract_embeddings(model.encoder, tokenized_test, device, batch_size)

        losses = train_frozen_head(
            model=model,
            train_embeddings=train_emb,
            train_numeric=train_numeric,
            y_train=y_train,
            epochs=variant.epochs,
            batch_size=batch_size,
            lr=lr,
            device=device,
        )
        probs, y_true = predict_frozen_head(
            model=model,
            test_embeddings=test_emb,
            test_numeric=test_numeric,
            y_test=y_test,
            batch_size=batch_size,
            device=device,
        )
    else:
        losses, probs, y_true = train_unfrozen(
            model=model,
            tokenized_train=tokenized_train,
            tokenized_test=tokenized_test,
            train_numeric=train_numeric,
            test_numeric=test_numeric,
            y_train=y_train,
            y_test=y_test,
            epochs=variant.epochs,
            batch_size=batch_size,
            lr=lr,
            device=device,
            max_batches_per_epoch=max_unfrozen_batches_per_epoch,
        )

    metrics = compute_metrics(y_true, probs, threshold=0.5)
    thresh = compute_threshold_rows(y_true, probs)

    elapsed = time.time() - start
    return {
        "status": "ok",
        "note": "",
        "train_size": int(len(train_df)),
        "test_size": int(len(test_df)),
        "train_label_counts": split_info["train_label_counts"],
        "test_label_counts": split_info["test_label_counts"],
        "metrics": metrics,
        "thresholds": thresh,
        "epochs_used": variant.epochs,
        "runtime_seconds": elapsed,
        "train_losses": losses,
        "scaler_used": scaler is not None,
    }


def write_metrics_csv(path: str, results: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = [
        "variant",
        "split",
        "status",
        "train_size",
        "test_size",
        "train_label_counts",
        "test_label_counts",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "mean_prob_pos",
        "mean_prob_neg",
        "confusion_matrix",
        "runtime_seconds",
        "note",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for variant, split_map in results.items():
            for split_key, r in split_map.items():
                m = r.get("metrics") or {}
                writer.writerow(
                    {
                        "variant": variant,
                        "split": split_key,
                        "status": r.get("status"),
                        "train_size": r.get("train_size"),
                        "test_size": r.get("test_size"),
                        "train_label_counts": json.dumps(r.get("train_label_counts", {}), ensure_ascii=False),
                        "test_label_counts": json.dumps(r.get("test_label_counts", {}), ensure_ascii=False),
                        "accuracy": m.get("accuracy"),
                        "precision": m.get("precision"),
                        "recall": m.get("recall"),
                        "f1": m.get("f1"),
                        "roc_auc": m.get("roc_auc"),
                        "mean_prob_pos": m.get("mean_prob_pos"),
                        "mean_prob_neg": m.get("mean_prob_neg"),
                        "confusion_matrix": json.dumps(m.get("confusion_matrix")) if m else "",
                        "runtime_seconds": r.get("runtime_seconds"),
                        "note": r.get("note", ""),
                    }
                )


def write_thresholds_csv(path: str, results: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fields = ["variant", "split", "threshold", "precision", "recall", "f1", "false_positives", "false_negatives"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for variant, split_map in results.items():
            for split_key, r in split_map.items():
                for row in r.get("thresholds", []):
                    writer.writerow(
                        {
                            "variant": variant,
                            "split": split_key,
                            "threshold": row["threshold"],
                            "precision": row["precision"],
                            "recall": row["recall"],
                            "f1": row["f1"],
                            "false_positives": row["false_positives"],
                            "false_negatives": row["false_negatives"],
                        }
                    )


def best_variant(results: Dict[str, Dict[str, Dict[str, Any]]], split_key: str) -> Optional[Tuple[str, float]]:
    best: Optional[Tuple[str, float]] = None
    for variant in results:
        r = results[variant].get(split_key)
        if not r or r.get("status") != "ok":
            continue
        f1 = r["metrics"]["f1"]
        if best is None or f1 > best[1]:
            best = (variant, f1)
    return best


def compare_pairs(results: Dict[str, Dict[str, Dict[str, Any]]], split_keys: Sequence[str]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def avg_delta(v1: str, v2: str, metric: str) -> Optional[float]:
        deltas = []
        for sk in split_keys:
            r1 = results[v1].get(sk)
            r2 = results[v2].get(sk)
            if not r1 or not r2 or r1.get("status") != "ok" or r2.get("status") != "ok":
                continue
            deltas.append(r1["metrics"][metric] - r2["metrics"][metric])
        if not deltas:
            return None
        return float(np.mean(deltas))

    out["fusion_vs_text_frozen_f1"] = avg_delta("fusion_frozen", "textonly_frozen", "f1")
    out["fusion_vs_text_unfrozen_f1"] = avg_delta("fusion_unfrozen", "textonly_unfrozen", "f1")
    out["unfrozen_vs_frozen_fusion_f1"] = avg_delta("fusion_unfrozen", "fusion_frozen", "f1")
    out["unfrozen_vs_frozen_textonly_f1"] = avg_delta("textonly_unfrozen", "textonly_frozen", "f1")
    out["unfrozen_vs_frozen_fusion_recall"] = avg_delta("fusion_unfrozen", "fusion_frozen", "recall")
    out["unfrozen_vs_frozen_text_recall"] = avg_delta("textonly_unfrozen", "textonly_frozen", "recall")
    return out


def answer_research_questions(
    results: Dict[str, Dict[str, Dict[str, Any]]],
    split_validity: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    qa: Dict[str, str] = {}
    core_splits = ["cross_source_a", "cross_source_b"]
    cmp = compare_pairs(results, core_splits)

    q1_delta = cmp.get("unfrozen_vs_frozen_fusion_f1")
    if q1_delta is None:
        qa["Q1"] = "Insufficient valid results to compare freeze vs unfreeze on cross-source A/B."
    elif q1_delta > 0.01:
        qa["Q1"] = f"Unfreezing improved fusion F1 on A/B by {q1_delta:+.4f} on average, suggesting extra cost may be justified when robustness is critical."
    elif q1_delta < -0.01:
        qa["Q1"] = f"Unfreezing reduced fusion F1 on A/B by {q1_delta:+.4f} on average, so extra cost was not justified under current setup."
    else:
        qa["Q1"] = f"Unfreezing had marginal effect on fusion F1 on A/B (avg delta {q1_delta:+.4f}); cost/benefit is weak."

    q2_delta_f = cmp.get("fusion_vs_text_frozen_f1")
    q2_delta_u = cmp.get("fusion_vs_text_unfrozen_f1")
    if q2_delta_f is None and q2_delta_u is None:
        qa["Q2"] = "Could not quantify fusion value due to missing comparable runs."
    else:
        observed = [x for x in [q2_delta_f, q2_delta_u] if x is not None]
        if observed and all(x > 0.01 for x in observed):
            q2_note = "Numeric fusion improved cross-source F1 versus text-only."
        elif observed and all(x < -0.01 for x in observed):
            q2_note = "Numeric fusion reduced cross-source F1 versus text-only under this setup."
        else:
            q2_note = "Fusion impact was mixed or marginal across freeze settings."
        qa["Q2"] = (
            f"Fusion minus text-only F1 on A/B: frozen={q2_delta_f:+.4f} if available, "
            f"unfrozen={q2_delta_u:+.4f} if available. {q2_note}"
        )

    best_random = best_variant(results, "random")
    qa["Q3"] = (
        f"Best random split variant by F1: {best_random[0]} ({best_random[1]:.4f})."
        if best_random
        else "Best random split variant could not be determined."
    )

    best_a = best_variant(results, "cross_source_a")
    best_b = best_variant(results, "cross_source_b")
    qa["Q4"] = (
        f"Best on A: {best_a[0]} ({best_a[1]:.4f}); best on B: {best_b[0]} ({best_b[1]:.4f})."
        if best_a and best_b
        else "Could not determine best variant on A/B."
    )

    # Q5: ranking vs threshold behavior
    notes = []
    for split_key in ["cross_source_a", "cross_source_b"]:
        best = best_variant(results, split_key)
        if not best:
            continue
        variant = best[0]
        r = results[variant][split_key]
        roc = r["metrics"].get("roc_auc")
        thr_rows = r.get("thresholds", [])
        if roc is not None and thr_rows:
            f1_low = next((x["f1"] for x in thr_rows if abs(x["threshold"] - 0.2) < 1e-9), None)
            f1_mid = next((x["f1"] for x in thr_rows if abs(x["threshold"] - 0.5) < 1e-9), None)
            f1_high = next((x["f1"] for x in thr_rows if abs(x["threshold"] - 0.8) < 1e-9), None)
            notes.append(
                f"{split_key}: ROC-AUC={roc:.4f}, F1@0.2={f1_low:.4f}, F1@0.5={f1_mid:.4f}, F1@0.8={f1_high:.4f}"
            )
    qa["Q5"] = (
        "Threshold behavior remains a major driver where ROC-AUC is high but decision metrics vary strongly: "
        + "; ".join(notes)
        if notes
        else "Insufficient data to compare ranking quality vs threshold sensitivity."
    )

    c_valid = split_validity["cross_source_c"]["valid_for_phishing_metrics"]
    qa["Q6"] = (
        "Cross-source C is not a valid phishing generalization benchmark in current form because the test set is single-class (label 0 only)."
        if not c_valid
        else "Cross-source C appears valid with both classes present."
    )

    # Q7 recommendation seed
    qa["Q7"] = (
        "Next direction: fix evaluation by creating a label-balanced held-out benchmark for Enron-like domains, "
        "then optimize threshold-calibrated fusion (possibly temperature scaling + source-aware calibration)."
    )
    return qa


def write_markdown_report(
    path: str,
    dataset_summary: Dict[str, Any],
    split_info: Dict[str, Dict[str, Any]],
    results: Dict[str, Dict[str, Dict[str, Any]]],
    variants: Sequence[VariantConfig],
    answers: Dict[str, str],
    total_runtime: float,
    max_unfrozen_batches_per_epoch: Optional[int],
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)

    lines: List[str] = []
    lines.append("# Email Transformer Ablation Report (TG-5.9)")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    lines.append("## 1. Overview")
    lines.append("- Purpose: isolate contributions of transformer context, numeric fusion, freeze/unfreeze behavior, and threshold choice.")
    lines.append("- Compared variants: fusion_frozen, fusion_unfrozen, textonly_frozen, textonly_unfrozen.")
    lines.append("")

    lines.append("## 2. Dataset and Split Validity")
    lines.append(f"- Rows: {dataset_summary['rows']:,}")
    lines.append(f"- Label distribution: {dataset_summary['label_counts']}")
    lines.append(f"- Source distribution: {dataset_summary['source_counts']}")
    lines.append(f"- Numeric feature count: {dataset_summary['numeric_feature_count']}")
    lines.append("")
    lines.append("| Split | Train Label Counts | Test Label Counts | Valid For Phishing Metrics | Note |")
    lines.append("|---|---|---|---|---|")
    for sk, info in split_info.items():
        lines.append(
            f"| {sk} | `{info['train_label_counts']}` | `{info['test_label_counts']}` | {info['valid_for_phishing_metrics']} | {info['validity_note']} |"
        )
    lines.append("")

    lines.append("## 3. Variant Configuration")
    lines.append("| Variant | Uses Numeric Features | Encoder Frozen | Epochs |")
    lines.append("|---|---|---|---:|")
    for v in variants:
        lines.append(f"| {v.name} | {v.use_numeric} | {v.freeze_encoder} | {v.epochs} |")
    if max_unfrozen_batches_per_epoch is not None:
        lines.append(f"- Unfrozen training cap: max {max_unfrozen_batches_per_epoch} batches per epoch (CPU practicality constraint).")
    lines.append("")

    lines.append("## 4. Main Metrics (Threshold=0.5)")
    lines.append("| Variant | Split | Status | Accuracy | Precision | Recall | F1 | ROC-AUC |")
    lines.append("|---|---|---|---:|---:|---:|---:|---:|")
    for v in variants:
        for sk in split_info.keys():
            r = results[v.name][sk]
            if r["status"] != "ok":
                lines.append(f"| {v.name} | {sk} | {r['status']} | n/a | n/a | n/a | n/a | n/a |")
            else:
                m = r["metrics"]
                roc = "n/a" if m["roc_auc"] is None else f"{m['roc_auc']:.4f}"
                lines.append(
                    f"| {v.name} | {sk} | ok | {m['accuracy']:.4f} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {roc} |"
                )
    lines.append("")

    lines.append("## 5. Threshold Comparison (0.2 / 0.5 / 0.8)")
    for focus_split in ["cross_source_a", "cross_source_b"]:
        lines.append(f"### {focus_split}")
        lines.append("| Variant | Threshold | Precision | Recall | F1 |")
        lines.append("|---|---:|---:|---:|---:|")
        for v in variants:
            r = results[v.name][focus_split]
            if r["status"] != "ok":
                continue
            for row in r["thresholds"]:
                lines.append(
                    f"| {v.name} | {row['threshold']:.1f} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |"
                )
        lines.append("")

    lines.append("## 6. Fusion Value Analysis")
    lines.append("- Compare fusion vs text-only under same freeze setting using A/B results.")
    for freeze_state, a, b in [
        ("frozen", "fusion_frozen", "textonly_frozen"),
        ("unfrozen", "fusion_unfrozen", "textonly_unfrozen"),
    ]:
        deltas = []
        for sk in ["cross_source_a", "cross_source_b"]:
            ra = results[a][sk]
            rb = results[b][sk]
            if ra["status"] == "ok" and rb["status"] == "ok":
                deltas.append(ra["metrics"]["f1"] - rb["metrics"]["f1"])
        if deltas:
            lines.append(f"- {freeze_state}: mean F1 delta (fusion - text-only) on A/B = {np.mean(deltas):+.4f}")
        else:
            lines.append(f"- {freeze_state}: insufficient comparable runs")
    lines.append("")

    lines.append("## 7. Freeze vs Unfreeze Analysis")
    lines.append("- Compare unfrozen vs frozen under same input mode (A/B).")
    for mode, u, f in [
        ("fusion", "fusion_unfrozen", "fusion_frozen"),
        ("text-only", "textonly_unfrozen", "textonly_frozen"),
    ]:
        deltas = []
        for sk in ["cross_source_a", "cross_source_b"]:
            ru = results[u][sk]
            rf = results[f][sk]
            if ru["status"] == "ok" and rf["status"] == "ok":
                deltas.append(ru["metrics"]["f1"] - rf["metrics"]["f1"])
        if deltas:
            lines.append(f"- {mode}: mean F1 delta (unfrozen - frozen) on A/B = {np.mean(deltas):+.4f}")
        else:
            lines.append(f"- {mode}: insufficient comparable runs")
    lines.append("")

    lines.append("## 8. Invalid Benchmark Analysis")
    if not split_info["cross_source_c"]["valid_for_phishing_metrics"]:
        lines.append("- Cross-source C is limited/invalid for phishing generalization because its test set contains a single class only.")
        lines.append("- Phishing-class precision/recall/F1/ROC-AUC are not comparable there.")
        lines.append("- Recommended fix: construct a held-out Enron-like test set with both legitimate and phishing labels.")
    else:
        lines.append("- Cross-source C contains both classes and is comparable.")
    lines.append("")

    lines.append("## 9. Key Findings (Research Questions)")
    for q in ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]:
        lines.append(f"- **{q}**: {answers[q]}")
    lines.append("")

    lines.append("## 10. Recommended Next TG")
    lines.append("- Build a repaired cross-source benchmark with valid class balance for C-like evaluation.")
    lines.append("- Add probability calibration per-source and re-run threshold policy analysis.")
    lines.append("- Consider lightweight domain-adaptation regularization before larger model changes.")
    lines.append("")
    lines.append(f"Total runtime: {total_runtime:.1f} seconds")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="TG-5.9 transformer ablation analysis")
    parser.add_argument("--data", type=str, default=DATA_CSV)
    parser.add_argument("--model-name", type=str, default=MODEL_NAME)
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    parser.add_argument("--frozen-epochs", type=int, default=FROZEN_EPOCHS)
    parser.add_argument("--unfrozen-epochs", type=int, default=UNFROZEN_EPOCHS)
    parser.add_argument(
        "--max-unfrozen-batches-per-epoch",
        type=int,
        default=30,
        help="Cap training batches per epoch for unfrozen variants (CPU practicality). Use 0 for no cap.",
    )
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--test-size", type=float, default=TEST_SIZE)
    parser.add_argument(
        "--max-train-rows-per-split",
        type=int,
        default=0,
        help="Optional deterministic cap on train rows per split for faster CPU runs. 0 disables cap.",
    )
    parser.add_argument(
        "--max-test-rows-per-split",
        type=int,
        default=0,
        help="Optional deterministic cap on test rows per split for faster CPU runs. 0 disables cap.",
    )
    args = parser.parse_args()
    max_unfrozen_batches = None if int(args.max_unfrozen_batches_per_epoch) <= 0 else int(args.max_unfrozen_batches_per_epoch)

    started = time.time()
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    df, numeric_cols, medians, dataset_summary = load_dataset(args.data)
    splits = build_splits(df, seed=args.seed, test_size=args.test_size)
    splits = apply_split_row_caps(
        splits=splits,
        max_train_rows=max(0, int(args.max_train_rows_per_split)),
        max_test_rows=max(0, int(args.max_test_rows_per_split)),
        seed=args.seed,
    )

    print(f"Dataset rows: {dataset_summary['rows']:,}")
    print(f"Numeric columns ({len(numeric_cols)}): {numeric_cols}")
    if int(args.max_train_rows_per_split) > 0 or int(args.max_test_rows_per_split) > 0:
        print(
            "Row caps active: "
            f"max_train_rows_per_split={int(args.max_train_rows_per_split)} "
            f"max_test_rows_per_split={int(args.max_test_rows_per_split)}"
        )
    for sk, info in splits.items():
        print(f"Split {sk}: train={len(info['train_df'])} test={len(info['test_df'])} valid={info['valid_for_phishing_metrics']}")

    variants = [
        VariantConfig("fusion_frozen", True, True, args.frozen_epochs),
        VariantConfig("fusion_unfrozen", True, False, args.unfrozen_epochs),
        VariantConfig("textonly_frozen", False, True, args.frozen_epochs),
        VariantConfig("textonly_unfrozen", False, False, args.unfrozen_epochs),
    ]

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    frozen_encoder = AutoModel.from_pretrained(args.model_name)
    frozen_encoder.to(device)
    frozen_encoder.eval()

    results: Dict[str, Dict[str, Dict[str, Any]]] = {v.name: {} for v in variants}

    # Evaluate split-by-split so tokenization/embeddings can be reused within each split.
    for sk, split_info in splits.items():
        print(f"\n=== Running split: {sk} ({split_info['name']}) ===")
        for v in variants:
            results[v.name][sk] = run_variant_on_split(
                variant=v,
                split_key=sk,
                split_info=split_info,
                numeric_cols=numeric_cols,
                tokenizer=tokenizer,
                model_name=args.model_name,
                max_length=args.max_length,
                batch_size=args.batch_size,
                lr=args.learning_rate,
                device=device,
                frozen_encoder_cache=frozen_encoder if v.freeze_encoder else None,
                max_unfrozen_batches_per_epoch=max_unfrozen_batches,
            )

    total_runtime = time.time() - started

    write_metrics_csv(OUT_METRICS_CSV, results)
    write_thresholds_csv(OUT_THRESH_CSV, results)
    answers = answer_research_questions(results, splits)
    write_markdown_report(
        path=OUT_MD,
        dataset_summary=dataset_summary,
        split_info=splits,
        results=results,
        variants=variants,
        answers=answers,
        total_runtime=total_runtime,
        max_unfrozen_batches_per_epoch=max_unfrozen_batches,
    )

    print("\n=== TG-5.9 Complete ===")
    for sk in ["random", "cross_source_a", "cross_source_b", "cross_source_c"]:
        best = best_variant(results, sk)
        if best:
            print(f"Best {sk}: {best[0]} (F1={best[1]:.4f})")
        else:
            print(f"Best {sk}: n/a")
    print(f"Saved markdown: {os.path.relpath(OUT_MD, ROOT)}")
    print(f"Saved metrics csv: {os.path.relpath(OUT_METRICS_CSV, ROOT)}")
    print(f"Saved thresholds csv: {os.path.relpath(OUT_THRESH_CSV, ROOT)}")
    print(f"Total runtime: {total_runtime:.1f}s")


if __name__ == "__main__":
    main()
