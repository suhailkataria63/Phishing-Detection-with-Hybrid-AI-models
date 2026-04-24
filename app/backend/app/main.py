from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .schemas import (
    EmailPredictRequest,
    EmailPredictResponse,
    JointPredictRequest,
    JointPredictResponse,
    PredictRequest,
    PredictResponse,
    Reason,
    URLAssessment,
)
from .ml.email_model import EmailInferenceInput, EmailModel
from .ml.hybrid_url import HybridURLModel
from .ml.email_model import (
    DEFAULT_MODEL_PATH as EMAIL_MODEL_PATH,
    DEFAULT_META_PATH as EMAIL_META_PATH,
    DEFAULT_TOKENIZER_PATH as EMAIL_TOKENIZER_PATH,
)
from .ml.url_model import MODEL_PATH as URL_V1_MODEL_PATH, SCHEMA_PATH as URL_V1_SCHEMA_PATH
from .ml.url_model_v2 import V2_PATH as URL_V2_MODEL_PATH
from .utils.domain_utils import (
    TRUST_UNTRUSTED,
    classify_trusted_domain,
    extract_registrable_domain,
    is_top_ranked_domain,
)
from .utils.email_utils import dedupe_preserve_order, extract_sender_domain, extract_urls_from_text
from .utils.joint_optimization import (
    apply_rule_assisted_joint_score,
    extract_joint_heuristic_features,
)
from .utils.joint_scoring import combine_email_url_scores, risk_level_from_score


app = FastAPI(title=settings.app_name)
url_model = HybridURLModel()
email_model = EmailModel()
MODEL_LOAD_STATUS = {
    "url_model_loaded": False,
    "email_model_loaded": False,
    "url_model_error": "",
    "email_model_error": "",
}
OPERATING_MODE_THRESHOLDS = {
    "soc": 0.40,
    "balanced": 0.50,
    "high_confidence": 0.60,
}

origins = settings.resolved_cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    url_ready = bool(getattr(url_model.v1, "model", None) and getattr(url_model.v2, "model", None))
    email_ready = email_model.is_ready
    MODEL_LOAD_STATUS["url_model_loaded"] = url_ready
    MODEL_LOAD_STATUS["email_model_loaded"] = email_ready

    return {
        "status": "ok",
        "service": settings.app_name,
        "url_model_loaded": url_ready,
        "email_model_ready": email_ready,
        "url_model_error": MODEL_LOAD_STATUS.get("url_model_error", ""),
        "email_model_error": MODEL_LOAD_STATUS.get("email_model_error", ""),
        "model_paths": {
            "url_v1_model": str(URL_V1_MODEL_PATH),
            "url_v1_schema": str(URL_V1_SCHEMA_PATH),
            "url_v2_model": str(URL_V2_MODEL_PATH),
            "email_model": str(EMAIL_MODEL_PATH),
            "email_tokenizer": str(EMAIL_TOKENIZER_PATH),
            "email_meta": str(EMAIL_META_PATH),
        },
        "model_paths_exist": {
            "url_v1_model": URL_V1_MODEL_PATH.exists(),
            "url_v1_schema": URL_V1_SCHEMA_PATH.exists(),
            "url_v2_model": URL_V2_MODEL_PATH.exists(),
            "email_model": EMAIL_MODEL_PATH.exists(),
            "email_tokenizer": EMAIL_TOKENIZER_PATH.exists(),
            "email_meta": EMAIL_META_PATH.exists(),
        },
    }


@app.on_event("startup")
def startup_event():
    try:
        url_model.load()
        MODEL_LOAD_STATUS["url_model_loaded"] = True
        MODEL_LOAD_STATUS["url_model_error"] = ""
    except Exception as exc:
        MODEL_LOAD_STATUS["url_model_loaded"] = False
        MODEL_LOAD_STATUS["url_model_error"] = str(exc)

    try:
        email_model.load()
        MODEL_LOAD_STATUS["email_model_loaded"] = bool(email_model.is_ready)
        MODEL_LOAD_STATUS["email_model_error"] = ""
    except Exception as exc:
        MODEL_LOAD_STATUS["email_model_loaded"] = False
        MODEL_LOAD_STATUS["email_model_error"] = str(exc)


def _ensure_url_model_ready() -> None:
    if bool(getattr(url_model.v1, "model", None) and getattr(url_model.v2, "model", None)):
        return
    detail = MODEL_LOAD_STATUS.get("url_model_error", "") or "URL model artifacts are missing or failed to load."
    raise HTTPException(status_code=503, detail=f"URL model unavailable: {detail}")


