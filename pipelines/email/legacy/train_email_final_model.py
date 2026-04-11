#!/usr/bin/env python3
"""TG-6.0 final email model training, packaging, and reporting.

Final selected model:
- DistilBERT text-only
- Frozen encoder
- Head-only training
"""

from __future__ import annotations

import argparse
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
from torch import nn
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModel, AutoTokenizer


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_CSV = os.path.join(ROOT, "data", "processed", "email_dataset_v2_features.csv")

MODEL_OUT = os.path.join(ROOT, "models", "email_final_model.pt")
TOKENIZER_OUT = os.path.join(ROOT, "models", "email_final_tokenizer")
META_OUT = os.path.join(ROOT, "models", "email_final_metadata.json")

THRESH_REPORT_OUT = os.path.join(ROOT, "reports", "email_final_thresholds.md")
FINAL_REPORT_OUT = os.path.join(ROOT, "reports", "email_final_model_report.md")
ABLATION_METRICS_CSV = os.path.join(ROOT, "reports", "email_transformer_ablation_metrics.csv")

MODEL_NAME = "distilbert-base-uncased"
MAX_LENGTH = 256
BATCH_SIZE = 16
EPOCHS = 3
LEARNING_RATE = 2e-5
RANDOM_SEED = 1337
TEST_SIZE = 0.2
THRESHOLDS = [0.2, 0.5, 0.8]

LABEL_MAP = {
    0: "legitimate",
    1: "suspicious/phishing-like",
}


@dataclass
class SplitResult:
    split_name: str
    train_size: int
    test_size: int
    train_label_counts: Dict[int, int]
    test_label_counts: Dict[int, int]
    metrics_05: Dict[str, Any]
    thresholds: List[Dict[str, Any]]
    losses: List[float]
    model: Optional["DistilBertTextOnlyModel"] = None


class EmbeddingTextDataset(Dataset):
    def __init__(self, text_embeddings: np.ndarray, labels: Sequence[int]) -> None:
        self.text_embeddings = torch.tensor(text_embeddings, dtype=torch.float32)
        self.labels = torch.tensor(np.asarray(labels, dtype=np.float32), dtype=torch.float32)

    def __len__(self) -> int:
        return int(self.labels.shape[0])

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        return {
            "text_embedding": self.text_embeddings[idx],
            "label": self.labels[idx],
        }


class DistilBertTextOnlyModel(nn.Module):
    def __init__(self, model_name: str) -> None:
        super().__init__()
        self.encoder = AutoModel.from_pretrained(model_name)
        text_dim = int(self.encoder.config.hidden_size)
        self.classifier = nn.Sequential(
            nn.Linear(text_dim, 256),
            nn.ReLU(),
            nn.Dropout(0.3),
            nn.Linear(256, 1),
        )

    def forward_from_embedding(self, text_embedding: torch.Tensor) -> torch.Tensor:
        return self.classifier(text_embedding).squeeze(1)


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


def load_dataset(path: str) -> pd.DataFrame:
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
    df = df[df["text"].str.len() > 0].reset_index(drop=True)
    return df


def tokenize_texts(tokenizer, texts: Sequence[str], max_length: int) -> Dict[str, torch.Tensor]:
    enc = tokenizer(
        list(texts),
        truncation=True,
        padding="max_length",
        max_length=max_length,
        return_tensors="pt",
    )
    return {"input_ids": enc["input_ids"], "attention_mask": enc["attention_mask"]}


