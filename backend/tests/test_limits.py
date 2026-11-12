"""Launch limits are plain code: exact on each limit and just past it."""
import pytest

from app.limits import GO, NO_GO, evaluate


def test_nominal_readings_are_go():
    r = evaluate(10, 15, 99)
    assert r.verdict == GO and r.violations == []


@pytest.mark.parametrize("wind,temp,fuel", [
    (25, 15, 99),     # wind exactly at max
    (10, 4, 99),      # temp exactly at min
    (10, 15, 98),     # fuel exactly at min
    (10, 15, 100),    # fuel exactly at max
    (25, 4, 98),      # all on the edge at once
    (0, 4, 100),
])
def test_exactly_on_each_limit_is_go(wind, temp, fuel):
    assert evaluate(wind, temp, fuel).verdict == GO


@pytest.mark.parametrize("wind,temp,fuel,field", [
    (25.1, 15, 99, "wind_knots"),
    (26, 15, 99, "wind_knots"),
    (10, 3.9, 99, "temp_c"),
    (10, 3, 99, "temp_c"),
    (10, 15, 97.9, "fuel_pct"),
    (10, 15, 100.1, "fuel_pct"),
])
def test_just_past_each_limit_is_no_go(wind, temp, fuel, field):
    r = evaluate(wind, temp, fuel)
    assert r.verdict == NO_GO
    assert [v.field for v in r.violations] == [field]


def test_every_violation_is_listed():
    r = evaluate(40, -2, 90)
    assert r.verdict == NO_GO
    assert {v.field for v in r.violations} == {"wind_knots", "temp_c", "fuel_pct"}
    assert all(v.message for v in r.violations)


def test_limits_module_does_not_touch_models():
    import app.limits as limits
    src = open(limits.__file__).read()
    assert "llm" not in src and "openai" not in src.lower() and "pipeline" not in src
