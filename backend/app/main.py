"""FastAPI app: filing, Flight Director actions, and the console API."""
from __future__ import annotations

import json
import logging
import os
import secrets
import time
from pathlib import Path

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import FAKE_MODEL, Settings
from .cost import total_cost
from .db import Database
from .limits import LIMITS, evaluate
from .llm import FakeModelClient, ModelClient, OpenAIClient
from .pipeline import PENDING_APPROVAL, PROCESSING, Pipeline
from .schemas import ApproveIn, RejectIn, ReportIn

logging.basicConfig(level=logging.INFO)


# Demo mode only: a short per-call delay so the fake behaves like a real API in time, and the trace visibly
# shows the three checks overlapping (instant replies would finish one after another inside the gather).
DEMO_STEP_DELAY_S = 0.15

# Labels match the form so an error names the field the engineer actually sees.
FIELD_LABELS = {"name": "Name", "station": "Station", "wind_knots": "Wind (kn)", "temp_c": "Temp (°C)",
                "fuel_pct": "Fuel (%)", "note": "Note", "approver": "Flight Director name"}


def _num(v) -> str:
    return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)


def _friendly(e: dict) -> str:
    """Plain-English reason for one Pydantic error (falls back to Pydantic's own text)."""
    t, ctx = e.get("type", ""), e.get("ctx") or {}
    if t == "missing":
        return "is required"
    if t == "string_too_short" or (t == "value_error" and "blank" in e.get("msg", "")):
        return "must not be blank"
    if t == "finite_number":
        return "must be a finite number (not NaN or Infinity)"
    if t in ("float_type", "float_parsing", "int_type", "int_parsing"):
        return "must be a number"
    if t == "less_than_equal":
        return f"must be {_num(ctx.get('le'))} or less"
    if t == "greater_than_equal":
        return f"must be {_num(ctx.get('ge'))} or more"
    if t == "string_too_long":
        return f"must be at most {ctx.get('max_length')} characters"
    if t == "extra_forbidden":
        return "is not a field of a report"
    return e.get("msg", "is invalid")


def _serialize(r: dict, trace: list[dict] | None = None) -> dict:
    out = {k: v for k, v in r.items() if not k.endswith("_json")}
    out["violations"] = json.loads(r["violations_json"])
    out["classification"] = json.loads(r["classification_json"]) if r["classification_json"] else None
    out["checks"] = json.loads(r["checks_json"]) if r["checks_json"] else None
    out["briefing"] = json.loads(r["briefing_json"]) if r["briefing_json"] else None
    out["injection_flag"] = bool(r["injection_flag"])
    out["needs_review"] = bool(r["needs_review"])
    out["brief_by_at"] = r["created_at"] + r["brief_by_minutes"] * 60 if r["brief_by_minutes"] else None
    if trace is not None:
        out["trace"] = [{**t, "output": json.loads(t["output"]) if t["output"] and t["status"] == "ok" else t["output"]}
                        for t in trace]
        out["total_cost_usd"] = str(total_cost(t["cost_usd"] for t in trace))
    return out


