"""Pydantic models: API input, and model replies (validated in code)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUBSYSTEMS = ("propulsion", "avionics", "communications", "ground_support", "weather", "structures")
UNCLASSIFIED = "unclassified"


class ReportIn(BaseModel):
    """Rejects only physically impossible input. Out-of-limit values are accepted and become no_go."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    station: str = Field(min_length=1, max_length=100)
    # strict: real JSON numbers only (no "12" strings, no booleans); NaN/Infinity rejected as "not finite"
    wind_knots: float = Field(ge=0, le=200, strict=True, allow_inf_nan=False, description="0-200 kn is physically possible")
    temp_c: float = Field(ge=-80, le=80, strict=True, allow_inf_nan=False, description="-80..80 C is physically possible")
    fuel_pct: float = Field(ge=0, le=120, strict=True, allow_inf_nan=False, description="0-120% sensor range")
    note: str = Field(min_length=1, max_length=4000)

    @field_validator("name", "station", "note", mode="before")
    @classmethod
    def _strip(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("must not be blank")
        return v


def _not_blank(v):
    if isinstance(v, str):
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
    return v


class ApproveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approver: str = Field(min_length=1, max_length=100)
    acknowledge_injection: bool = False

    @field_validator("approver", mode="before")
    @classmethod
    def _approver(cls, v):
        # a person must be named: whitespace-only names are rejected, names are stored trimmed
        return _not_blank(v)


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approver: str = Field(min_length=1, max_length=100)
    reason: str = Field(default="", max_length=1000)

    @field_validator("approver", mode="before")
    @classmethod
    def _approver(cls, v):
        return _not_blank(v)


# ---- model reply schemas (validated in code after every call) ----

class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subsystem: Literal["propulsion", "avionics", "communications", "ground_support", "weather", "structures"]
    severity: Literal["high", "medium", "low"]
    rationale: str


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flagged: bool
    findings: list[str]


class Draft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str
    recommended_actions: list[str]


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid")
    passed: bool
    feedback: str


def _strict(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties,
            "required": required or list(properties), "additionalProperties": False}


CLASSIFICATION_SCHEMA = _strict({
    "subsystem": {"type": "string", "enum": list(SUBSYSTEMS)},
    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
    "rationale": {"type": "string"},
})
CHECK_SCHEMA = _strict({
    "flagged": {"type": "boolean"},
    "findings": {"type": "array", "items": {"type": "string"}},
})
DRAFT_SCHEMA = _strict({
    "summary": {"type": "string"},
    "recommended_actions": {"type": "array", "items": {"type": "string"}},
})
REVIEW_SCHEMA = _strict({
    "passed": {"type": "boolean"},
    "feedback": {"type": "string"},
})
