"""Code backstop for hidden instructions. PURE CODE, no model.

The model check (check_injection) is the primary detector; these rules catch the blatant patterns even if
the model misses them. The final injection flag is model OR rules. Neither can change the verdict.
"""
from __future__ import annotations

import re

# Each pattern targets text addressed to an AI or to the launch decision, not ordinary engineering prose.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override of prior instructions", re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(instruction|prompt|rule|direction)s?\b", re.I)),
    ("override of prior context", re.compile(
        r"\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\b", re.I)),
    ("impersonated system/assistant role", re.compile(r"(^|[\s\[(<])(system|assistant|developer)\s*:", re.I)),
    ("role-play prompt", re.compile(r"\byou are now\b|\bact as (an? )?(ai|assistant|system)\b|\bsystem prompt\b", re.I)),
    ("attempt to dictate the verdict", re.compile(
        r"\b(set|mark|change|make|declare|flip)\b[^.\n]{0,30}\b(verdict|status|launch|report|decision)\b"
        r"[^.\n]{0,20}\b(go|approved?|nominal|green)\b", re.I)),
    ("attempt to approve", re.compile(r"\b(auto-?)?approve\b[^.\n]{0,25}\b(this|the)\b[^.\n]{0,15}\b(briefing|report)\b", re.I)),
    ("request to conceal", re.compile(r"\b(do not|don't|never)\s+(mention|report|reveal|tell|include)\b", re.I)),
    ("request to falsify readings", re.compile(
        r"\breport\b[^.\n]{0,40}\bas\b[^.\n]{0,12}(\bnominal\b|\bnormal\b|\bgo\b|\b100\s?%)", re.I)),
]


def detect_instructions(note: str) -> list[str]:
    """Return one finding per matched rule: '<rule>: "<matched text>"'."""
    findings = []
    for label, pattern in PATTERNS:
        m = pattern.search(note)
        if m:
            findings.append(f'{label}: "{m.group(0).strip()}"')
    return findings