# Legacy URL endpoint (kept intact for backwards compatibility).
@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    _ensure_url_model_ready()
    return url_model.predict(req.url, enable_explain=req.enable_explain)


# New explicit URL endpoint.
@app.post("/detect/url", response_model=PredictResponse)
def detect_url(req: PredictRequest):
    _ensure_url_model_ready()
    return url_model.predict(req.url, enable_explain=req.enable_explain)


def _ensure_email_input(subject: str, body: str) -> None:
    if not (subject or "").strip() and not (body or "").strip():
        raise HTTPException(status_code=422, detail="Provide at least subject or body for email analysis.")


def _resolve_threshold(operating_mode: str, explicit_threshold: float | None) -> float:
    if explicit_threshold is not None:
        return float(max(0.0, min(1.0, explicit_threshold)))
    return float(OPERATING_MODE_THRESHOLDS.get((operating_mode or "balanced").strip().lower(), 0.5))


def _compute_sender_url_mismatch_score(sender_domain: str, urls: list[str]) -> tuple[float, dict]:
    sender_domain = (sender_domain or "").strip().lower()
    if not sender_domain or not urls:
        return 0.0, {
            "sender_domain": sender_domain,
            "sender_registrable": "",
            "url_registrables": [],
            "mismatch": False,
            "reason": "insufficient_context",
        }

    sender_reg = extract_registrable_domain(sender_domain)
    url_regs = sorted({extract_registrable_domain(u) for u in urls if extract_registrable_domain(u)})
    if not sender_reg or not url_regs:
        return 0.0, {
            "sender_domain": sender_domain,
            "sender_registrable": sender_reg,
            "url_registrables": url_regs,
            "mismatch": False,
            "reason": "insufficient_context",
        }

    aligned = sender_reg in url_regs
    if aligned:
        return 0.0, {
            "sender_domain": sender_domain,
            "sender_registrable": sender_reg,
            "url_registrables": url_regs,
            "mismatch": False,
            "reason": "aligned",
        }

    sender_reputable = (
        classify_trusted_domain(sender_reg) != TRUST_UNTRUSTED or is_top_ranked_domain(sender_reg, max_rank=20000)
    )
    untrusted_url_regs = [
        reg for reg in url_regs
        if classify_trusted_domain(reg) == TRUST_UNTRUSTED and not is_top_ranked_domain(reg, max_rank=20000)
    ]
    mismatch_score = 0.35
    mismatch_reason = "domain_mismatch"
    if sender_reputable and untrusted_url_regs:
        mismatch_score = 0.80
        mismatch_reason = "reputable_sender_to_untrusted_url"
    elif untrusted_url_regs:
        mismatch_score = 0.60
        mismatch_reason = "mismatch_with_untrusted_url"

    return mismatch_score, {
        "sender_domain": sender_domain,
        "sender_registrable": sender_reg,
        "url_registrables": url_regs,
        "mismatch": True,
        "reason": mismatch_reason,
        "sender_reputable": sender_reputable,
        "untrusted_url_registrables": untrusted_url_regs,
    }


@app.post("/detect/email", response_model=EmailPredictResponse)
@app.post("/predict/email", response_model=EmailPredictResponse)
def detect_email(req: EmailPredictRequest):
    _ensure_email_input(req.subject, req.body)
    effective_threshold = _resolve_threshold(req.operating_mode, req.threshold)
    sender_domain = extract_sender_domain(req.sender)

    payload = EmailInferenceInput(
        subject=req.subject,
        body=req.body,
        sender=req.sender,
        sender_domain=sender_domain,
    )
    out = email_model.predict(payload, threshold=effective_threshold)
    out.setdefault("meta", {})
    out["meta"]["operating_mode"] = req.operating_mode
    out["meta"]["resolved_threshold"] = effective_threshold
    return EmailPredictResponse(**out)


