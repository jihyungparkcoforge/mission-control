"""Brief-by time. PURE CODE.

final severity = "high" if any limit violation, else the model's severity.
If classification failed (model_severity is None) the safe default is "high".
"""
from __future__ import annotations

BRIEF_BY_MINUTES = {"high": 5, "medium": 15, "low": 30}
SEVERITIES = tuple(BRIEF_BY_MINUTES)


def final_severity(model_severity: str | None, has_violation: bool) -> str:
    if has_violation or model_severity not in BRIEF_BY_MINUTES:
        return "high"
    return model_severity


def brief_by_minutes(model_severity: str | None, has_violation: bool) -> tuple[str, int]:
    sev = final_severity(model_severity, has_violation)
    return sev, BRIEF_BY_MINUTES[sev]
