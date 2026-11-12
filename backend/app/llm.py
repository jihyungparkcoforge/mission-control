"""The ONE interface every model call goes through.

OpenAIClient talks to the real API. FakeModelClient is used by all tests (no network, no key)
and by the app in DEMO MODE when OPENAI_API_KEY is not set.
"""
from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol


@dataclass
class ModelResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class ModelClient(Protocol):
    model: str

    async def complete(self, *, step: str, system: str, user: str,
                       schema: dict, schema_name: str) -> ModelResult: ...


class OpenAIClient:
    def __init__(self, api_key: str, model: str):
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=api_key, timeout=60)
        self.model = model

    async def complete(self, *, step: str, system: str, user: str,
                       schema: dict, schema_name: str) -> ModelResult:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_schema",
                             "json_schema": {"name": schema_name, "schema": schema, "strict": True}},
        )
        usage = resp.usage
        return ModelResult(
            text=resp.choices[0].message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            model=resp.model or self.model,
        )


def _tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class FakeCall:
    step: str
    system: str
    user: str


Response = str | dict | Exception | Callable[[str], Any]


@dataclass
class FakeModelClient:
    """Scriptable fake.

    `responses` maps a step kind ("classify", "check_injection", "check_missing", "check_tone",
    "draft", "review") to a str (raw text), dict (JSON-encoded), Exception (raised),
    callable(user_prompt) -> any of those, or a list of those consumed one per call.
    Unscripted steps fall back to deterministic demo heuristics.
    """
    responses: dict[str, Response | list[Response]] = field(default_factory=dict)
    delay: float = 0.0
    model: str = "fake-model"
    calls: list[FakeCall] = field(default_factory=list)

    async def complete(self, *, step: str, system: str, user: str,
                       schema: dict, schema_name: str) -> ModelResult:
        self.calls.append(FakeCall(step, system, user))
        if self.delay:
            await asyncio.sleep(self.delay)
        kind = re.sub(r"_\d+$", "", step)
        if kind in self.responses:
            spec = self.responses[kind]
            if isinstance(spec, list):
                spec = spec.pop(0) if len(spec) > 1 else spec[0]
        else:
            spec = _demo_reply(kind, user)
        if callable(spec) and not isinstance(spec, Exception):
            spec = spec(user)
        if isinstance(spec, Exception):
            raise spec
        text = spec if isinstance(spec, str) else json.dumps(spec)
        return ModelResult(text, _tokens(system + user), _tokens(text), self.model)


# ---------- deterministic demo heuristics (DEMO MODE only; not real AI) ----------

_SUBSYSTEM_KEYWORDS = [
    ("propulsion", ("valve", "engine", "fuel", "lox", "pressure", "tank", "thrust", "propellant")),
    ("communications", ("telemetry", "link", "radio", "comms", "antenna", "signal", "downlink")),
    ("avionics", ("computer", "sensor", "gnc", "flight software", "avionics", "battery", "power")),
    ("weather", ("wind", "cloud", "lightning", "rain", "temperature", "weather", "cold")),
    ("ground_support", ("pad", "tower", "umbilical", "crane", "ground", "hvac", "gse")),
    ("structures", ("crack", "frame", "fairing", "bolt", "structure", "vibration")),
]
_INJECTION = re.compile(r"ignore (all |any )?(previous|prior|above)|system prompt|you are now|"
                        r"set (the )?verdict|mark (it |this )?(as )?go|disregard|override", re.I)


def _note(user: str) -> str:
    m = re.search(r"<note>\n?(.*?)\n?</note>", user, re.S)
    return m.group(1) if m else ""


def _demo_reply(kind: str, user: str) -> dict:
    note = _note(user)
    low = note.lower()
    if kind == "classify":
        subsystem = next((s for s, kws in _SUBSYSTEM_KEYWORDS if any(k in low for k in kws)), "ground_support")
        severity = ("high" if re.search(r"fail|leak|fire|abort|scrub|lost", low)
                    else "medium" if re.search(r"odd|intermittent|drop|anomal|spike|slow", low) else "low")
        return {"subsystem": subsystem, "severity": severity, "rationale": "Demo keyword heuristic."}
    if kind == "check_injection":
        hit = _INJECTION.search(note)
        return {"flagged": bool(hit), "findings": [f"Instruction-like text: '{hit.group(0)}'"] if hit else []}
    if kind == "check_missing":
        missing = []
        if not re.search(r"\d", note):
            missing.append("No time, value, or measurement given")
        if len(note) < 40:
            missing.append("Note is very short; component and impact unclear")
        return {"flagged": bool(missing), "findings": missing}
    if kind == "check_tone":
        panic = re.search(r"!!|\b(PANIC|EMERGENCY|HELP|ASAP)\b|\b[A-Z]{5,}\b", note)
        return {"flagged": bool(panic), "findings": ["Urgent / alarmed wording"] if panic else []}
    if kind == "draft":
        # Never echo instruction-like sentences into the briefing.
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", note) if s.strip()]
        facts = [s for s in sentences if not _INJECTION.search(s)]
        summary = f"Engineer reports: {' '.join(facts[:2])[:300]}" if facts else "Engineer report contains no usable facts."
        if "Injection flag: True" in user:
            summary += " The note also contained instruction-like text, which was ignored."
        return {"summary": summary, "recommended_actions": ["Confirm reading with the reporting station"]}
    if kind == "review":
        return {"passed": True, "feedback": "Demo reviewer: no issues found."}
    raise ValueError(f"unknown step kind {kind}")
