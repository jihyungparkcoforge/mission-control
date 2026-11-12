"""Failure paths through the API: races, wrong-state actions, review errors."""
from decimal import Decimal

import pytest

from app.llm import FakeModelClient
from tests.conftest import FD, GOOD


def test_review_call_error_halts(make_client):
    c = make_client(FakeModelClient(responses={"review": RuntimeError("rate limited")}))
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    r = c.get(f"/api/reports/{rid}").json()
    assert r["status"] == "error" and "Review round 1" in r["error_message"]
    assert r["briefing"] is None


def test_unknown_report_is_404(make_client):
    c = make_client()
    assert c.get("/api/reports/999").status_code == 404
    assert c.post("/api/reports/999/approve", json={"approver": "FD"}, headers=FD).status_code == 404


def test_concurrent_approval_race_is_refused(make_client):
    """Two FDs approve at once: the second compare-and-set loses and gets 409, not a double approval."""
    c = make_client()
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    db = c.app.state.db
    real = db.transition

    def lose_race(report_id, from_statuses, **fields):
        real(report_id, from_statuses, status="approved", decided_by="Other FD")  # the other FD wins first
        return real(report_id, from_statuses, **fields)

    db.transition = lose_race
    res = c.post(f"/api/reports/{rid}/approve", json={"approver": "FD Kim"}, headers=FD)
    assert res.status_code == 409
    assert db.get_report(rid)["decided_by"] == "Other FD"


@pytest.mark.parametrize("action", ["reject", "regenerate"])
def test_actions_refused_from_wrong_state(make_client, action):
    c = make_client(FakeModelClient(responses={"check_tone": RuntimeError("x")}))   # -> status error
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    body = {"approver": "FD"} if action == "reject" else None
    assert c.post(f"/api/reports/{rid}/{action}", json=body, headers=FD).status_code == 409


def test_rejected_briefing_can_be_regenerated(make_client):
    c = make_client()
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    c.post(f"/api/reports/{rid}/reject", json={"approver": "FD", "reason": "vague"}, headers=FD)
    c.post(f"/api/reports/{rid}/regenerate", headers=FD)
    r = c.get(f"/api/reports/{rid}").json()
    assert r["status"] == "pending_approval" and r["decided_by"] is None and r["run_count"] == 2


def test_unpriced_model_refused_at_startup(settings):
    from app.main import create_app
    with pytest.raises(RuntimeError, match="No price configured"):
        create_app(settings, FakeModelClient(model="unpriced-model"))


def test_trace_cost_uses_requested_model_price(settings, make_client):
    settings.prices["fake-model"] = (Decimal("1"), Decimal("1"))
    c = make_client()
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    r = c.get(f"/api/reports/{rid}").json()
    assert all(t["status"] == "ok" for t in r["trace"])
    assert Decimal(r["total_cost_usd"]) > 0
