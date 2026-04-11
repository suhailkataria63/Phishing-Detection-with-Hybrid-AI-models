from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PredictRequest(BaseModel):
    url: str = Field(..., min_length=3, description="URL to analyze")
    enable_context: bool = False
    enable_explain: bool = True


class Reason(BaseModel):
    feature: str
    value: Any
    note: str


class PredictResponse(BaseModel):
    label: Literal["phishing", "legitimate"]
    probability: float = Field(..., ge=0.0, le=1.0)

    # per-signal scores (for future fusion)
    url_score: float = Field(..., ge=0.0, le=1.0)
    domain_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    email_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    reasons: List[Reason] = []
    context: Optional[Dict[str, Any]] = None

    meta: Dict[str, Any] = {}


class EmailPredictRequest(BaseModel):
    subject: str = ""
    body: str = ""
    sender: str = ""
    operating_mode: Literal["soc", "balanced", "high_confidence"] = "balanced"
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    enable_explain: bool = True


class EmailPredictResponse(BaseModel):
    label: Literal["phishing", "legitimate"]
    probability: float = Field(..., ge=0.0, le=1.0)
    email_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high", "critical"]
    suggested_action: str
    reasons: List[Reason] = []
    context: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = {}


class JointPredictRequest(BaseModel):
    subject: str = ""
    body: str = ""
    sender: str = ""
    urls: List[str] = []
    operating_mode: Literal["soc", "balanced", "high_confidence"] = "balanced"
    joint_strategy: Literal["baseline", "optimized"] = "optimized"
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    enable_explain: bool = True


class URLAssessment(BaseModel):
    url: str
    label: Literal["phishing", "legitimate"]
    score: float = Field(..., ge=0.0, le=1.0)
    reasons: List[Reason] = []


class JointPredictResponse(BaseModel):
    final_label: Literal["phishing", "legitimate"]
    final_score: float = Field(..., ge=0.0, le=1.0)
    risk_level: Literal["low", "medium", "high", "critical"]

    email_label: Literal["phishing", "legitimate"]
    email_score: float = Field(..., ge=0.0, le=1.0)

    url_score: float = Field(..., ge=0.0, le=1.0)
    analyzed_url_count: int = Field(default=0, ge=0)
    risky_url_count: int = Field(default=0, ge=0)

    extracted_urls: List[str] = []
    url_results: List[URLAssessment] = []

    reasons: List[Reason] = []
    context: Optional[Dict[str, Any]] = None
    meta: Dict[str, Any] = {}
