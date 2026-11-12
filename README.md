# Mission Control — Go/No-Go Launch Console

Engineers file anomaly reports; a pipeline sorts them with a model, checks the launch limits **in plain
code**, runs three model checks concurrently, drafts and reviews a briefing, and a **human Flight Director**
approves it.

## Run

```bash
docker compose up --build
```

Open http://localhost:8000. If port 8000 is taken, run `PORT=8088 docker compose up --build`.

- Without `OPENAI_API_KEY`, the app runs in **DEMO MODE** with a deterministic fake model, shown in a yellow banner.
- With a real key: put `OPENAI_API_KEY=sk-...` in a `.env` file at the repo root (git-ignored) and run the same
  command. Default model is `gpt-6.1-terra`; override with `OPENAI_MODEL` (and `MODEL_PRICE_INPUT` /
  `MODEL_PRICE_OUTPUT`, USD per 1M tokens, if the model is not in `backend/app/config.py`).
- Flight Director token (needed to approve, reject, regenerate or re-run; enter it in a report's
  **Flight Director decision** section and click **Unlock**):
  - **Demo mode:** the public demo token `flight-director`, so the approval flow can be tried.
  - **With a real API key:** set a private `FD_TOKEN` in `.env`. If it is unset, the app generates a one-time token
    and prints it in the server log (`docker compose logs app | grep "FD token"`). The public demo token is refused.

## Test

```bash
docker compose run --rm --build test
```

Runs backend pytest and frontend vitest in a container with `network_mode: none` and no API key.
Every model call goes through `ModelClient` (`backend/app/llm.py`), and tests use `FakeModelClient`.
Locally, without Docker: `sh scripts/run-tests.sh` (after `uv sync` in `backend/` and `npm ci` in `frontend/`).
Coverage: `cd backend && uv run pytest --cov` (line + branch) · `cd frontend && npx vitest run --coverage`.

## How it works

| Question | Answer |
|---|---|
| Where is data stored? | SQLite file `/data/mission_control.db` in the Docker volume `mc-data` (tables `reports`, `trace_steps`). |
| Where is the verdict computed? | `backend/app/limits.py`, pure code, before any model call. Limits are inclusive: wind ≤ 25 kn, temp ≥ 4 °C, 98 ≤ fuel ≤ 100 %. |
| Where is brief-by computed? | `backend/app/timing.py`: high 5 / medium 15 / low 30 min; any violation means high. |
| How many model calls? | 1 classify + 3 concurrent checks + 1–3 rounds of (draft + review). That is 6 to 10 per run. |
| What if a model call fails? | **Classify:** red error card, safe default `unclassified` + `high` (5 min), pipeline continues. **Any check, draft, or review:** pipeline stops with `status=error` and no briefing (an unverified briefing could look verified). The code verdict is always shown. FD can re-run. |
| Hidden instructions in the note? | Flagged by the injection check, marked `needs_review`, and shown as a warning. The FD must acknowledge before approving. The verdict can't change because no model output reaches `limits.py`. |
| Review loop? | At most 3 rounds, and reviewer feedback is added to the next draft prompt. If all 3 fail the status is `review_failed`, which can't be approved; the FD can regenerate. |
| Who can approve? | Only `POST /api/reports/{id}/approve` with a valid `X-FD-Token` and approver name, from `pending_approval`. The pipeline has no code path to `approved`. |
| Cost? | `backend/app/cost.py`: tokens × price per step (Decimal). The report total is the sum of its trace cards. |

## Layout

```
backend/app/   main.py (API) · limits.py · timing.py · cost.py · llm.py (ModelClient + fake)
               pipeline.py · prompts.py · schemas.py · db.py · config.py
backend/tests/ test_limits · test_timing · test_classify · test_injection · test_review_loop
               test_approval · test_cost · test_api (incl. restart test)
frontend/src/  App · FileReportForm · ReportList · ReportDetail · TraceCard · console.test.tsx
docs/tool-choices.md   tool choices (reason / rejected alternative / customer concern)
DECISIONS.md · plan.md decision log and implementation plan
```
