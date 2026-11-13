"""Code check that a drafted briefing agrees with the code-computed verdict. PURE CODE, no model.

The reviewer model is the main quality gate; this backstop guarantees that a briefing which states the opposite
verdict (or none) can never reach the Flight Director as "passed".
"""
from __future__ import annotations

import re

from .limits import GO, NO_GO

_NO_GO = re.compile(r"\bno[\s_-]?go\b", re.I)
_GO = re.compile(r"\bGO\b")          # upper-case GO as a verdict word; ordinary "go" in prose is ignored
# A sentence about what *would* happen ("would be NO-GO if wind rises") is not a statement of the verdict.
_CONDITIONAL = re.compile(r"\b(if|would|could|unless|should|might|may become|in case)\b", re.I)


def _verdict_mentions(summary: str) -> tuple[bool, bool]:
    """(states NO-GO, states GO), ignoring conditional sentences."""
    says_no_go = says_go = False
    for sentence in re.split(r"(?<=[.!?;])\s+", summary):
        if _CONDITIONAL.search(sentence):
            continue
        says_no_go |= bool(_NO_GO.search(sentence))
        says_go |= bool(_GO.search(_NO_GO.sub(" ", sentence)))
    return says_no_go, says_go


def verdict_problem(verdict: str, summary: str) -> str | None:
    """Return a reason the summary disagrees with the verdict, or None if it states the verdict correctly."""
    says_no_go, says_go = _verdict_mentions(summary)
    if verdict == NO_GO:
        if says_go:
            return "The briefing states GO, but the code-computed verdict is NO-GO."
        if not says_no_go:
            return "The briefing must state the code-computed NO-GO verdict."
    elif verdict == GO:
        if says_no_go:
            return "The briefing states NO-GO, but the code-computed verdict is GO."
        if not says_go:
            return "The briefing must state the code-computed GO verdict."
    return None
