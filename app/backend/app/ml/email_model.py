"""Email phishing inference using packaged final DistilBERT artifacts.

This module powers TG-6.0 email detection in the FastAPI backend.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from torch import nn
from transformers import AutoModel, AutoTokenizer

from ..utils.domain_utils import (
    TRUST_UNTRUSTED,
    classify_trusted_domain,
    is_top_ranked_domain,
)
from ..utils.email_utils import build_email_text, dedupe_preserve_order, extract_urls_from_text
from ..utils.joint_scoring import risk_level_from_score


PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODEL_DIR = PROJECT_ROOT / "models"

DEFAULT_MODEL_PATH = MODEL_DIR / "email" / "email_final_model.pt"
DEFAULT_TOKENIZER_PATH = MODEL_DIR / "email" / "email_final_tokenizer"
DEFAULT_META_PATH = MODEL_DIR / "email" / "email_final_metadata.json"

LEGACY_MODEL_PATH = MODEL_DIR / "email" / "email_transformer_model.pt"
LEGACY_META_PATH = MODEL_DIR / "email" / "email_transformer_metadata.json"

DEFAULT_MAX_LENGTH = 256

BENIGN_NOTIFICATION_HINTS = (
    "monthly statement",
    "account statement",
    "statement is ready",
    "official banking portal",
)
BENIGN_TRANSACTIONAL_HINTS = (
    "order has been shipped",
    "track your shipment",
    "delivery update",
    "your monthly statement",
    "account statement is now available",
    "view your order",
    "order details",
    "invoice is ready",
)
URGENCY_LURE_HINTS = (
    "urgent",
    "immediately",
    "within 24 hours",
    "suspended",
    "suspension",
    "verify now",
    "action required",
    "click now",
)
CREDENTIAL_LURE_HINTS = (
    "verify your account",
    "verify identity",
    "account verification",
    "sign in",
    "login",
    "password",
    "reset password",
    "otp",
    "authentication",
)
STEALTH_SOCIAL_ENGINEERING_HINTS = (
    "gift card",
    "wire transfer",
    "bank account change",
    "change payment details",
    "update payment details",
    "employee login",
    "review the attached",
    "open attachment",
    "docusign",
    "shared document",
    "confirm acknowledgement",
    "payroll",
    "crypto wallet",
    "seed phrase",
)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    t = (text or "").lower()
    return any(n in t for n in needles)


def _count_matches(text: str, needles: tuple[str, ...]) -> int:
    t = (text or "").lower()
    return sum(1 for n in needles if n in t)


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

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        outputs = self.encoder(input_ids=input_ids, attention_mask=attention_mask)
        text_embedding = outputs.last_hidden_state[:, 0, :]
        return self.classifier(text_embedding).squeeze(1)


@dataclass
class EmailInferenceInput:
    subject: str
    body: str
    sender: str = ""
    sender_domain: str = ""
    urls: List[str] = field(default_factory=list)


class EmailModel:
    """Runtime loader and predictor for packaged email phishing artifacts."""

    def __init__(
        self,
        model_path: Path = DEFAULT_MODEL_PATH,
        tokenizer_path: Path = DEFAULT_TOKENIZER_PATH,
        meta_path: Path = DEFAULT_META_PATH,
    ) -> None:
        self.model_path = model_path
        self.tokenizer_path = tokenizer_path
        self.meta_path = meta_path

        self.model: Optional[DistilBertTextOnlyModel] = None
        self.tokenizer = None
        self.meta: Dict[str, Any] = {}
        self.runtime_supported = False
        self.device = torch.device("cpu")
        self.max_length = DEFAULT_MAX_LENGTH

    def _resolve_artifacts(self) -> None:
        if not self.model_path.exists() and LEGACY_MODEL_PATH.exists():
            self.model_path = LEGACY_MODEL_PATH
        if not self.meta_path.exists() and LEGACY_META_PATH.exists():
            self.meta_path = LEGACY_META_PATH

    def load(self) -> None:
        self._resolve_artifacts()

        if self.meta_path.exists():
            try:
                self.meta = json.loads(self.meta_path.read_text(encoding="utf-8"))
            except Exception:
                self.meta = {"warning": "Failed to parse metadata JSON."}

        if not self.model_path.exists():
            self.runtime_supported = False
            self.model = None
            self.tokenizer = None
            self.meta = {
                **self.meta,
                "status": "not_trained",
                "expected_model_path": str(self.model_path),
                "expected_tokenizer_path": str(self.tokenizer_path),
            }
            return

        try:
            ckpt = torch.load(self.model_path, map_location="cpu")
            model_name = str(
                ckpt.get("model_name")
                or self.meta.get("model_name")
                or "distilbert-base-uncased"
            )
            self.max_length = int(
                ckpt.get("max_length")
                or self.meta.get("max_length")
                or DEFAULT_MAX_LENGTH
            )

            if self.tokenizer_path.exists():
                self.tokenizer = AutoTokenizer.from_pretrained(str(self.tokenizer_path))
            else:
                # Fallback for older packaging if tokenizer directory is absent.
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)

            model = DistilBertTextOnlyModel(model_name=model_name)
            classifier_state = ckpt.get("classifier_state_dict") if isinstance(ckpt, dict) else None
            if isinstance(classifier_state, dict):
                model.classifier.load_state_dict(classifier_state)
            model.eval()
            model.to(self.device)
            self.model = model

            self.runtime_supported = True
            self.meta = {
                **self.meta,
                "status": "ready",
                "artifact_path": str(self.model_path),
                "tokenizer_path": str(self.tokenizer_path),
                "engine": "email_final_distilbert_text_frozen",
                "model_name": model_name,
                "max_length": self.max_length,
            }
        except Exception as exc:
            self.runtime_supported = False
            self.model = None
            self.tokenizer = None
            self.meta = {
                **self.meta,
                "status": "load_failed",
                "error": str(exc),
            }

    @property
    def is_ready(self) -> bool:
        return self.runtime_supported and self.model is not None and self.tokenizer is not None

    def predict(self, payload: EmailInferenceInput, threshold: float = 0.5) -> Dict[str, Any]:
        text = build_email_text(payload.subject, payload.body)
        safe_threshold = float(max(0.0, min(1.0, threshold)))

        if not text:
            return {
                "label": "legitimate",
                "probability": 0.0,
                "email_score": 0.0,
                "risk_level": "low",
                "suggested_action": "Provide a subject or body before analysis.",
                "reasons": [
                    {
                        "feature": "email_input",
                        "value": "empty",
                        "note": "Subject/body are empty; no content to evaluate.",
                    }
                ],
                "context": {"text_length": 0, "token_count": 0},
                "meta": {
                    "engine": "email_final_distilbert_text_frozen",
                    "threshold": safe_threshold,
                    **self.meta,
                },
            }

        if not self.is_ready:
            return {
                "label": "legitimate",
                "probability": 0.5,
                "email_score": 0.5,
                "risk_level": "medium",
                "suggested_action": "Model artifacts are not ready; verify backend setup.",
                "reasons": [
                    {
                        "feature": "email_model_status",
                        "value": self.meta.get("status", "not_ready"),
                        "note": "Email model is not loaded; returning neutral score.",
                    }
                ],
                "context": {"text_length": len(text), "token_count": 0},
                "meta": {
                    "engine": "email_final_distilbert_text_frozen",
                    "threshold": safe_threshold,
                    **self.meta,
                },
            }

        enc = self.tokenizer(
            [text],
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )

        with torch.no_grad():
            logits = self.model(
                input_ids=enc["input_ids"].to(self.device),
                attention_mask=enc["attention_mask"].to(self.device),
            )
            # Avoid NumPy dependency at inference-time tensor conversion.
            score = float(torch.sigmoid(logits).detach().cpu().item())

        reasons: List[Dict[str, Any]] = []
        merged_urls = dedupe_preserve_order([*(payload.urls or []), *extract_urls_from_text(payload.body or "")])
        all_urls_reputable = bool(merged_urls) and all(
            (classify_trusted_domain(u) != TRUST_UNTRUSTED) or is_top_ranked_domain(u, max_rank=20000)
            for u in merged_urls
        )
        trusted_url_count = sum(
            classify_trusted_domain(u) != TRUST_UNTRUSTED for u in merged_urls
        )
        top_ranked_url_count = sum(is_top_ranked_domain(u, max_rank=20000) for u in merged_urls)
        benign_statement_like = _contains_any(text, BENIGN_NOTIFICATION_HINTS)
        benign_transactional_hits = _count_matches(text, BENIGN_TRANSACTIONAL_HINTS)
        has_urgency_lure = _contains_any(text, URGENCY_LURE_HINTS)
        credential_lure_hits = _count_matches(text, CREDENTIAL_LURE_HINTS)
        stealth_se_hits = _count_matches(text, STEALTH_SOCIAL_ENGINEERING_HINTS)

        if (
            all_urls_reputable
            and benign_statement_like
            and not has_urgency_lure
            and score < 0.97
        ):
            original = score
            score = min(score, 0.35)
            reasons.append(
                {
                    "feature": "reputable_statement_notification_guard",
                    "value": {
                        "original_score": round(original, 4),
                        "adjusted_score": round(score, 4),
                        "trusted_urls": trusted_url_count,
                        "top_ranked_urls": top_ranked_url_count,
                    },
                    "note": (
                        "Detected benign statement-style notification with trusted/top-ranked portal URLs and no urgency cues; "
                        "score dampened to reduce false positives."
                    ),
                }
            )

        if (
            all_urls_reputable
            and benign_transactional_hits >= 2
            and not has_urgency_lure
            and stealth_se_hits == 0
            and credential_lure_hits <= 1
            and score < 0.97
        ):
            original = score
            adjusted_cap = 0.32 if trusted_url_count > 0 else 0.38
            score = min(score, adjusted_cap)
            reasons.append(
                {
                    "feature": "transactional_benign_guard",
                    "value": {
                        "original_score": round(original, 4),
                        "adjusted_score": round(score, 4),
                        "transactional_hits": benign_transactional_hits,
                        "trusted_urls": trusted_url_count,
                        "top_ranked_urls": top_ranked_url_count,
                    },
                    "note": (
                        "Transactional/shipping/statement pattern detected with reputable URLs and no urgency; "
                        "score dampened to reduce false positives."
                    ),
                }
            )

        if (
            stealth_se_hits >= 2
            and (credential_lure_hits >= 1 or has_urgency_lure)
            and score < 0.9
        ):
            original = score
            score = max(score, 0.72)
            reasons.append(
                {
                    "feature": "stealth_social_engineering_cue",
                    "value": {
                        "original_score": round(original, 4),
                        "adjusted_score": round(score, 4),
                        "stealth_hits": stealth_se_hits,
                        "credential_hits": credential_lure_hits,
                    },
                    "note": (
                        "Detected high-risk social-engineering intent with credential/urgency language; "
                        "score elevated for benign-looking phishing patterns."
                    ),
                }
            )

        label = "phishing" if score >= safe_threshold else "legitimate"
        risk_level = risk_level_from_score(score)

        if score >= 0.8:
            suggested_action = "Escalate immediately and quarantine related messages."
        elif score >= 0.5:
            suggested_action = "Flag for analyst review before user interaction."
        elif score >= 0.3:
            suggested_action = "Monitor and inspect links/sender context."
        else:
            suggested_action = "Likely legitimate; keep routine monitoring."

        return {
            "label": label,
            "probability": score,
            "email_score": score,
            "risk_level": risk_level,
            "suggested_action": suggested_action,
            "reasons": reasons + [
                {
                    "feature": "email_threshold_check",
                    "value": {"score": round(score, 4), "threshold": safe_threshold},
                    "note": "Email verdict is derived from model score compared with threshold.",
                }
            ],
            "context": {
                "text_length": len(text),
                "token_count": int(enc["attention_mask"].sum().item()),
                "trusted_urls_detected": trusted_url_count,
                "top_ranked_urls_detected": top_ranked_url_count,
                "all_urls_reputable": all_urls_reputable,
                "transactional_benign_hits": benign_transactional_hits,
                "credential_lure_hits": credential_lure_hits,
                "stealth_social_engineering_hits": stealth_se_hits,
            },
            "meta": {
                "engine": "email_final_distilbert_text_frozen",
                "threshold": safe_threshold,
                **self.meta,
            },
        }


def planned_fusion_contract() -> Dict[str, Any]:
    """Document how email score can be fused with URL/domain signals."""
    return {
        "text_channel": "transformer probability from subject+body",
        "signal_channel": "URL model probabilities + domain heuristics",
        "fusion_strategy": "rule-based weighted ensemble with escalation guardrails",
        "status": "implemented_for_joint_detection",
    }
