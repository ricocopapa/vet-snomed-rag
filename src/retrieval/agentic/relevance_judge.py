"""G-3 RelevanceJudgeAgent — Agentic RAG Step #10 "Is the answer relevant?"

생성된 답변이 쿼리에 충분히 관련·정확한지 판정.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional


@dataclass
class RelevanceVerdict:
    verdict: Literal["PASS", "PARTIAL", "FAIL"] = "PARTIAL"
    confidence: float = 0.5
    missing_aspects: list[str] = field(default_factory=list)
    reasoning: str = ""
    method: str = "gemini"  # "gemini" | "fallback"


_JUDGE_PROMPT = """당신은 Agentic RAG 시스템의 Answer Relevance Judge입니다.

[쿼리]
{query}

[생성된 답변]
{answer}

[검색된 SNOMED 개념 (Top {top_n})]
{retrieved_summary}

판정 기준:
- PASS: 답변이 쿼리의 모든 핵심 요구를 충족. 검색 결과와 일치.
- PARTIAL: 일부 누락 또는 불명확. 추가 retrieval 필요.
- FAIL: 전혀 관련 없음 또는 완전히 틀림.

JSON만 출력 (다른 텍스트 금지):
{{
  "verdict": "PASS" | "PARTIAL" | "FAIL",
  "confidence": 0.0~1.0,
  "missing_aspects": ["...", "..."],
  "reasoning": "1-2문장 근거"
}}
"""


class RelevanceJudgeAgent:
    """Agentic RAG #10 Relevance Judge.

    Gemini flash-lite 기본. 503·파싱 실패 시 PARTIAL/confidence=0.5 폴백 (안전 기본).
    """

    def __init__(self, backend: str = "gemini-3.1-flash-lite-preview"):
        self.backend = backend

    def judge(
        self,
        query: str,
        answer: str,
        retrieved_concepts: Optional[list[dict]] = None,
    ) -> RelevanceVerdict:
        """쿼리·답변·검색 결과 3자 기반 관련성 판정."""
        # 빈 답변 즉시 FAIL
        if not answer or not answer.strip():
            return RelevanceVerdict(
                verdict="FAIL",
                confidence=1.0,
                missing_aspects=["empty_answer"],
                reasoning="답변이 비어 있음",
                method="rule_based",
            )

        if self.backend.startswith("gemini"):
            try:
                return self._gemini_judge(query, answer, retrieved_concepts or [])
            except Exception as e:
                return RelevanceVerdict(
                    verdict="PARTIAL",
                    confidence=0.5,
                    missing_aspects=[f"judge_error:{type(e).__name__}"],
                    reasoning=f"Gemini judge 실패 → 안전 폴백 PARTIAL/0.5",
                    method="fallback",
                )

        # 기본 폴백
        return RelevanceVerdict(
            verdict="PARTIAL",
            confidence=0.5,
            missing_aspects=["no_llm_judge"],
            reasoning="LLM judge 미가용",
            method="fallback",
        )

    def _gemini_judge(
        self, query: str, answer: str, retrieved: list[dict]
    ) -> RelevanceVerdict:
        from google import genai  # lazy

        _ensure_env_loaded()
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return RelevanceVerdict(
                verdict="PARTIAL",
                confidence=0.5,
                missing_aspects=["no_api_key"],
                reasoning="GOOGLE_API_KEY 없음",
                method="fallback",
            )

        client = genai.Client(api_key=api_key)
        top_n = min(len(retrieved), 5)
        summary = (
            "\n".join(
                f"- {r.get('concept_id','?')}: {r.get('preferred_term','?')}"
                for r in retrieved[:top_n]
            )
            if retrieved
            else "(검색 결과 없음)"
        )
        prompt = _JUDGE_PROMPT.format(
            query=query, answer=answer[:1500], top_n=top_n, retrieved_summary=summary
        )
        response = client.models.generate_content(model=self.backend, contents=prompt)
        text = (response.text or "").strip()
        text = re.sub(r"^```(json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)

        verdict_raw = str(data.get("verdict", "PARTIAL")).upper()
        if verdict_raw not in ("PASS", "PARTIAL", "FAIL"):
            verdict_raw = "PARTIAL"

        return RelevanceVerdict(
            verdict=verdict_raw,  # type: ignore
            confidence=float(data.get("confidence", 0.5)),
            missing_aspects=list(data.get("missing_aspects", [])),
            reasoning=data.get("reasoning", ""),
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