@app.post("/detect/joint", response_model=JointPredictResponse)
@app.post("/predict/joint", response_model=JointPredictResponse)
def detect_joint(req: JointPredictRequest):
    if not (req.subject or "").strip() and not (req.body or "").strip() and not req.urls:
        raise HTTPException(status_code=422, detail="Provide email content and/or URLs for joint analysis.")
    effective_threshold = _resolve_threshold(req.operating_mode, req.threshold)
    sender_domain = extract_sender_domain(req.sender)

    extracted_urls = extract_urls_from_text(req.body or "")
    merged_urls = dedupe_preserve_order([*(req.urls or []), *extracted_urls])

    email_payload = EmailInferenceInput(
        subject=req.subject,
        body=req.body,
        sender=req.sender,
        sender_domain=sender_domain,
    )
    email_out = email_model.predict(email_payload, threshold=effective_threshold)
    email_score = float(email_out.get("email_score", email_out.get("probability", 0.5)))
    email_hard_cue_count = int(email_out.get("context", {}).get("stealth_social_engineering_hits", 0))

    url_results = []
    url_scores = []
    trusted_url_flags = []
    reputable_url_flags = []
    any_url_hard_cue = False
    max_urls_to_analyze = 20
    for raw_url in merged_urls[:max_urls_to_analyze]:
        trust_kind = classify_trusted_domain(raw_url)
        is_trusted = trust_kind != TRUST_UNTRUSTED
        is_popular = is_top_ranked_domain(raw_url, max_rank=20000)
        trusted_url_flags.append(is_trusted)
        reputable_url_flags.append(is_trusted or is_popular)

        try:
            url_out = url_model.predict(raw_url, enable_explain=req.enable_explain)
            score = float(url_out.get("url_score", url_out.get("probability", 0.0)))
            url_scores.append(score)

            hard_cue_features = {
                "has_ip_host",
                "tld_suspicious",
                "num_at",
                "has_http_in_path",
                "rule_override",
                "fake_brand_domain",
                "ip_sensitive_path",
                "embedded_redirect_target",
                "untrusted_lure_pattern",
            }
            meta_hard = bool(url_out.get("meta", {}).get("has_hard_cue", False))
            reason_hard = any(
                isinstance(r, dict) and r.get("feature") in hard_cue_features
                for r in (url_out.get("reasons") or [])
            )
            any_url_hard_cue = any_url_hard_cue or meta_hard or reason_hard

            reasons = []
            if req.enable_explain:
                for r in (url_out.get("reasons") or [])[:4]:
                    if isinstance(r, dict) and {"feature", "value", "note"}.issubset(r.keys()):
                        reasons.append(Reason(**r))

            url_results.append(
                URLAssessment(
                    url=raw_url,
                    label=str(url_out.get("label", "legitimate")),
                    score=score,
                    reasons=reasons,
                )
            )
        except Exception as exc:
            if req.enable_explain:
                url_results.append(
                    URLAssessment(
                        url=raw_url,
                        label="legitimate",
                        score=0.0,
                        reasons=[
                            Reason(
                                feature="url_analysis_error",
                                value=str(exc),
                                note="URL could not be analyzed and was skipped from risk aggregation.",
                            )
                        ],
                    )
                )

    all_urls_trusted = bool(trusted_url_flags) and all(trusted_url_flags)
    all_urls_reputable = bool(reputable_url_flags) and all(reputable_url_flags)
    sender_url_mismatch_score, sender_url_meta = _compute_sender_url_mismatch_score(sender_domain, merged_urls)
    baseline_joint = combine_email_url_scores(
        email_score=email_score,
        url_scores=url_scores,
        threshold=effective_threshold,
        all_urls_reputable=all_urls_reputable,
        any_url_hard_cue=any_url_hard_cue,
        sender_url_mismatch_score=sender_url_mismatch_score,
        email_hard_cue_count=email_hard_cue_count,
    )
    heuristic_features = extract_joint_heuristic_features(
        subject=req.subject,
        body=req.body,
        sender=req.sender,
        urls=merged_urls,
        email_score=email_score,
        url_scores=url_scores,
    )
    joint = baseline_joint
    if req.joint_strategy == "optimized":
        opt_score, opt_label, opt_notes, opt_flags = apply_rule_assisted_joint_score(
            email_score=email_score,
            url_scores=url_scores,
            heuristic=heuristic_features,
            threshold=effective_threshold,
        )
        joint = {
            **baseline_joint,
            "final_score": opt_score,
            "final_label": opt_label,
            "risk_level": risk_level_from_score(opt_score),
            "optimized_rule_count": len(opt_notes),
            "reasons": [
                *baseline_joint.get("reasons", []),
                "Optimized strategy enabled: rule-assisted calibrations applied.",
                *opt_notes,
            ],
            "optimization_flags": opt_flags,
        }

    reasons = []
    if req.enable_explain:
        if not merged_urls:
            reasons.append(
                Reason(
                    feature="urls_extracted",
                    value=0,
                    note="No URLs found in body or manual input; joint decision relied on email channel.",
                )
            )
        else:
            reasons.append(
                Reason(
                    feature="urls_extracted",
                    value=len(merged_urls),
                    note="Joint analysis includes both extracted and manually provided URLs.",
                )
            )
        if sender_url_meta.get("mismatch"):
            reasons.append(
                Reason(
                    feature="sender_url_domain_mismatch",
                    value={
                        "sender_registrable": sender_url_meta.get("sender_registrable"),
                        "url_registrables": sender_url_meta.get("url_registrables"),
                        "mismatch_score": round(sender_url_mismatch_score, 3),
                    },
                    note=(
                        "Sender domain does not align with linked domains; mismatch contributes to risk based on sender/url trust context."
                    ),
                )
            )

        for idx, line in enumerate(joint.get("reasons", [])):
            reasons.append(
                Reason(
                    feature=f"joint_logic_{idx+1}",
                    value={
                        "email_score": round(joint["email_score"], 4),
                        "url_score": round(joint["url_score"], 4),
                        "email_weight": round(float(joint.get("email_weight", 0.6)), 2),
                        "url_weight": round(float(joint.get("url_weight", 0.4)), 2),
                    },
                    note=str(line),
                )
            )

    return JointPredictResponse(
        final_label=joint["final_label"],
        final_score=joint["final_score"],
        risk_level=joint["risk_level"],
        email_label=str(email_out.get("label", "legitimate")),
        email_score=float(joint["email_score"]),
        url_score=float(joint["url_score"]),
        analyzed_url_count=int(joint["analyzed_url_count"]),
        risky_url_count=int(joint["risky_url_count"]),
        extracted_urls=merged_urls,
        url_results=url_results,
        reasons=reasons,
        context={
            "email_text_length": int(email_out.get("context", {}).get("text_length", 0)),
            "max_urls_analyzed": max_urls_to_analyze,
        },
        meta={
            "engine": "joint_email_url_rule_ensemble",
            "weights": {
                "email": float(joint.get("email_weight", 0.6)),
                "url": float(joint.get("url_weight", 0.4)),
            },
            "threshold": effective_threshold,
            "resolved_threshold": effective_threshold,
            "operating_mode": req.operating_mode,
            "email_engine": email_out.get("meta", {}).get("engine"),
            "url_engine": "hybrid_url_v1_v2",
            "joint_strategy": req.joint_strategy,
            "strategy_version": str(
                joint.get("optimization_flags", {}).get("strategy_version", "baseline_v1")
            ),
            "all_urls_trusted": all_urls_trusted,
            "all_urls_reputable": all_urls_reputable,
            "any_url_hard_cue": any_url_hard_cue,
            "sender_domain": sender_domain,
            "sender_url_mismatch_score": sender_url_mismatch_score,
            "email_hard_cue_count": email_hard_cue_count,
            "trusted_domain_match": bool(
                joint.get("optimization_flags", {}).get(
                    "trusted_domain_match",
                    heuristic_features.get("trusted_domain_match", 0.0) > 0,
                )
            ),
            "brand_domain_mismatch": bool(
                joint.get("optimization_flags", {}).get(
                    "brand_domain_mismatch",
                    heuristic_features.get("brand_domain_mismatch", 0.0) > 0,
                )
            ),
            "no_url_benign_support": bool(
                joint.get("optimization_flags", {}).get(
                    "no_url_benign_support",
                    heuristic_features.get("no_url_benign_support", 0.0) > 0,
                )
            ),
            "suspicious_url_escalation": bool(
                joint.get("optimization_flags", {}).get(
                    "suspicious_url_escalation",
                    heuristic_features.get("suspicious_url_escalation", 0.0) > 0,
                )
            ),
            "heuristics": {
                "url_count": int(heuristic_features.get("url_count", 0.0)),
                "suspicious_url_indicators": int(
                    heuristic_features.get("ip_url_count", 0.0)
                    + heuristic_features.get("suspicious_tld_count", 0.0)
                    + heuristic_features.get("typosquat_count", 0.0)
                    + heuristic_features.get("shortener_count", 0.0)
                ),
                "benign_hits": int(heuristic_features.get("benign_hits", 0.0)),
                "suspicious_email_lex": int(heuristic_features.get("suspicious_email_lex", 0.0)),
                "trusted_domain_match": int(heuristic_features.get("trusted_domain_match", 0.0)),
                "brand_domain_mismatch": int(heuristic_features.get("brand_domain_mismatch", 0.0)),
                "no_url_benign_support": int(heuristic_features.get("no_url_benign_support", 0.0)),
                "suspicious_url_escalation": int(heuristic_features.get("suspicious_url_escalation", 0.0)),
                "multi_url_conflict": int(heuristic_features.get("multi_url_conflict", 0.0)),
            },
        },
    )
