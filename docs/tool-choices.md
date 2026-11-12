# Tool Choices

Each choice lists a specific reason, one rejected alternative, and one customer concern with our answer.

## Back end — FastAPI (Python 3.11)
- **Reason:** Pydantic validates the report form and returns a clear per-field 422 message for bad input
  automatically, and the same library validates the model's structured replies. pytest makes the
  boundary tests (25 vs 25.1 knots, etc.) short and readable.
- **Rejected alternative:** Node + Express — validation, schema checking, and async orchestration would
  have to be stitched together from several extra libraries.
- **Customer concern:** "Who can audit the launch verdict logic?" — The verdict is one pure function in one
  file (`backend/app/limits.py`) with no model involvement, readable in a minute and covered by boundary tests.

## Front end — React + Vite + TypeScript
- **Reason:** The console has a lot of changing state — the report list, trace cards that fill in as each
  pipeline step finishes, and approve/reject/regenerate buttons that depend on status. A component model fits this well.
- **Rejected alternative:** Server-rendered Jinja + htmx — simpler, but live card updates and switching
  between engineer and Flight Director actions become awkward.
- **Customer concern:** "Will the screen confuse people under time pressure?" — The GO / NO-GO verdict is the
  largest element at the top of each report and is color-coded; brief-by time sits next to it.

## Database — SQLite
- **Reason:** The whole record — reports, verdicts, trace steps, costs, and who approved what — is one file.
  Copying that file after the launch preserves a complete audit trail.
- **Rejected alternative:** Plain JSON files — risk of corruption on concurrent writes and no transactions.
- **Customer concern:** "Where is our data stored, and does it leave the site?" — In a local SQLite file on a
  Docker volume. The only data sent out is the report note and readings, to the model API; the verdict
  is computed locally and does not depend on that call.

## Model — OpenAI `gpt-6.1-terra` for every step
- **Reason:** Structured Outputs (strict JSON schema) forces the shape of the classification, check, draft and
  review replies, which our code then validates. Terra is a mid-tier model: on real reports (valve delay, wind and
  temperature violation, fuel violation with a hidden instruction) it classified correctly, caught every hidden
  instruction, and wrote briefings with no invented facts, at about $0.005 per report and ~15 s.
- **Rejected alternative:** `gpt-6-astra` (the flagship). We ran the same three reports on both. Astra was a
  little more thorough — it rated the wind/temperature report `high` itself (Terra said `medium`, which code
  raises to `high` anyway because of the violations) and listed one more hidden-instruction phrase (the fake
  "SYSTEM:" label) — but every outcome the Flight Director sees was identical: same verdicts, same brief-by times,
  same injection flags, accurate briefings. Astra cost about 8× more per report (~$0.037 vs ~$0.0045). That
  extra power is overkill for sorting and summarising a short note.
- **Customer concern:** "Is a mid-tier model safe enough for a launch decision?" — The model never makes the
  launch decision. The GO/NO-GO verdict and brief-by time are plain code; the model only sorts and drafts. Every
  draft is checked by a second review call (up to 3 rounds), and nothing is approved until a human Flight
  Director approves it. Switching to a stronger model is a single setting (`OPENAI_MODEL`).