def extract_cls_embeddings(
    encoder: nn.Module,
    tokenized: Dict[str, torch.Tensor],
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    encoder.eval()
    input_ids = tokenized["input_ids"]
    attention_mask = tokenized["attention_mask"]
    chunks: List[np.ndarray] = []
    total_batches = int((input_ids.shape[0] + batch_size - 1) / batch_size)
    with torch.no_grad():
        for i in range(0, input_ids.shape[0], batch_size):
            ids = input_ids[i : i + batch_size].to(device)
            mask = attention_mask[i : i + batch_size].to(device)
            outputs = encoder(input_ids=ids, attention_mask=mask)
            cls = outputs.last_hidden_state[:, 0, :].detach().cpu().numpy()
            chunks.append(cls)
            batch_idx = int(i / batch_size) + 1
            if total_batches >= 10 and (batch_idx % 50 == 0 or batch_idx == total_batches):
                print(f"    embedding batch {batch_idx}/{total_batches}")
    if not chunks:
        hidden = int(getattr(getattr(encoder, "config", None), "hidden_size", 768))
        return np.zeros((0, hidden), dtype=np.float32)
    return np.vstack(chunks).astype(np.float32)


def compute_pos_weight(y_train: np.ndarray, device: torch.device) -> torch.Tensor:
    pos = float((y_train == 1).sum())
    neg = float((y_train == 0).sum())
    if pos <= 0:
        return torch.tensor(1.0, dtype=torch.float32, device=device)
    return torch.tensor(max(1.0, neg / pos), dtype=torch.float32, device=device)


def train_classifier_head(
    model: DistilBertTextOnlyModel,
    train_embeddings: np.ndarray,
    y_train: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    device: torch.device,
) -> List[float]:
    train_ds = EmbeddingTextDataset(train_embeddings, y_train)
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)

    pos_weight = compute_pos_weight(y_train, device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    optimizer = torch.optim.AdamW(model.classifier.parameters(), lr=lr)

    losses: List[float] = []
    for epoch in range(1, epochs + 1):
        model.classifier.train()
        total = 0.0
        for batch in train_loader:
            text_embedding = batch["text_embedding"].to(device)
            labels = batch["label"].to(device)

            optimizer.zero_grad()
            logits = model.forward_from_embedding(text_embedding)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.classifier.parameters(), 1.0)
            optimizer.step()
            total += float(loss.item())

        avg = total / max(1, len(train_loader))
        losses.append(avg)
        print(f"    epoch {epoch}/{epochs} - head_loss={avg:.4f}")
    return losses


def predict_from_embeddings(
    model: DistilBertTextOnlyModel,
    test_embeddings: np.ndarray,
    y_test: np.ndarray,
    batch_size: int,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray]:
    test_ds = EmbeddingTextDataset(test_embeddings, y_test)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)

    model.classifier.eval()
    probs: List[np.ndarray] = []
    ys: List[np.ndarray] = []
    with torch.no_grad():
        for batch in test_loader:
            text_embedding = batch["text_embedding"].to(device)
            y = batch["label"].detach().cpu().numpy()
            logits = model.forward_from_embedding(text_embedding)
            p = torch.sigmoid(logits).detach().cpu().numpy()
            probs.append(p)
            ys.append(y)

    if not probs:
        return np.array([]), np.array([])
    return np.concatenate(probs), np.concatenate(ys)


def evaluate_at_threshold(y_true: np.ndarray, probs: np.ndarray, threshold: float) -> Dict[str, Any]:
    preds = (probs >= threshold).astype(int)
    cm = confusion_matrix(y_true, preds, labels=[0, 1])
    tn, fp, fn, tp = cm.ravel()
    out: Dict[str, Any] = {
        "threshold": float(threshold),
        "accuracy": float(accuracy_score(y_true, preds)),
        "precision": float(precision_score(y_true, preds, zero_division=0)),
        "recall": float(recall_score(y_true, preds, zero_division=0)),
        "f1": float(f1_score(y_true, preds, zero_division=0)),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "confusion_matrix": cm.tolist(),
    }
    if len(np.unique(y_true)) > 1:
        out["roc_auc"] = float(roc_auc_score(y_true, probs))
    else:
        out["roc_auc"] = None
    return out


def evaluate_thresholds(y_true: np.ndarray, probs: np.ndarray) -> List[Dict[str, Any]]:
    return [evaluate_at_threshold(y_true, probs, t) for t in THRESHOLDS]


