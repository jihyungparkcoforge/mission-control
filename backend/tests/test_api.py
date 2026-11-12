"""Filing: all fields, clear rejection messages, persistence across restart."""
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.llm import FakeModelClient, OpenAIClient
from app.main import create_app
from tests.conftest import FD, GOOD


def test_file_report_saves_all_fields(make_client):
    c = make_client()
    res = c.post("/api/reports", json=GOOD)
    assert res.status_code == 201
    r = c.get(f"/api/reports/{res.json()['id']}").json()
    for k, v in GOOD.items():
        assert r[k] == v
    assert r["verdict"] == "go" and r["status"] == "pending_approval"


@pytest.mark.parametrize("field", list(GOOD))
def test_missing_field_rejected_with_message(make_client, field):
    body = {k: v for k, v in GOOD.items() if k != field}
    res = make_client().post("/api/reports", json=body)
    assert res.status_code == 422
    err = res.json()["errors"][0]
    assert err["field"] == field and err["message"].endswith("is required")
    assert err["label"] in res.json()["message"]


@pytest.mark.parametrize("field,value", [
    ("wind_knots", "windy"), ("wind_knots", -1), ("wind_knots", 201),
    ("temp_c", -81), ("temp_c", 81), ("fuel_pct", -0.1), ("fuel_pct", 120.1),
    ("name", "   "), ("note", ""),
])
def test_impossible_values_rejected(make_client, field, value):
    res = make_client().post("/api/reports", json={**GOOD, field: value})
    assert res.status_code == 422
    err = res.json()["errors"][0]
    assert err["field"] == field and err["message"].startswith(err["label"])
    assert "Input should" not in err["message"]                      # no raw Pydantic wording


@pytest.mark.parametrize("field,value", [("wind_knots", 40), ("fuel_pct", 100.1), ("temp_c", -10)])
def test_out_of_limit_but_possible_values_are_saved_as_no_go(make_client, field, value):
    res = make_client().post("/api/reports", json={**GOOD, field: value})
    assert res.status_code == 201 and res.json()["verdict"] == "no_go"


def test_reports_survive_restart(settings):
    app1 = create_app(settings, FakeModelClient())
    with TestClient(app1) as c1:
        rid = c1.post("/api/reports", json=GOOD).json()["id"]
        c1.post(f"/api/reports/{rid}/approve", json={"approver": "FD Kim"}, headers=FD)
    del app1, c1

    app2 = create_app(settings, FakeModelClient())   # new process, same DB file
    with TestClient(app2) as c2:
        r = c2.get(f"/api/reports/{rid}").json()
        assert r["name"] == GOOD["name"] and r["note"] == GOOD["note"]
        assert r["status"] == "approved" and r["decided_by"] == "FD Kim"
        assert len(r["trace"]) > 0
        assert [x["id"] for x in c2.get("/api/reports").json()] == [rid]


def test_reports_survive_a_real_process_restart(settings):
    """File a report in this process, then read it back from a brand-new Python process on the same DB file."""
    import json
    import subprocess
    import sys
    from pathlib import Path

    with TestClient(create_app(settings, FakeModelClient())) as c:
        rid = c.post("/api/reports", json=GOOD).json()["id"]
    code = (
        "import json, sys\n"
        "from fastapi.testclient import TestClient\n"
        "from app.config import Settings\n"
        "from app.llm import FakeModelClient\n"
        "from app.main import create_app\n"
        f"c = TestClient(create_app(Settings(db_path={settings.db_path!r}), FakeModelClient()))\n"
        f"print(json.dumps(c.get('/api/reports/{rid}').json()))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).resolve().parents[1],
                         capture_output=True, text=True, timeout=60, check=True).stdout
    r = json.loads(out.strip().splitlines()[-1])
    assert r["id"] == rid and r["name"] == GOOD["name"] and r["note"] == GOOD["note"]
    assert r["verdict"] == "go" and r["status"] == "pending_approval" and r["trace"]


def test_restart_marks_interrupted_runs_as_error(settings):
    from app.db import Database
    db = Database(settings.db_path)
    rid = db.insert_report({**GOOD, "created_at": 0, "status": "processing", "verdict": "go",
                            "violations_json": "[]"})
    c = TestClient(create_app(settings, FakeModelClient()))
    r = c.get(f"/api/reports/{rid}").json()
    assert r["status"] == "error" and "restart" in r["error_message"]
    c.post(f"/api/reports/{rid}/rerun", headers=FD)
    assert c.get(f"/api/reports/{rid}").json()["status"] == "pending_approval"


def test_config_reports_demo_mode(make_client):
    assert make_client().get("/api/config").json()["demo_mode"] is True


def test_config_exposes_the_code_limits(make_client):
    from app.limits import FUEL_MAX_PCT, FUEL_MIN_PCT, TEMP_MIN_C, WIND_MAX_KNOTS
    limits = make_client().get("/api/config").json()["limits"]
    assert limits["wind_knots"]["max"] == WIND_MAX_KNOTS and limits["wind_knots"]["min"] is None
    assert limits["temp_c"]["min"] == TEMP_MIN_C and limits["temp_c"]["max"] is None
    assert (limits["fuel_pct"]["min"], limits["fuel_pct"]["max"]) == (FUEL_MIN_PCT, FUEL_MAX_PCT)


def test_create_app_picks_client_from_key(tmp_path):
    demo = create_app(Settings(db_path=str(tmp_path / "a.db")))
    assert demo.state.pipeline.client.model == "fake-model"
    real = create_app(Settings(db_path=str(tmp_path / "b.db"), openai_api_key="sk-test-not-real"))
    assert isinstance(real.state.pipeline.client, OpenAIClient)


@pytest.mark.parametrize("raw,expected", [
    ('NaN', "finite number"), ('Infinity', "finite number"), ('-Infinity', "finite number"),
    ('"12"', "must be a number"), ('true', "must be a number"), ('null', "must be a number"),
])
def test_non_finite_or_non_numeric_readings_get_a_precise_message(make_client, raw, expected):
    import json as _json
    body = _json.dumps({**GOOD, "wind_knots": 0}).replace('"wind_knots": 0', f'"wind_knots": {raw}')
    res = make_client().post("/api/reports", content=body, headers={"Content-Type": "application/json"})
    assert res.status_code == 422
    err = res.json()["errors"][0]
    assert err["field"] == "wind_knots" and expected in err["message"]
    assert "less than or equal" not in res.json()["message"]


def test_integer_readings_are_still_accepted(make_client):
    res = make_client().post("/api/reports", json={**GOOD, "wind_knots": 25, "temp_c": 4, "fuel_pct": 100})
    assert res.status_code == 201 and res.json()["verdict"] == "go"


@pytest.mark.parametrize("field,value,text", [
    ("wind_knots", 201, "Wind (kn) must be 200 or less"),
    ("temp_c", -81, "Temp (°C) must be -80 or more"),
    ("fuel_pct", "abc", "Fuel (%) must be a number"),
    ("name", "  ", "Name must not be blank"),
])
def test_rejection_messages_use_form_labels_and_plain_english(make_client, field, value, text):
    res = make_client().post("/api/reports", json={**GOOD, field: value})
    assert res.status_code == 422
    assert res.json()["errors"][0]["message"] == text
    assert res.json()["message"] == f"Report not filed: {text}"
