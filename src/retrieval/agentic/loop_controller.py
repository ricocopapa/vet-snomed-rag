"""G-4 RewriteLoopController — Agentic RAG Step #11 "Final Response / Rewrite Loop"

Relevance 결과에 따라 Rewrite 루프 결정 + max_iter 관리 + cycle detection.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .relevance_judge import RelevanceVerdict


@dataclass
class LoopDecision:
    should_continue: bool
    new_query: Optional[str] = None
    reason: str = ""
    iter_count: int = 0


_REWRITE_PROMPT = """Agentic RAG 루프 재작성 에이전트.
이전 답변이 불충분했습니다. 누락된 관점을 반영해 쿼리를 개선하세요.

[원본 쿼리] {original}
[현재 쿼리] {current}
[판정] {verdict} (confidence {confidence:.2f})
[누락 관점] {missing}
[이전 쿼리 이력] {history}

원칙:
- 이전 쿼리와 의미적으로 다른 각도에서 재작성
- 누락 관점을 포함하는 더 구체적 쿼리
- 동일 패턴 반복 금지

JSON만 출력:
{{
  "new_query": "재작성된 쿼리",
  "rationale": "재작성 근거 1문장"
}}
"""


class RewriteLoopController:
    """Agentic RAG #11 루프 제어.

    max_iter 기본 2 (설계서 §11 권고값, latency 안전).
    """

    def __init__(
        self,
        max_iter: int = 2,
        threshold: float = 0.7,
        cycle_similarity_threshold: float = 0.95,
        rewrite_backend: str = "gemini-2.5-flash-lite",
    ):
        self.max_iter = max_iter
        self.threshold = threshold
        self.cycle_threshold = cycle_similarity_threshold
        self.rewrite_backend = rewrite_backend

    def decide(
        self,
        original_query: str,
        current_query: str,
        relevance: RelevanceVerdict,
        iter_count: int,
        history: list[str],
    ) -> LoopDecision:
        """루프 계속 여부 결정 + 필요 시 신규 쿼리 생성."""
        # 1) PASS + threshold 충족 → 종료
        if relevance.verdict == "PASS" and relevance.confidence >= self.threshold:
            return LoopDecision(
                should_continue=False,
                new_query=None,
                reason=f"PASS (conf={relevance.confidence:.2f} ≥ {self.threshold})",
                iter_count=iter_count,
            )

        # 2) max_iter 도달 → 종료 (FAIL이어도)
        if iter_count >= self.max_iter:
            return LoopDecision(
                should_continue=False,
                new_query=None,
                reason=f"max_iter={self.max_iter} 도달 ({relevance.verdict})",
                iter_count=iter_count,
            )

        # 3) Rewrite 시도
        try:
            new_q = self._rewrite(
                original_query, current_query, relevance, history
            )
        except Exception as e:
            return LoopDecision(
                should_continue=False,
                new_query=None,
                reason=f"rewrite 실패({type(e).__name__}) → 종료",
                iter_count=iter_count,
            )

        # 4) Cycle detection
        if self._is_cycle(new_q, history + [current_query]):
            return LoopDecision(
                should_continue=False,
                new_query=None,
                reason="cycle detection: 동일 패턴 반복 → 종료",
                iter_count=iter_count,
            )

        return LoopDecision(
            should_continue=True,
            new_query=new_q,
            reason=f"Rewrite ({relevance.verdict} conf={relevance.confidence:.2f})",
            iter_count=iter_count,
        )

    def _rewrite(
        self,
        original: str,
        current: str,
        relevance: RelevanceVerdict,
        history: list[str],
    ) -> str:
        from google import genai

        _ensure_env_loaded()
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_API_KEY 없음")

        client = genai.Client(api_key=api_key)
        prompt = _REWRITE_PROMPT.format(
            original=original,
            current=current,
            verdict=relevance.verdict,
            confidence=relevance.confidence,
            missing=", ".join(relevance.missing_aspects) or "(none)",
            history=" | ".join(history[-3:]) or "(없음)",
        )
        response = client.models.generate_content(
            model=self.rewrite_backend, contents=prompt
        )
        text = (response.text or "").strip()
        text = re.sub(r"^```(json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
        data = json.loads(text)
        new_q = str(data.get("new_query", "")).strip()
        if not new_q:
            raise RuntimeError("rewrite empty")
        return new_q

    def _is_cycle(self, new_query: str, history: list[str]) -> bool:
        """문자열 유사도 기반 cycle detection.

        sentence-transformers 사용 시 semantic similarity 가능하나,
        추가 의존성 부담 + latency → 토큰 Jaccard 간이 측정.
        """
        if not history:
            return False
        new_tokens = set(_tokenize(new_query))
        if not new_tokens:
            return False
        for h in history:
            h_tokens = set(_tokenize(h))
            if not h_tokens:
                continue
            overlap = len(new_tokens & h_tokens) / max(
                1, len(new_tokens | h_tokens)
            )
            if overlap >= self.cycle_threshold:
                return True
        return False


def _tokenize(text: str) -> list[str]:
    """간이 토큰화 (공백·구두점 분리)."""
    return re.findall(r"[\w가-힣]+", text.lower())


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