def run_textonly_frozen_split(
    split_name: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    tokenizer,
    model_name: str,
    max_length: int,
    batch_size: int,
    epochs: int,
    learning_rate: float,
    device: torch.device,
) -> SplitResult:
    print(f"\n=== {split_name} ===")
    print(f"  train={len(train_df):,} test={len(test_df):,}")
    train_labels = train_df["label"].astype(int).to_numpy()
    test_labels = test_df["label"].astype(int).to_numpy()

    model = DistilBertTextOnlyModel(model_name=model_name)
    model.to(device)
    for param in model.encoder.parameters():
        param.requires_grad = False

    tokenized_train = tokenize_texts(tokenizer, train_df["text"].tolist(), max_length)
    tokenized_test = tokenize_texts(tokenizer, test_df["text"].tolist(), max_length)

    print("  extracting train embeddings...")
    train_emb = extract_cls_embeddings(model.encoder, tokenized_train, device=device, batch_size=batch_size)
    print("  extracting test embeddings...")
    test_emb = extract_cls_embeddings(model.encoder, tokenized_test, device=device, batch_size=batch_size)

    losses = train_classifier_head(
        model=model,
        train_embeddings=train_emb,
        y_train=train_labels,
        epochs=epochs,
        batch_size=batch_size,
        lr=learning_rate,
        device=device,
    )

    probs, y_true = predict_from_embeddings(
        model=model,
        test_embeddings=test_emb,
        y_test=test_labels,
        batch_size=batch_size,
        device=device,
    )
    metrics_05 = evaluate_at_threshold(y_true, probs, 0.5)
    thresholds = evaluate_thresholds(y_true, probs)

    return SplitResult(
        split_name=split_name,
        train_size=int(len(train_df)),
        test_size=int(len(test_df)),
        train_label_counts={int(k): int(v) for k, v in train_df["label"].value_counts().sort_index().items()},
        test_label_counts={int(k): int(v) for k, v in test_df["label"].value_counts().sort_index().items()},
        metrics_05=metrics_05,
        thresholds=thresholds,
        losses=losses,
        model=model,
    )


def format_float(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{digits}f}"


def save_model_artifacts(
    model: DistilBertTextOnlyModel,
    tokenizer,
    metadata: Dict[str, Any],
) -> None:
    os.makedirs(os.path.dirname(MODEL_OUT), exist_ok=True)
    os.makedirs(TOKENIZER_OUT, exist_ok=True)

    ckpt = {
        "model_name": metadata["model_name"],
        "max_length": metadata["max_length"],
        "architecture": "distilbert_textonly_frozen",
        "classifier_state_dict": model.classifier.state_dict(),
        "label_mapping": metadata["label_mapping"],
    }
    torch.save(ckpt, MODEL_OUT)
    tokenizer.save_pretrained(TOKENIZER_OUT)
    with open(META_OUT, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)


