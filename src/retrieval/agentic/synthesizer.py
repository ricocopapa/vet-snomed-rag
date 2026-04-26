"""G-5 ExternalSynthesizerAgent — v2.6 N-3 외부 도구 결과 LLM 합성.

base.answer (LOCAL SNOMED + UMLS/PubMed markdown append) + external_results 메타데이터를
LLM에 전달하여 인용 명확하고 풍부한 통합 답변을 생성한다.

핸드오프: docs/20260426_v2_6_roadmap_handoff.md §3-3

[성공 기준]
- 합성 답변 ≥ base 답변 +30% 길이
- 외부 source 식별자(CUI / PMID) ≥ 80% 본문 인용
- external_results=={} 시 호출 skip (회귀 0)
- 케이스당 < $0.001 (Gemini Flash Lite Preview)
"""
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class SynthesisResult:
    """합성 결과 + 관찰성 필드."""
    synthesized_answer: str
    used: bool                # 합성 LLM 실제 호출 여부
    method: str = "gemini"    # "gemini" | "fallback" | "skip"
    fallback_reason: str = "" # skip / fallback 사유


_SYNTH_PROMPT = """당신은 수의학 SNOMED CT RAG 시스템의 답변 통합기입니다.

[쿼리]
{query}

[1차 답변 — LOCAL SNOMED 검색 결과 + 외부 도구 markdown 섹션 포함]
{base_answer}

[외부 도구 식별자 요약]
{external_summary}

요구사항:
1. 1차 답변의 LOCAL SNOMED 결과(concept_id, FSN)는 그대로 보존하라. 임의 변경·생략 금지.
2. 1차 답변에 포함된 외부 도구 markdown 섹션(예: `[UMLS Cross-Walk]`, `[PubMed Evidence]`)의
   식별자(CUI Cxxxxxxx / PMID 숫자 / ICD10CM·MSH 코드)를 본문에서 명시 인용·해설하라.
3. 답변에 [LOCAL], [UMLS], [PubMed] 같은 출처 표기를 자연스럽게 사용.
4. 답변은 1차 답변보다 길어야 한다(외부 정보 통합·해설).
5. 한국어 자연어 답변. SNOMED 코드와 외부 식별자는 원형 그대로.

통합 답변 (markdown):
"""


# v2.8 R-7: 429 RESOURCE_EXHAUSTED 시 retryDelay 따라 1회 재시도. 상한 30초.
_RETRY_MAX_SECONDS = 30


class ExternalSynthesizerAgent:
    """v2.6 N-3 외부 도구 결과 합성기.

    v2.8 R-7: 429 quota 응답에 대해 retryDelay 기반 1회 재시도 추가.

    Args:
        backend: Gemini 모델 ID. Flash Lite Preview 권장 (저비용·빠름).
    """

    def __init__(self, backend: str = "gemini-3.1-flash-lite-preview"):
        self.backend = backend

    def synthesize(
        self,
        query: str,
        base_answer: str,
        external_results: dict,
    ) -> SynthesisResult:
        """외부 결과 비어있지 않을 때만 LLM 합성. 그 외 skip(회귀 0)."""
        # external_results 비어있거나 모든 tool 빈 list → skip
        if not external_results or not any(external_results.values()):
            return SynthesisResult(
                synthesized_answer=base_answer,
                used=False,
                method="skip",
                fallback_reason="external_results empty",
            )

        try:
            return self._synthesize_gemini(query, base_answer, external_results)
        except Exception as e:
            # 모든 실패 → base_answer 그대로 (회귀 0 보장)
            return SynthesisResult(
                synthesized_answer=base_answer,
                used=False,
                method="fallback",
                fallback_reason=f"{type(e).__name__}: {e}",
            )

    def _synthesize_gemini(
        self,
        query: str,
        base_answer: str,
        external_results: dict,
    ) -> SynthesisResult:
        from google import genai  # lazy

        _ensure_env_loaded()
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return SynthesisResult(
                synthesized_answer=base_answer,
                used=False,
                method="fallback",
                fallback_reason="no GOOGLE_API_KEY",
            )

        external_summary = _format_external_summary(external_results)
        prompt = _SYNTH_PROMPT.format(
            query=query,
            base_answer=base_answer[:4000],  # 토큰 보호
            external_summary=external_summary,
        )

        client = genai.Client(api_key=api_key)
        try:
            response = client.models.generate_content(model=self.backend, contents=prompt)
        except Exception as e:
            # v2.8 R-7: 429 RESOURCE_EXHAUSTED 시 retryDelay 따라 1회 재시도
            err_msg = str(e)
            if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                retry_seconds = _parse_retry_delay(err_msg)
                if retry_seconds is not None and 0 < retry_seconds <= _RETRY_MAX_SECONDS:
                    time.sleep(retry_seconds + 1)
                    response = client.models.generate_content(
                        model=self.backend, contents=prompt
                    )
                else:
                    raise
            else:
                raise
        text = (response.text or "").strip()
        if not text:
            return SynthesisResult(
                synthesized_answer=base_answer,
                used=False,
                method="fallback",
                fallback_reason="empty LLM response",
            )

        return SynthesisResult(
            synthesized_answer=text,
            used=True,
            method="gemini",
        )


def _format_external_summary(external_results: dict) -> str:
    """external_results → LLM 입력용 식별자 요약."""
    lines = []
    umls_items = external_results.get("umls", []) or []
    if umls_items:
        lines.append("[UMLS]")
        for r in umls_items[:3]:
            cui = r.get("cui", "")
            name = r.get("name", "")
            xw = r.get("cross_walks", {}) or {}
            xw_str = " | ".join(
                f"{src}: {','.join(codes[:3])}" for src, codes in xw.items()
            ) if xw else ""
            lines.append(f"- {cui} {name}".rstrip())
            if xw_str:
                lines.append(f"  cross-walks: {xw_str}")

    pubmed_items = external_results.get("pubmed", []) or []
    if pubmed_items:
        lines.append("[PubMed]")
        for r in pubmed_items[:5]:
            pmid = r.get("pmid", "")
            year = r.get("year", "")
            journal = r.get("journal", "")
            title = r.get("title", "")
            lines.append(f"- PMID {pmid} ({year} {journal}) {title}".rstrip())

    return "\n".join(lines) if lines else "(외부 결과 없음)"


def _parse_retry_delay(err_msg: str) -> Optional[float]:
    """v2.8 R-7: Gemini 429 응답의 retryDelay (예: "15.030921765s") 파싱."""
    m = re.search(r"retryDelay'?:?\s*'?(\d+(?:\.\d+)?)s'?", err_msg)
    if not m:
        m = re.search(r"retry in (\d+(?:\.\d+)?)s", err_msg)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            return None
    return None


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
