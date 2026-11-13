"""Classification uses a structured schema, is checked in code, and invalid values fall back safely."""
import pytest

from app.llm import FakeModelClient
from app.schemas import CLASSIFICATION_SCHEMA
from tests.conftest import GOOD


def _run(make_client, classify_reply, **overrides):
    c = make_client(FakeModelClient(responses={"classify": classify_reply}))
    rid = c.post("/api/reports", json={**GOOD, **overrides}).json()["id"]
    return c.get(f"/api/reports/{rid}").json()


def test_schema_is_strict_enum():
    assert CLASSIFICATION_SCHEMA["additionalProperties"] is False
    assert set(CLASSIFICATION_SCHEMA["required"]) == {"subsystem", "severity", "rationale"}
    assert "unclassified" not in CLASSIFICATION_SCHEMA["properties"]["subsystem"]["enum"]


def test_valid_reply_is_used(make_client):
    r = _run(make_client, {"subsystem": "propulsion", "severity": "medium", "rationale": "valve"})
    assert r["subsystem"] == "propulsion"
    assert r["model_severity"] == "medium" and r["final_severity"] == "medium"
    assert r["brief_by_minutes"] == 15
    assert r["classification_error"] is None


@pytest.mark.parametrize("bad_reply", [
    "this is not json",
    {"subsystem": "plumbing", "severity": "medium", "rationale": "x"},      # out-of-enum subsystem
    {"subsystem": "propulsion", "severity": "catastrophic", "rationale": "x"},  # out-of-enum severity
    {"subsystem": "propulsion"},                                            # missing fields
    RuntimeError("API down"),                                               # call itself fails
])
def test_invalid_reply_falls_back_safely_and_shows_error(make_client, bad_reply):
    r = _run(make_client, bad_reply)
    assert r["subsystem"] == "unclassified"
    assert r["model_severity"] is None
    assert r["final_severity"] == "high" and r["brief_by_minutes"] == 5   # safe default: earliest briefing
    assert r["classification_error"]
    card = next(t for t in r["trace"] if t["step"] == "classify")
    assert card["status"] == "error" and card["error"]
    # the rest of the pipeline continues and the code verdict is untouched
    assert r["verdict"] == "go"
    assert r["status"] == "pending_approval"


def test_a_partly_valid_reply_is_discarded_as_a_whole(make_client):
    """Intentional: if any part of the reply breaks the schema, no part of it is trusted. A valid "low" severity
    next to an invented subsystem is not kept; the report gets the safe default (high, 5 min) and an error card."""
    r = _run(make_client, {"subsystem": "hydraulics", "severity": "low", "rationale": "x"})
    assert r["subsystem"] == "unclassified" and r["model_severity"] is None
    assert r["final_severity"] == "high" and r["brief_by_minutes"] == 5      # not "low" / 30
