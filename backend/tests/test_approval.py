"""Only a person (Flight Director with token) can approve, and only a pending briefing."""
import pytest

from app.llm import FakeModelClient
from tests.conftest import FD, GOOD


def _pending(make_client):
    c = make_client(FakeModelClient())
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    assert c.get(f"/api/reports/{rid}").json()["status"] == "pending_approval"
    return c, rid



def test_approve_without_token_is_refused(make_client):
    c, rid = _pending(make_client)
    assert c.post(f"/api/reports/{rid}/approve", json={"approver": "x"}).status_code == 401
    assert c.post(f"/api/reports/{rid}/approve", json={"approver": "x"},
                  headers={"X-FD-Token": "wrong"}).status_code == 403
    assert c.get(f"/api/reports/{rid}").json()["status"] == "pending_approval"


def test_approve_requires_name(make_client):
    c, rid = _pending(make_client)
    assert c.post(f"/api/reports/{rid}/approve", json={"approver": ""}, headers=FD).status_code == 422


def test_fd_approves_pending(make_client):
    c, rid = _pending(make_client)
    res = c.post(f"/api/reports/{rid}/approve", json={"approver": "FD Kim"}, headers=FD)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "approved" and body["decided_by"] == "FD Kim"
    # cannot approve twice
    assert c.post(f"/api/reports/{rid}/approve", json={"approver": "FD Kim"}, headers=FD).status_code == 409


def test_cannot_approve_error_report(make_client):
    c = make_client(FakeModelClient(responses={"check_missing": RuntimeError("x")}))
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    assert c.post(f"/api/reports/{rid}/approve", json={"approver": "FD"}, headers=FD).status_code == 409


def test_reject_and_rerun(make_client):
    c, rid = _pending(make_client)
    r = c.post(f"/api/reports/{rid}/reject", json={"approver": "FD", "reason": "too vague"}, headers=FD).json()
    assert r["status"] == "rejected" and r["decision_reason"] == "too vague"
    assert c.post(f"/api/reports/{rid}/rerun", headers=FD).status_code == 409  # rerun only from error


@pytest.mark.parametrize("approver", ["", "   ", "\t \n"])
def test_blank_approver_cannot_approve_or_reject(make_client, approver):
    c, rid = _pending(make_client)
    for action in ("approve", "reject"):
        res = c.post(f"/api/reports/{rid}/{action}", json={"approver": approver}, headers=FD)
        assert res.status_code == 422
        assert res.json()["errors"][0]["message"] == "Flight Director name must not be blank"
    assert c.get(f"/api/reports/{rid}").json()["status"] == "pending_approval"


def test_approver_name_is_stored_trimmed_and_errors_name_the_action(make_client):
    c, rid = _pending(make_client)
    bad = c.post(f"/api/reports/{rid}/approve", json={"approver": " "}, headers=FD).json()
    assert bad["message"].startswith("Approval refused:")
    bad = c.post(f"/api/reports/{rid}/reject", json={"approver": " "}, headers=FD).json()
    assert bad["message"].startswith("Rejection refused:")
    r = c.post(f"/api/reports/{rid}/approve", json={"approver": "  FD Kim  "}, headers=FD).json()
    assert r["status"] == "approved" and r["decided_by"] == "FD Kim"
