"""Brief-by time. PURE CODE.

final severity = "high" if any limit violation or if the note carried hidden instructions (owner decision),
else the model's severity. If classification failed (model_severity is None) the safe default is "high".
"""
from __future__ import annotations

BRIEF_BY_MINUTES = {"high": 5, "medium": 15, "low": 30}
SEVERITIES = tuple(BRIEF_BY_MINUTES)


def final_severity(model_severity: str | None, has_violation: bool, injection_flagged: bool = False) -> str:
    if has_violation or injection_flagged or model_severity not in BRIEF_BY_MINUTES:
        return "high"
    return model_severity


def brief_by_minutes(model_severity: str | None, has_violation: bool,
                     injection_flagged: bool = False) -> tuple[str, int]:
    sev = final_severity(model_severity, has_violation, injection_flagged)
    return sev, BRIEF_BY_MINUTES[sev]