def write_threshold_report(path: str, threshold_rows: List[Dict[str, Any]]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [
        "# Email Final Threshold Summary",
        "",
        "Selected final model: DistilBERT text-only frozen encoder.",
        "",
        "| Threshold | Precision | Recall | F1 |",
        "|---:|---:|---:|---:|",
    ]
    for row in threshold_rows:
        lines.append(
            f"| {row['threshold']:.1f} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |"
        )
    lines.extend(
        [
            "",
            "Recommendation:",
            "- low threshold (0.2-0.3) for high-recall SOC detection",
            "- high threshold (0.7-0.8) for high-confidence alerts",
        ]
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def best_variant_from_ablation(split_key: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(ABLATION_METRICS_CSV):
        return None
    df = pd.read_csv(ABLATION_METRICS_CSV)
    df = df[(df["split"] == split_key) & (df["status"] == "ok")].copy()
    if df.empty:
        return None
    df["f1"] = pd.to_numeric(df["f1"], errors="coerce")
    df = df.dropna(subset=["f1"])
    if df.empty:
        return None
    row = df.sort_values("f1", ascending=False).iloc[0]
    return {
        "variant": str(row["variant"]),
        "f1": float(row["f1"]),
        "precision": float(row["precision"]),
        "recall": float(row["recall"]),
        "roc_auc": float(row["roc_auc"]) if pd.notna(row["roc_auc"]) else None,
    }


def write_final_model_report(
    path: str,
    dataset_summary: Dict[str, Any],
    random_result: SplitResult,
    cross_a: SplitResult,
    cross_b: SplitResult,
) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    best_a = best_variant_from_ablation("cross_source_a")
    best_b = best_variant_from_ablation("cross_source_b")

    lines = [
        "# Email Final Model Report (TG-6.0)",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## 1. Model Choice Rationale",
        "- Selected model: DistilBERT text-only with frozen encoder.",
        "- Rationale: strongest robustness-cost tradeoff from TG-5.9, while numeric fusion and unfreezing did not consistently improve cross-source F1.",
        "- Operationally safer: frozen encoder is faster and more stable for repeatable packaging.",
        "",
        "## 2. Dataset Summary",
        f"- Rows: {dataset_summary['rows']:,}",
        f"- Label distribution: {dataset_summary['label_counts']}",
        f"- Source distribution: {dataset_summary['source_counts']}",
        "",
        "## 3. Random Split Metrics (Deployment Candidate)",
        f"- Train size: {random_result.train_size:,} | Test size: {random_result.test_size:,}",
        f"- Train label counts: {random_result.train_label_counts}",
        f"- Test label counts: {random_result.test_label_counts}",
        f"- Accuracy: **{format_float(random_result.metrics_05['accuracy'])}**",
        f"- Precision: **{format_float(random_result.metrics_05['precision'])}**",
        f"- Recall: **{format_float(random_result.metrics_05['recall'])}**",
        f"- F1: **{format_float(random_result.metrics_05['f1'])}**",
        f"- ROC-AUC: **{format_float(random_result.metrics_05.get('roc_auc'))}**",
        f"- Confusion matrix: `{random_result.metrics_05['confusion_matrix']}`",
        "",
        "## 4. Cross-Source A/B Results (Selected Final Model)",
        f"- A (Train Enron+Nazario, Test SpamAssassin): F1={format_float(cross_a.metrics_05['f1'])}, "
        f"Precision={format_float(cross_a.metrics_05['precision'])}, Recall={format_float(cross_a.metrics_05['recall'])}, "
        f"ROC-AUC={format_float(cross_a.metrics_05.get('roc_auc'))}",
        f"- B (Train Enron+SpamAssassin, Test Nazario): F1={format_float(cross_b.metrics_05['f1'])}, "
        f"Precision={format_float(cross_b.metrics_05['precision'])}, Recall={format_float(cross_b.metrics_05['recall'])}, "
        f"ROC-AUC={format_float(cross_b.metrics_05.get('roc_auc'))}",
        "",
        "### Reference to TG-5.9 Best Variant Logic",
    ]
    if best_a:
        lines.append(
            f"- Best variant on A (TG-5.9 run): `{best_a['variant']}` "
            f"(F1={best_a['f1']:.4f}, Precision={best_a['precision']:.4f}, Recall={best_a['recall']:.4f})."
        )
    else:
        lines.append("- Best variant on A could not be loaded from `email_transformer_ablation_metrics.csv`.")
    if best_b:
        lines.append(
            f"- Best variant on B (TG-5.9 run): `{best_b['variant']}` "
            f"(F1={best_b['f1']:.4f}, Precision={best_b['precision']:.4f}, Recall={best_b['recall']:.4f})."
        )
    else:
        lines.append("- Best variant on B could not be loaded from `email_transformer_ablation_metrics.csv`.")

    lines.extend(
        [
            "",
            "## 5. Threshold Behavior (Random Split)",
            "| Threshold | Precision | Recall | F1 |",
            "|---:|---:|---:|---:|",
        ]
    )
    for row in random_result.thresholds:
        lines.append(
            f"| {row['threshold']:.1f} | {row['precision']:.4f} | {row['recall']:.4f} | {row['f1']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## 6. Deployment Recommendation",
            "- Use this packaged frozen text-only DistilBERT as the default production candidate.",
            "- SOC/high-recall triage: threshold 0.2-0.3.",
            "- High-confidence blocking/alerting: threshold 0.7-0.8.",
            "- Keep source-held-out monitoring enabled; A/B drift remains non-trivial.",
        ]
    )

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).rstrip() + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="TG-6.0 final model training and packaging")
    parser.add_argument("--data", default=DATA_CSV)
    parser.add_argument("--model-name", default=MODEL_NAME)
    parser.add_argument("--max-length", type=int, default=MAX_LENGTH)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--learning-rate", type=float, default=LEARNING_RATE)
    parser.add_argument("--seed", type=int, default=RANDOM_SEED)
    parser.add_argument("--test-size", type=float, default=TEST_SIZE)
    args = parser.parse_args()

    started = time.time()
    set_seed(args.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device: {device}")

    df = load_dataset(args.data)
    dataset_summary = {
        "rows": int(len(df)),
        "label_counts": {int(k): int(v) for k, v in df["label"].value_counts().sort_index().items()},
        "source_counts": {str(k): int(v) for k, v in df["source"].value_counts().sort_index().items()},
    }
    print(f"Dataset rows: {dataset_summary['rows']:,}")

    tokenizer = AutoTokenizer.from_pretrained(args.model_name)

    random_train, random_test = train_test_split(
        df,
        test_size=args.test_size,
        random_state=args.seed,
        stratify=df["label"],
    )
    random_train = random_train.reset_index(drop=True)
    random_test = random_test.reset_index(drop=True)

    cross_a_train = df[df["source"].isin(["enron", "nazario"])].reset_index(drop=True)
    cross_a_test = df[df["source"] == "spamassassin"].reset_index(drop=True)

    cross_b_train = df[df["source"].isin(["enron", "spamassassin"])].reset_index(drop=True)
    cross_b_test = df[df["source"] == "nazario"].reset_index(drop=True)

    random_result = run_textonly_frozen_split(
        split_name="random_split",
        train_df=random_train,
        test_df=random_test,
        tokenizer=tokenizer,
        model_name=args.model_name,
        max_length=args.max_length,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        device=device,
    )

    cross_a_result = run_textonly_frozen_split(
        split_name="cross_source_a",
        train_df=cross_a_train,
        test_df=cross_a_test,
        tokenizer=tokenizer,
        model_name=args.model_name,
        max_length=args.max_length,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        device=device,
    )

    cross_b_result = run_textonly_frozen_split(
        split_name="cross_source_b",
        train_df=cross_b_train,
        test_df=cross_b_test,
        tokenizer=tokenizer,
        model_name=args.model_name,
        max_length=args.max_length,
        batch_size=args.batch_size,
        epochs=args.epochs,
        learning_rate=args.learning_rate,
        device=device,
    )

    metadata = {
        "artifact_name": "email_final_model",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": args.model_name,
        "architecture": "distilbert_textonly_frozen",
        "max_length": args.max_length,
        "label_mapping": {"0": LABEL_MAP[0], "1": LABEL_MAP[1]},
        "training_config": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "test_size": args.test_size,
            "seed": args.seed,
            "encoder_frozen": True,
        },
        "threshold_recommendation_range": {
            "high_recall_soc_detection": "0.2-0.3",
            "high_confidence_alerts": "0.7-0.8",
            "default": 0.5,
        },
        "preprocessing_rules": {
            "text_input": "subject + ' [SEP] ' + body",
            "missing_subject_or_body": "treated as empty string",
            "label_filter": "only labels {0,1} retained",
            "source_normalization": "lowercase source names",
        },
        "random_split_metrics_at_0_5": {
            "accuracy": random_result.metrics_05["accuracy"],
            "precision": random_result.metrics_05["precision"],
            "recall": random_result.metrics_05["recall"],
            "f1": random_result.metrics_05["f1"],
            "roc_auc": random_result.metrics_05.get("roc_auc"),
            "confusion_matrix": random_result.metrics_05["confusion_matrix"],
        },
    }

    if random_result.model is None:
        raise RuntimeError("Random split model missing; packaging cannot continue.")
    save_model_artifacts(
        model=random_result.model,
        tokenizer=tokenizer,
        metadata=metadata,
    )
    write_threshold_report(THRESH_REPORT_OUT, random_result.thresholds)
    write_final_model_report(
        path=FINAL_REPORT_OUT,
        dataset_summary=dataset_summary,
        random_result=random_result,
        cross_a=cross_a_result,
        cross_b=cross_b_result,
    )

    runtime = time.time() - started
    print("\n=== TG-6.0 Complete ===")
    print(f"Saved model: {os.path.relpath(MODEL_OUT, ROOT)}")
    print(f"Saved tokenizer: {os.path.relpath(TOKENIZER_OUT, ROOT)}")
    print(f"Saved metadata: {os.path.relpath(META_OUT, ROOT)}")
    print(f"Saved threshold report: {os.path.relpath(THRESH_REPORT_OUT, ROOT)}")
    print(f"Saved final report: {os.path.relpath(FINAL_REPORT_OUT, ROOT)}")
    print(
        "Random metrics @0.5: "
        f"F1={random_result.metrics_05['f1']:.4f}, "
        f"ROC-AUC={format_float(random_result.metrics_05.get('roc_auc'))}"
    )
    print(f"Runtime seconds: {runtime:.1f}")


if __name__ == "__main__":
    main()

