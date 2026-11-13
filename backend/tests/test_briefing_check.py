"""Code backstop: a briefing that contradicts (or omits) the code verdict never passes review."""
import pytest

from app.briefing_check import verdict_problem
from app.llm import FakeModelClient
from tests.conftest import GOOD


@pytest.mark.parametrize("verdict,summary,ok", [
    ("no_go", "NO-GO: wind 31 kn exceeds the 25 kn limit.", True),
    ("no_go", "No-go because of wind.", True),
    ("no_go", "GO. All readings nominal.", False),                  # opposite verdict
    ("no_go", "NO-GO for wind, but overall GO for launch.", False),  # states both
    ("no_go", "Wind is high.", False),                               # omits the verdict
    ("go", "GO: no limit violations. Valve slow to close.", True),
    ("go", "GO; the crew can go ahead with fuelling.", True),         # ordinary lower-case "go" is fine
    ("go", "NO-GO: valve fault.", False),
    ("go", "Valve slow to close.", False),
])
def test_verdict_problem(verdict, summary, ok):
    assert (verdict_problem(verdict, summary) is None) is ok


def test_go_claiming_draft_for_a_no_go_report_never_reaches_approval(make_client):
    fake = FakeModelClient(responses={
        "draft": {"summary": "GO. All readings nominal.", "recommended_actions": []},
        "review": {"passed": True, "feedback": "Looks good."},          # the reviewer model is fooled
    })
    c = make_client(fake)
    rid = c.post("/api/reports", json={**GOOD, "wind_knots": 31}).json()["id"]
    r = c.get(f"/api/reports/{rid}").json()
    assert r["verdict"] == "no_go"
    assert r["status"] == "review_failed"                              # cannot be approved
    checks = [t for t in r["trace"] if t["step"].startswith("verdict_check_")]
    assert len(checks) == 3 and all(t["output"]["consistent"] is False for t in checks)
    drafts = [call for call in fake.calls if call.step.startswith("draft_")]
    assert "code-computed verdict is NO-GO" in drafts[1].user            # the reason is fed to the next draft


def test_consistent_briefing_passes_on_the_first_round(make_client):
    c = make_client(FakeModelClient())          # demo draft opens with the code verdict
    rid = c.post("/api/reports", json={**GOOD, "wind_knots": 31}).json()["id"]
    r = c.get(f"/api/reports/{rid}").json()
    assert r["status"] == "pending_approval" and r["review_rounds"] == 1
    step = next(t for t in r["trace"] if t["step"] == "verdict_check_1")
    assert step["output"] == {"consistent": True, "problem": None}
