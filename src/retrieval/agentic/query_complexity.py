"""G-1 QueryComplexityAgent — Agentic RAG Step #4 "Need More Details?"

쿼리가 단일 retrieval로 충분한지, 분해 필요한지 판단.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ComplexityVerdict:
    is_complex: bool
    subqueries: Optional[list[str]] = None  # is_complex=True면 2~5개
    reasoning: str = ""
    confidence: float = 1.0
    method: str = "rule_based"  # "rule_based" | "gemini"


_DECOMPOSE_PROMPT = """당신은 Agentic RAG 시스템의 Query Complexity Judge입니다.
사용자 질의가 단일 retrieval로 충분한지(simple), 서브 쿼리 분해가 필요한지(complex) 판단하세요.

원칙:
- 단일 SNOMED 개념·용어 질의 → simple
- 2개 이상 개념 비교·관계·복합 조건 포함 → complex
- complex면 {max_subqueries}개 이하 원자 서브 쿼리로 분해 (각 서브 쿼리는 단일 답변 가능해야 함)

질의: {query}

JSON만 출력 (다른 텍스트 금지):
{{
  "is_complex": true/false,
  "subqueries": ["...", "..."] or null,
  "reasoning": "판단 근거 1-2문장",
  "confidence": 0.0~1.0
}}
"""


_COMPLEX_KEYWORDS = [
    "and", "or", "vs", "versus", "compare", "comparison", "difference",
    "와", "과", "그리고", "또는", "비교", "차이", "동반", "관계",
]


class QueryComplexityAgent:
    """Agentic RAG #4 Need More Details? 판단 에이전트.

    Gemini flash-lite 기본. 503·파싱 실패 시 rule-based 폴백.
    """

    def __init__(
        self,
        backend: str = "gemini-2.5-flash-lite",
        max_subqueries: int = 5,
    ):
        self.backend = backend
        self.max_subqueries = max_subqueries

    def judge(self, query: str) -> ComplexityVerdict:
        """쿼리 복잡도 판정."""
        # Rule-based fallback 결과를 먼저 준비 (Gemini 실패 시 즉시 반환)
        fallback = self._rule_based(query)

        if self.backend.startswith("gemini"):
            try:
                return self._gemini_judge(query, fallback)
            except Exception as e:
                fallback.reasoning = f"Gemini 실패({type(e).__name__}) → rule_based"
                fallback.method = "rule_based_fallback"
                return fallback

        return fallback

    def _rule_based(self, query: str) -> ComplexityVerdict:
        """규칙 기반 판정: 길이 + 키워드."""
        q_lower = query.lower()
        q_len = len(query)
        # 짧고 단일 개념 → simple
        is_short = q_len < 40
        has_complex_kw = any(kw in q_lower for kw in _COMPLEX_KEYWORDS)

        if is_short and not has_complex_kw:
            return ComplexityVerdict(
                is_complex=False,
                subqueries=None,
                reasoning=f"짧은 단일 개념 쿼리 (len={q_len}, complex_kw=False)",
                confidence=0.85,
                method="rule_based",
            )

        # 복합 조건으로 추정되나 분해 서브쿼리는 rule로 생성 불가 → is_complex=True but subqueries=None
        return ComplexityVerdict(
            is_complex=True,
            subqueries=None,
            reasoning=f"복합 키워드 감지 또는 장문 (len={q_len}, complex_kw={has_complex_kw})",
            confidence=0.6,
            method="rule_based",
        )

    def _gemini_judge(self, query: str, fallback: ComplexityVerdict) -> ComplexityVerdict:
        """Gemini flash-lite 판정."""
        from google import genai  # lazy import

        # .env 로드 (GOOGLE_API_KEY)
        _ensure_env_loaded()

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            fallback.reasoning = "GOOGLE_API_KEY 없음 → rule_based"
            fallback.method = "rule_based_fallback"
            return fallback

        client = genai.Client(api_key=api_key)
        prompt = _DECOMPOSE_PROMPT.format(
            max_subqueries=self.max_subqueries, query=query
        )
        response = client.models.generate_content(model=self.backend, contents=prompt)
        text = (response.text or "").strip()
        # 코드블록 제거
        text = re.sub(r"^```(json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)

        return ComplexityVerdict(
            is_complex=bool(data.get("is_complex", False)),
            subqueries=data.get("subqueries"),
            reasoning=data.get("reasoning", ""),
            confidence=float(data.get("confidence", 0.7)),
            method="gemini",
        )


def _ensure_env_loaded():
    env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
