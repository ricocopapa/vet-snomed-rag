"""PII 정규식 마스킹/복원.

마스킹: LLM 전달 직전 자동 적용
복원: LLM 응답 후 필요 시 적용 (mapping 테이블 기반)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List

PII_PATTERNS = {
    "PHONE": re.compile(r"\b\d{2,3}-\d{3,4}-\d{4}\b"),
    "EMAIL": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "RRN": re.compile(r"\b\d{6}-\d{7}\b"),
    "ACCT": re.compile(r"\b\d{3,}-\d{2,}-\d{6,}\b"),
}


@dataclass
class MaskResult:
    masked_text: str
    mapping: Dict[str, str] = field(default_factory=dict)  # token → original


def mask_pii(text: str) -> MaskResult:
    """텍스트 내 PII 4종 정규식 매칭 → [TYPE_REDACTED_N] 토큰으로 치환."""
    mapping: Dict[str, str] = {}
    counters: Dict[str, int] = {k: 0 for k in PII_PATTERNS}
    masked = text

    # 우선순위: 더 구체적인 패턴부터 (계좌·주민 → 전화 → 이메일)
    order = ["RRN", "ACCT", "PHONE", "EMAIL"]
    for kind in order:
        pattern = PII_PATTERNS[kind]

        def _replace(match: re.Match) -> str:
            counters[kind] += 1
            token = f"[{kind}_REDACTED_{counters[kind]}]"
            mapping[token] = match.group(0)
            return token

        masked = pattern.sub(_replace, masked)

    return MaskResult(masked_text=masked, mapping=mapping)


def unmask_pii(text: str, mapping: Dict[str, str]) -> str:
    """마스킹 결과 복원. 토큰을 원본 문자열로 치환."""
    restored = text
    for token, original in mapping.items():
        restored = restored.replace(token, original)
    return restored
