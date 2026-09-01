"""PII detection and redaction (regex-based MVP).

Swap in an NER model behind the PIIDetector protocol without touching consumers.
The regex set covers the common direct identifiers; everything else falls back
to the aggregating annotation rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import DataClassification, PIIMatch, PIIType
from .ports import ClassificationAnnotator, PIIDetector


@dataclass(frozen=True)
class _Pattern:
    pii_type: PIIType
    regex: re.Pattern[str]


_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(PIIType.EMAIL, re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    _Pattern(PIIType.PHONE, re.compile(r"\+?\d[\d\s().-]{7,}\d")),
    _Pattern(PIIType.SSN, re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    _Pattern(
        PIIType.CREDIT_CARD,
        re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    ),
    _Pattern(PIIType.IP_ADDRESS, re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
)


class RegexPIIDetector(PIIDetector):
    """Detects emails, phones, SSNs, credit cards, and IPs via regex."""

    def detect(self, text: str) -> list[PIIMatch]:
        matches: list[PIIMatch] = []
        for pattern in _PATTERNS:
            for match in pattern.regex.finditer(text):
                matches.append(
                    PIIMatch(
                        pii_type=pattern.pii_type,
                        start=match.start(),
                        end=match.end(),
                        redacted_value=self._mask(match.group(0)),
                    )
                )
        return sorted(matches, key=lambda m: (m.start, m.end))

    def redact(self, text: str) -> str:
        pieces: list[str] = []
        cursor = 0
        for match in self.detect(text):
            pieces.append(text[cursor : match.start])
            pieces.append(match.redacted_value)
            cursor = match.end
        pieces.append(text[cursor:])
        return "".join(pieces)

    @staticmethod
    def _mask(value: str) -> str:
        return f"<REDACTED:{'*' * len(value)}>"


class DefaultClassificationAnnotator(ClassificationAnnotator):
    """Annotates data by what it contains: explicit classification wins, then PII."""

    def __init__(self, detector: PIIDetector | None = None) -> None:
        self._detector = detector or RegexPIIDetector()

    def classify(self, data: dict[str, object]) -> DataClassification:
        explicit = data.get("classification")
        if isinstance(explicit, (DataClassification, str)) and explicit:
            try:
                return DataClassification(explicit)
            except ValueError:
                pass
        serialized = _stringify(data)
        if self._detector.detect(serialized):
            return DataClassification.RESTRICTED
        if data.get("tenant") or data.get("organization"):
            return DataClassification.CONFIDENTIAL
        return DataClassification.INTERNAL


def _stringify(data: dict[str, object]) -> str:
    pieces: list[str] = []
    for _key, value in data.items():
        if isinstance(value, str):
            pieces.append(value)
        else:
            pieces.append(str(value))
    return " ".join(pieces)


__all__ = ["DefaultClassificationAnnotator", "RegexPIIDetector"]
