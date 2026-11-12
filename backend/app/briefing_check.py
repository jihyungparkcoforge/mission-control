"""Code check that a drafted briefing agrees with the code-computed verdict. PURE CODE, no model.

The reviewer model is the main quality gate; this backstop guarantees that a briefing which states the opposite
verdict (or none) can never reach the Flight Director as "passed".
"""
from __future__ import annotations

import re

from .limits import GO, NO_GO

_NO_GO = re.compile(r"\bno[\s_-]?go\b", re.I)
_GO = re.compile(r"\bGO\b")          # upper-case GO as a verdict word; ordinary "go" in prose is ignored


def verdict_problem(verdict: str, summary: str) -> str | None:
    """Return a reason the summary disagrees with the verdict, or None if it states the verdict correctly."""
    says_no_go = bool(_NO_GO.search(summary))
    says_go = bool(_GO.search(_NO_GO.sub(" ", summary)))
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
