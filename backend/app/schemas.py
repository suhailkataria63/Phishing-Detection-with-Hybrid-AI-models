from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any

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
