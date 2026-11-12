"""Launch limits. PURE CODE: no model output is ever read here.

Limits are inclusive:
  wind_knots <= 25
  temp_c     >= 4
  98 <= fuel_pct <= 100
Any reading outside its limit makes the verdict "no_go".
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

WIND_MAX_KNOTS = 25.0
TEMP_MIN_C = 4.0
FUEL_MIN_PCT = 98.0
FUEL_MAX_PCT = 100.0

# Exposed to the console (GET /api/config) so the UI draws bands from the same constants. None = open-ended.
LIMITS = {
    "wind_knots": {"label": "Wind", "unit": "kn", "min": None, "max": WIND_MAX_KNOTS},
    "temp_c": {"label": "Temperature", "unit": "°C", "min": TEMP_MIN_C, "max": None},
    "fuel_pct": {"label": "Fuel", "unit": "%", "min": FUEL_MIN_PCT, "max": FUEL_MAX_PCT},
}

GO = "go"
NO_GO = "no_go"


@dataclass(frozen=True)
class Violation:
    field: str
    value: float
    limit: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class LimitResult:
    verdict: str
    violations: list[Violation]


def evaluate(wind_knots: float, temp_c: float, fuel_pct: float) -> LimitResult:
    violations: list[Violation] = []
    if not wind_knots <= WIND_MAX_KNOTS:
        violations.append(Violation("wind_knots", wind_knots, "<= 25",
                                    f"Wind {wind_knots} kn exceeds the 25 kn maximum"))
    if not temp_c >= TEMP_MIN_C:
        violations.append(Violation("temp_c", temp_c, ">= 4",
                                    f"Temperature {temp_c} C is below the 4 C minimum"))
    if not (FUEL_MIN_PCT <= fuel_pct <= FUEL_MAX_PCT):
        violations.append(Violation("fuel_pct", fuel_pct, "98-100",
                                    f"Fuel {fuel_pct}% is outside the 98-100% range"))
    return LimitResult(NO_GO if violations else GO, violations)
