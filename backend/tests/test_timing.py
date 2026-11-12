"""Brief-by time follows severity; any violation counts as high."""
import pytest

from app.timing import brief_by_minutes


@pytest.mark.parametrize("sev,expected", [("high", 5), ("medium", 15), ("low", 30)])
def test_time_follows_severity(sev, expected):
    assert brief_by_minutes(sev, has_violation=False) == (sev, expected)


@pytest.mark.parametrize("sev", ["high", "medium", "low", None])
def test_violation_forces_high(sev):
    assert brief_by_minutes(sev, has_violation=True) == ("high", 5)


@pytest.mark.parametrize("bad", [None, "critical", "", "LOW"])
def test_unknown_severity_falls_back_to_high(bad):
    assert brief_by_minutes(bad, has_violation=False) == ("high", 5)
