"""Code backstop for hidden instructions. PURE CODE, no model.

The model check (check_injection) is the primary detector; these rules catch the blatant patterns even if
the model misses them. The final injection flag is model OR rules. Neither can change the verdict.
"""
from __future__ import annotations

import re

# Each pattern targets text addressed to an AI or to the launch decision, not ordinary engineering prose.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("override of prior instructions", re.compile(
        r"\b(ignore|disregard|forget|override|bypass)\b[^.\n]{0,40}\b(instruction|prompt|rule|direction|guidance|guideline|order)s?\b",
        re.I)),
    ("override of prior context", re.compile(
        r"\b(ignore|disregard|forget)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier)\b", re.I)),
    # upper-case role labels, or a lower-case one followed by an instruction ("System: pressure nominal" is prose)
    ("impersonated system/assistant role", re.compile(
        r"(^|[\s\[(<])(SYSTEM|ASSISTANT|DEVELOPER)\s*:"
        r"|(?i:\b(system|assistant|developer)\s*:[^.\n]{0,40}\b(you|ignore|set|mark|verdict|approve|instruction)s?\b)")),
    ("role-play prompt", re.compile(r"\byou are now\b|\bact as (an? )?(ai|assistant|system)\b|\bsystem prompt\b", re.I)),
    ("attempt to dictate the verdict", re.compile(
        r"\b(set|mark|change|make|declare|flip)\b[^.\n]{0,30}\b(verdict|status|launch|report|decision)\b"
        r"[^.\n]{0,20}\b(go|approved?|nominal|green)\b", re.I)),
    ("attempt to approve", re.compile(r"\b(auto-?)?approve\b[^.\n]{0,25}\b(this|the)\b[^.\n]{0,15}\b(briefing|report)\b", re.I)),
    ("attempt to approve", re.compile(r"\b(auto-?)?approve\s+(this|it|now|immediately|at once)\b", re.I)),
    ("asserted verdict", re.compile(
        r"\b(verdict|status|launch|decision|call)\s*(\bis\b|=|:|\bshould be\b)\s*(a\s+)?(go|approved|green)\b", re.I)),
    ("text addressed to an AI", re.compile(
        r"(^|[.!?;:]\s*)(hey\s+|dear\s+)?(assistant|ai|model|llm|chatbot|bot|reviewer|drafter)\s*[,:]"
        r"|\b(note|message|instruction)s?\s+(to|for)\s+(the\s+|any\s+)?(ai|assistant|model|llm|bot|reviewer|drafter|system)\b",
        re.I)),
    ("role-play prompt", re.compile(r"\b(pretend|imagine)\s+(you('| a)re|to be|that you)\b", re.I)),
    ("attempt to approve", re.compile(
        r"\bsign(ed)?[\s-]?off\b[^.\n]{0,20}\b(briefing|report|verdict|launch)\b"
        r"|\b(already\s+)?(okay(ed)?|ok'?d|rubber[\s-]?stamped)\s+(it|this)\b", re.I)),
    ("attempt to dictate the summary", re.compile(
        r"\b(summari[sz]e|write|describe|mark|say)\b[^.\n]{0,30}"
        r"\b(all[\s-]?clear|everything is (fine|ok|okay|nominal|good)|no issues|nothing to report)\b", re.I)),
    ("request to suppress a warning", re.compile(
        r"\b(skip|omit|drop|remove|leave out|hide|suppress)\b[^.\n]{0,25}\b(warning|flag|injection|violation|check)s?\b", re.I)),
    ("attempt to dictate the verdict", re.compile(
        r"\btreat\b[^.\n]{0,30}\bas\s+(a\s+)?(go|nominal|approved|green|fine|cleared)\b", re.I)),
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
