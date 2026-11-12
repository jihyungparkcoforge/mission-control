"""Draft/review loop: stops at three rounds, feedback goes into the next draft."""
from app.llm import FakeModelClient
from app.pipeline import MAX_REVIEW_ROUNDS
from tests.conftest import FD, GOOD

FAIL = lambda fb: {"passed": False, "feedback": fb}  # noqa: E731
PASS = {"passed": True, "feedback": "ok"}


def _file(make_client, fake):
    c = make_client(fake)
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    return c, rid, c.get(f"/api/reports/{rid}").json()


def test_loop_stops_at_three_rounds(make_client):
    fake = FakeModelClient(responses={"review": [FAIL("r1"), FAIL("r2"), FAIL("r3"), PASS]})
    c, rid, r = _file(make_client, fake)
    assert MAX_REVIEW_ROUNDS == 3
    assert r["status"] == "review_failed"
    assert r["review_rounds"] == 3
    steps = [t["step"] for t in r["trace"]]
    assert steps.count("draft_1") == 1 and "draft_4" not in steps and "review_4" not in steps
    assert sum(s.startswith("draft_") for s in steps) == 3
    assert sum(s.startswith("review_") for s in steps) == 3


def test_feedback_reaches_next_draft(make_client):
    fake = FakeModelClient(responses={"review": [FAIL("Remove the invented valve serial number"), PASS]})
    c, rid, r = _file(make_client, fake)
    assert r["status"] == "pending_approval" and r["review_rounds"] == 2
    drafts = [call for call in fake.calls if call.step.startswith("draft_")]
    assert len(drafts) == 2
    assert "REVIEWER FEEDBACK" not in drafts[0].user
    assert "Remove the invented valve serial number" in drafts[1].user


def test_review_failed_cannot_be_approved_but_can_regenerate(make_client):
    fake = FakeModelClient(responses={"review": [FAIL("a"), FAIL("b"), FAIL("c"), PASS]})
    c, rid, r = _file(make_client, fake)
    res = c.post(f"/api/reports/{rid}/approve", json={"approver": "FD"}, headers=FD)
    assert res.status_code == 409
    cost_before = r["total_cost_usd"]
    c.post(f"/api/reports/{rid}/regenerate", headers=FD)
    r = c.get(f"/api/reports/{rid}").json()
    assert r["status"] == "pending_approval"
    assert r["run_count"] == 2
    assert float(r["total_cost_usd"]) >= float(cost_before)  # cost accumulates across runs


def test_draft_error_halts(make_client):
    fake = FakeModelClient(responses={"draft": ConnectionError("network")})
    c, rid, r = _file(make_client, fake)
    assert r["status"] == "error" and "Draft round 1" in r["error_message"]
