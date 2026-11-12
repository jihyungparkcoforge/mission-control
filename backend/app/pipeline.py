"""Report pipeline: classify -> 3 concurrent checks -> draft/review loop (max 3 rounds).

The verdict is NOT computed here; it is computed by limits.evaluate() before this pipeline starts
and nothing in this module writes it. This module also never sets the approved status: only the
approve endpoint (a human Flight Director) can do that.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from . import prompts
from .injection import detect_instructions
from .config import Settings
from .cost import call_cost
from .db import Database
from .llm import ModelClient
from .schemas import (CHECK_SCHEMA, CLASSIFICATION_SCHEMA, DRAFT_SCHEMA, REVIEW_SCHEMA, UNCLASSIFIED,
                      CheckResult, Classification, Draft, Review)
from .timing import brief_by_minutes

log = logging.getLogger(__name__)

MAX_REVIEW_ROUNDS = 3
CHECK_STEPS = ("check_injection", "check_missing", "check_tone")

# Statuses the pipeline is allowed to set. The approved and rejected statuses are deliberately absent.
PROCESSING, PENDING_APPROVAL, REVIEW_FAILED, ERROR = "processing", "pending_approval", "review_failed", "error"

T = TypeVar("T", bound=BaseModel)


class Pipeline:
    def __init__(self, db: Database, client: ModelClient, settings: Settings):
        self.db, self.client, self.settings = db, client, settings

    async def _call(self, report_id: int, run: int, step: str, system: str, user: str,
                    schema: dict, schema_name: str, reply_model: type[T]) -> tuple[T | None, str | None]:
        """One model call = one trace card. Returns (parsed reply, None) or (None, error message)."""
        step_id = self.db.start_step(report_id, run, step, self.client.model)
        try:
            res = await self.client.complete(step=step, system=system, user=user,
                                             schema=schema, schema_name=schema_name)
        except Exception as e:  # network, auth, timeout, rate limit...
            msg = f"Model call failed: {type(e).__name__}: {e}"
            self.db.finish_step(step_id, status="error", error=msg)
            return None, msg
        # Price by the model we requested (the API may echo a dated snapshot id).
        cost = call_cost(self.client.model, res.input_tokens, res.output_tokens, self.settings.prices)
        tokens = dict(input_tokens=res.input_tokens, output_tokens=res.output_tokens, cost_usd=str(cost))
        try:
            parsed = reply_model.model_validate_json(res.text)
        except ValidationError as e:
            msg = f"Invalid model reply ({e.error_count()} schema error(s)): {e.errors()[0]['msg']}"
            self.db.finish_step(step_id, status="error", error=msg, output=res.text[:2000], **tokens)
            return None, msg
        self.db.finish_step(step_id, status="ok", output=parsed.model_dump_json(), **tokens)
        return parsed, None

    # ---------------------------------------------------------------- full run
    async def run_full(self, report_id: int) -> None:
        try:
            await self._run_full(report_id)
        except Exception as e:  # never leave a report stuck in "processing"
            log.exception("pipeline crashed")
            self.db.update_report(report_id, status=ERROR, error_message=f"Pipeline crashed: {e}")

    async def _run_full(self, report_id: int) -> None:
        r = self.db.get_report(report_id)
        run = r["run_count"] + 1
        self.db.update_report(report_id, run_count=run, status=PROCESSING, error_message=None,
                              briefing_json=None, review_rounds=0, review_feedback=None,
                              classification_error=None, injection_flag=0, needs_review=0)
        violations = json.loads(r["violations_json"])
        self.db.add_code_step(report_id, run, "limits_check", {"verdict": r["verdict"], "violations": violations})

        # 1) classification (model) -> validated in code, safe default on any error
        cls, err = await self._call(report_id, run, "classify", prompts.CLASSIFY_SYSTEM,
                                    prompts.report_block(r), CLASSIFICATION_SCHEMA, "classification",
                                    Classification)
        if cls is None:
            subsystem, model_sev, classification = UNCLASSIFIED, None, {"subsystem": UNCLASSIFIED}
        else:
            subsystem, model_sev, classification = cls.subsystem, cls.severity, cls.model_dump()

        # 2) brief-by (code)
        final_sev, minutes = brief_by_minutes(model_sev, bool(violations))
        self.db.update_report(report_id, subsystem=subsystem, model_severity=model_sev,
                              final_severity=final_sev, brief_by_minutes=minutes,
                              classification_error=err, classification_json=json.dumps(classification))
        self.db.add_code_step(report_id, run, "brief_by", {
            "model_severity": model_sev, "has_violation": bool(violations),
            "final_severity": final_sev, "brief_by_minutes": minutes,
            "classification_fallback": cls is None})

        # 3) three checks, concurrently
        results = await asyncio.gather(*(
            self._call(report_id, run, name, prompts.CHECK_SYSTEMS[name], prompts.report_block(r),
                       CHECK_SCHEMA, name, CheckResult)
            for name in CHECK_STEPS))
        failed = [f"{name}: {err}" for name, (_, err) in zip(CHECK_STEPS, results) if err]
        if failed:
            self.db.update_report(report_id, status=ERROR, error_message=(
                "Briefing withheld: the report could not be fully verified. " + " | ".join(failed)))
            return
        checks = {name: res.model_dump() for name, (res, _) in zip(CHECK_STEPS, results)}
        # code backstop: blatant instruction patterns are flagged even if the model missed them
        rule_hits = detect_instructions(r["note"])
        checks["injection_rules"] = {"flagged": bool(rule_hits), "findings": rule_hits}
        self.db.add_code_step(report_id, run, "injection_rules", checks["injection_rules"])
        injection = checks["check_injection"]["flagged"] or bool(rule_hits)
        self.db.update_report(report_id, checks_json=json.dumps(checks),
                              injection_flag=int(injection), needs_review=int(injection))

        # 4) draft / review loop
        await self._draft_loop(report_id, run)

    # ---------------------------------------------------------------- regenerate
    async def regenerate(self, report_id: int) -> None:
        try:
            r = self.db.get_report(report_id)
            run = r["run_count"] + 1
            self.db.update_report(report_id, run_count=run, status=PROCESSING, error_message=None,
                                  briefing_json=None, review_rounds=0, review_feedback=None,
                                  decided_by=None, decided_at=None, decision_reason=None)
            await self._draft_loop(report_id, run)
        except Exception as e:
            log.exception("regenerate crashed")
            self.db.update_report(report_id, status=ERROR, error_message=f"Pipeline crashed: {e}")

    async def _draft_loop(self, report_id: int, run: int) -> None:
        r = self.db.get_report(report_id)
        ctx = prompts.context_block(r, json.loads(r["classification_json"]), json.loads(r["checks_json"]))
        previous: dict | None = None
        feedback: str | None = None
        for rnd in range(1, MAX_REVIEW_ROUNDS + 1):
            draft, err = await self._call(report_id, run, f"draft_{rnd}", prompts.DRAFT_SYSTEM,
                                          prompts.draft_user(ctx, previous, feedback), DRAFT_SCHEMA,
                                          "briefing_draft", Draft)
            if err:
                self.db.update_report(report_id, status=ERROR, error_message=f"Draft round {rnd}: {err}")
                return
            review, err = await self._call(report_id, run, f"review_{rnd}", prompts.REVIEW_SYSTEM,
                                           prompts.review_user(ctx, draft.model_dump()), REVIEW_SCHEMA,
                                           "briefing_review", Review)
            if err:
                self.db.update_report(report_id, status=ERROR, error_message=f"Review round {rnd}: {err}")
                return
            self.db.update_report(report_id, briefing_json=draft.model_dump_json(),
                                  review_rounds=rnd, review_feedback=review.feedback)
            if review.passed:
                self.db.update_report(report_id, status=PENDING_APPROVAL)
                return
            previous, feedback = draft.model_dump(), review.feedback
        self.db.update_report(report_id, status=REVIEW_FAILED)