def create_app(settings: Settings | None = None, client: ModelClient | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if client is None:
        client = (FakeModelClient(delay=DEMO_STEP_DELAY_S) if settings.demo_mode
                  else OpenAIClient(settings.openai_api_key, settings.openai_model))
    cost_basis = (f"simulated at {settings.openai_model} prices (demo mode, no real API calls)" if client.model == FAKE_MODEL
                  else f"{client.model} per-token prices")
    if client.model not in settings.prices:
        raise RuntimeError(f"No price configured for model {client.model!r}; set MODEL_PRICE_INPUT/OUTPUT")
    db = Database(settings.db_path)
    if settings.fd_token_generated:
        # One-time secret for this run, shown only to whoever can read the server log (the operator).
        logging.warning("FD_TOKEN not set: generated a Flight Director token for this run: %s", settings.fd_token)
    recovered = db.recover_interrupted()
    if recovered:
        logging.warning("Marked %d interrupted report(s) as error", recovered)
    pipeline = Pipeline(db, client, settings)

    app = FastAPI(title="Mission Control")
    app.state.db, app.state.pipeline, app.state.settings = db, pipeline, settings

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        errors = []
        for e in exc.errors():
            field = ".".join(str(p) for p in e["loc"] if p != "body") or "body"
            label = FIELD_LABELS.get(field, field)
            errors.append({"field": field, "label": label, "message": f"{label} {_friendly(e)}"})
        summary = "; ".join(e["message"] for e in errors)
        return JSONResponse(status_code=422, content={"message": f"Report not filed: {summary}", "errors": errors})

    def require_fd(x_fd_token: str | None = Header(default=None)) -> None:
        if not x_fd_token:
            raise HTTPException(401, "Flight Director token required (X-FD-Token header)")
        if not secrets.compare_digest(x_fd_token, settings.fd_token):
            raise HTTPException(403, "Invalid Flight Director token")

    def load(report_id: int) -> dict:
        r = db.get_report(report_id)
        if not r:
            raise HTTPException(404, "Report not found")
        return r

    @app.get("/api/config")
    def config():
        return {"demo_mode": settings.demo_mode, "model": client.model, "limits": LIMITS, "cost_basis": cost_basis}

    @app.post("/api/reports", status_code=201)
    def file_report(body: ReportIn, background: BackgroundTasks):
        limits = evaluate(body.wind_knots, body.temp_c, body.fuel_pct)  # code-only verdict, before any model call
        report_id = db.insert_report({
            **body.model_dump(), "created_at": time.time(), "status": PROCESSING,
            "verdict": limits.verdict,
            "violations_json": json.dumps([v.to_dict() for v in limits.violations]),
            # until the model classifies, a violation already fixes the brief-by time
            **({"final_severity": "high", "brief_by_minutes": 5} if limits.violations else {}),
        })
        background.add_task(pipeline.run_full, report_id)
        return _serialize(db.get_report(report_id), db.get_trace(report_id))

    @app.get("/api/reports")
    def list_reports():
        costs = db.step_costs()
        return [{**_serialize(r), "total_cost_usd": str(total_cost(costs.get(r["id"], [])))} for r in db.list_reports()]

    @app.get("/api/reports/{report_id}")
    def get_report(report_id: int):
        return _serialize(load(report_id), db.get_trace(report_id))

    @app.post("/api/reports/{report_id}/approve", dependencies=[Depends(require_fd)])
    def approve(report_id: int, body: ApproveIn):
        r = load(report_id)
        if r["status"] != PENDING_APPROVAL:
            raise HTTPException(409, f"Only a pending briefing can be approved (status is {r['status']})")
        if r["injection_flag"] and not body.acknowledge_injection:
            raise HTTPException(409, "This note contained hidden instructions; acknowledge before approving")
        if not db.transition(report_id, (PENDING_APPROVAL,), status="approved",
                             decided_by=body.approver.strip(), decided_at=time.time(), needs_review=0):
            raise HTTPException(409, "Report changed state; reload and try again")
        return _serialize(load(report_id), db.get_trace(report_id))

    @app.post("/api/reports/{report_id}/reject", dependencies=[Depends(require_fd)])
    def reject(report_id: int, body: RejectIn):
        load(report_id)
        if not db.transition(report_id, (PENDING_APPROVAL, "review_failed"), status="rejected",
                             decided_by=body.approver.strip(), decided_at=time.time(),
                             decision_reason=body.reason):
            raise HTTPException(409, "Only a pending or review-failed briefing can be rejected")
        return _serialize(load(report_id), db.get_trace(report_id))

    @app.post("/api/reports/{report_id}/regenerate", dependencies=[Depends(require_fd)])
    def regenerate(report_id: int, background: BackgroundTasks):
        load(report_id)
        if not db.transition(report_id, ("review_failed", "rejected"), status=PROCESSING):
            raise HTTPException(409, "Only a review-failed or rejected briefing can be regenerated")
        background.add_task(pipeline.regenerate, report_id)
        return _serialize(load(report_id), db.get_trace(report_id))

    @app.post("/api/reports/{report_id}/rerun", dependencies=[Depends(require_fd)])
    def rerun(report_id: int, background: BackgroundTasks):
        load(report_id)
        if not db.transition(report_id, ("error",), status=PROCESSING):
            raise HTTPException(409, "Only a report in error can be re-run")
        background.add_task(pipeline.run_full, report_id)
        return _serialize(load(report_id), db.get_trace(report_id))

    static_dir = Path(os.getenv("STATIC_DIR", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
    return app

