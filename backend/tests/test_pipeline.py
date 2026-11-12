"""Pipeline-level behaviour, without the HTTP layer: concurrency and crash safety."""
from app.db import Database
from app.llm import FakeModelClient
from app.pipeline import Pipeline
from tests.conftest import GOOD


def _insert(db: Database, **extra) -> int:
    return db.insert_report({**GOOD, "created_at": 0, "status": "processing", "verdict": "go",
                             "violations_json": "[]", **extra})


async def test_three_checks_run_at_the_same_time(make_pipeline, settings):
    fake = FakeModelClient(delay=0.3)
    pipeline, db = make_pipeline(fake)
    from app.limits import evaluate
    lim = evaluate(10, 15, 99)
    rid = db.insert_report({**GOOD, "created_at": 0, "status": "processing", "verdict": lim.verdict,
                            "violations_json": "[]"})
    await pipeline.run_full(rid)
    checks = [t for t in db.get_trace(rid) if t["step"].startswith("check_")]
    assert len(checks) == 3
    # all three started before any of them finished -> they overlapped
    assert max(t["started_at"] for t in checks) < min(t["ended_at"] for t in checks)
    span = max(t["ended_at"] for t in checks) - min(t["started_at"] for t in checks)
    assert span < 0.6, f"checks took {span:.2f}s; sequential would be ~0.9s"


async def test_unexpected_crash_marks_report_error(settings):
    # A model with no configured price makes cost calculation raise inside the pipeline.
    db = Database(settings.db_path)
    rid = _insert(db)
    await Pipeline(db, FakeModelClient(model="unpriced-model"), settings).run_full(rid)
    r = db.get_report(rid)
    assert r["status"] == "error" and r["error_message"].startswith("Pipeline crashed")


async def test_regenerate_crash_marks_report_error(settings):
    db = Database(settings.db_path)
    rid = _insert(db, status="review_failed")
    await Pipeline(db, FakeModelClient(model="unpriced-model"), settings).regenerate(rid)
    r = db.get_report(rid)
    assert r["status"] == "error" and "Pipeline crashed" in r["error_message"]
