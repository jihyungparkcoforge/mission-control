"""Brief-by and cost rules, checked end-to-end through the API."""
from decimal import Decimal

from app.cost import call_cost
from app.llm import FakeModelClient
from tests.conftest import GOOD


def test_api_violation_overrides_low_model_severity(make_client):
    fake = FakeModelClient(responses={"classify": {"subsystem": "weather", "severity": "low", "rationale": "x"}})
    c = make_client(fake)
    r = c.post("/api/reports", json={**GOOD, "wind_knots": 25.1}).json()
    r = c.get(f"/api/reports/{r['id']}").json()
    assert r["model_severity"] == "low"
    assert r["final_severity"] == "high" and r["brief_by_minutes"] == 5

    r = c.post("/api/reports", json=GOOD).json()
    r = c.get(f"/api/reports/{r['id']}").json()
    assert r["final_severity"] == "low" and r["brief_by_minutes"] == 30


def test_report_cost_equals_sum_of_trace_steps(settings, make_client):
    settings.prices["fake-model"] = (Decimal("10"), Decimal("50"))
    c = make_client(FakeModelClient())
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    r = c.get(f"/api/reports/{rid}").json()
    model_steps = [t for t in r["trace"] if t["model"] != "code"]
    for t in model_steps:
        assert t["input_tokens"] > 0 and t["output_tokens"] > 0
        assert Decimal(t["cost_usd"]) == call_cost("fake-model", t["input_tokens"], t["output_tokens"], settings.prices)
    assert Decimal(r["total_cost_usd"]) == sum(Decimal(t["cost_usd"]) for t in r["trace"])
    assert Decimal(r["total_cost_usd"]) > 0


def test_demo_mode_shows_a_simulated_cost_at_the_real_model_price(settings, make_client):
    """A grader without an API key must still see cost computed in code, not $0."""
    c = make_client(FakeModelClient())
    cfg = c.get("/api/config").json()
    assert cfg["demo_mode"] is True and "simulated at gpt-6.1-terra prices" in cfg["cost_basis"]
    rid = c.post("/api/reports", json=GOOD).json()["id"]
    r = c.get(f"/api/reports/{rid}").json()
    terra = settings.prices["gpt-6.1-terra"]
    assert settings.prices["fake-model"] == terra
    for t in (t for t in r["trace"] if t["model"] != "code"):
        assert Decimal(t["cost_usd"]) == call_cost("gpt-6.1-terra", t["input_tokens"], t["output_tokens"], settings.prices)
    assert Decimal(r["total_cost_usd"]) > 0


def test_report_list_carries_each_report_cost(make_client):
    c = make_client(FakeModelClient())
    ids = [c.post("/api/reports", json=GOOD).json()["id"] for _ in range(2)]
    listed = {r["id"]: r["total_cost_usd"] for r in c.get("/api/reports").json()}
    for rid in ids:
        detail = c.get(f"/api/reports/{rid}").json()
        assert Decimal(listed[rid]) == Decimal(detail["total_cost_usd"]) > 0
