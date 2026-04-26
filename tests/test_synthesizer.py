"""tests/test_synthesizer.py — v2.6 N-3 ExternalSynthesizerAgent 단위 테스트.

핸드오프: docs/20260426_v2_6_roadmap_handoff.md §3-3-5

검증 항목:
1. external_results 비어있으면 호출 skip + base_answer 보존 (회귀 0)
2. UMLS만 있을 때 _format_external_summary가 CUI/cross-walk 정확히 포함
3. PubMed만 있을 때 PMID + journal/year 포함
4. 둘 다 있을 때 both 섹션 포함
5. LLM 호출 mock — synthesized_answer 반환 + used=True
6. LLM 예외 발생 시 fallback (used=False, base_answer 보존)
7. GOOGLE_API_KEY 미설정 시 fallback
8. 빈 LLM 응답 시 fallback
9. AgenticRAGPipeline 통합 — synthesis_used 필드 정상 채워짐
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from src.retrieval.agentic.synthesizer import (
    ExternalSynthesizerAgent,
    SynthesisResult,
    _format_external_summary,
)


# ── 1. external 비어있을 때 skip ──────────────────────────


def test_synthesize_skips_when_external_empty():
    agent = ExternalSynthesizerAgent()
    result = agent.synthesize(
        query="feline diabetes",
        base_answer="LOCAL answer",
        external_results={},
    )
    assert result.used is False
    assert result.method == "skip"
    assert result.synthesized_answer == "LOCAL answer"


def test_synthesize_skips_when_all_lists_empty():
    """external_results = {umls: [], pubmed: []} 도 skip."""
    agent = ExternalSynthesizerAgent()
    result = agent.synthesize(
        query="q", base_answer="A", external_results={"umls": [], "pubmed": []}
    )
    assert result.used is False
    assert result.method == "skip"


# ── 2-4. _format_external_summary ────────────────────────


def test_format_summary_umls_only():
    ext = {
        "umls": [
            {
                "cui": "C0011849",
                "name": "Diabetes Mellitus",
                "cross_walks": {"ICD10CM": ["E08-E13"], "MSH": ["D003920"]},
            }
        ]
    }
    s = _format_external_summary(ext)
    assert "[UMLS]" in s
    assert "C0011849" in s
    assert "Diabetes Mellitus" in s
    assert "ICD10CM: E08-E13" in s
    assert "MSH: D003920" in s
    assert "[PubMed]" not in s


def test_format_summary_pubmed_only():
    ext = {
        "pubmed": [
            {
                "pmid": "37123456",
                "year": "2025",
                "journal": "Vet J",
                "title": "Insulin therapy in cats",
            }
        ]
    }
    s = _format_external_summary(ext)
    assert "[PubMed]" in s
    assert "PMID 37123456" in s
    assert "2025 Vet J" in s
    assert "Insulin therapy in cats" in s
    assert "[UMLS]" not in s


def test_format_summary_both():
    ext = {
        "umls": [{"cui": "C1", "name": "X", "cross_walks": {}}],
        "pubmed": [{"pmid": "P1", "title": "T1"}],
    }
    s = _format_external_summary(ext)
    assert "[UMLS]" in s and "[PubMed]" in s


# ── 5. LLM 호출 mock — used=True ────────────────────────


def test_synthesize_with_llm_mock_used_true():
    agent = ExternalSynthesizerAgent()
    fake_response = MagicMock()
    fake_response.text = (
        "[LOCAL] feline diabetes mellitus → 73211009. "
        "[UMLS] CUI C0011849 cross-walks ICD10CM E08-E13. "
        "통합 답변 더 풍부."
    )
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
         patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=False):
        with patch("google.genai.Client", return_value=fake_client):
            result = agent.synthesize(
                query="feline diabetes",
                base_answer="짧은 base",
                external_results={
                    "umls": [{"cui": "C0011849", "name": "Diabetes Mellitus", "cross_walks": {"ICD10CM": ["E08-E13"]}}]
                },
            )

    assert result.used is True
    assert result.method == "gemini"
    assert "C0011849" in result.synthesized_answer
    assert result.synthesized_answer != "짧은 base"


# ── 6. LLM 예외 시 fallback ──────────────────────────────


def test_synthesize_llm_exception_falls_back():
    agent = ExternalSynthesizerAgent()
    with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
         patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=False):
        with patch("google.genai.Client", side_effect=RuntimeError("API down")):
            result = agent.synthesize(
                query="q",
                base_answer="base preserved",
                external_results={"umls": [{"cui": "C1", "name": "X"}]},
            )
    assert result.used is False
    assert result.method == "fallback"
    assert "RuntimeError" in result.fallback_reason
    assert result.synthesized_answer == "base preserved"


# ── 7. GOOGLE_API_KEY 미설정 시 fallback ─────────────────


def test_synthesize_no_api_key_falls_back():
    agent = ExternalSynthesizerAgent()
    with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
         patch.dict(os.environ, {}, clear=True):
        result = agent.synthesize(
            query="q",
            base_answer="base preserved",
            external_results={"umls": [{"cui": "C1", "name": "X"}]},
        )
    assert result.used is False
    assert result.method == "fallback"
    assert "no GOOGLE_API_KEY" in result.fallback_reason
    assert result.synthesized_answer == "base preserved"


# ── 8. 빈 LLM 응답 시 fallback ───────────────────────────


def test_synthesize_empty_llm_response_falls_back():
    agent = ExternalSynthesizerAgent()
    fake_response = MagicMock()
    fake_response.text = ""
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
         patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=False):
        with patch("google.genai.Client", return_value=fake_client):
            result = agent.synthesize(
                query="q",
                base_answer="base preserved",
                external_results={"umls": [{"cui": "C1", "name": "X"}]},
            )

    assert result.used is False
    assert result.method == "fallback"
    assert "empty LLM response" in result.fallback_reason


# ── 9. AgenticRAGPipeline 통합 — synthesis_used 필드 ────


def test_pipeline_synthesis_used_when_external_present():
    """외부 결과 있을 때 AgenticRAGResult.synthesis_used=True."""
    from src.retrieval.agentic.query_complexity import ComplexityVerdict
    from src.retrieval.agentic.relevance_judge import RelevanceVerdict
    from src.retrieval.agentic_pipeline import AgenticRAGPipeline

    base = MagicMock()
    base.query.return_value = {
        "answer": "LOCAL ans",
        "search_results": [MagicMock(concept_id="73211009", preferred_term="DM")],
        "reformulation": {"reformulated": "diabetes mellitus", "confidence": 1.0},
    }
    umls_mock = MagicMock()
    umls_mock.enabled = True
    umls_mock.search_with_cross_walks.return_value = [
        {"cui": "C0011849", "name": "Diabetes Mellitus", "cross_walks": {"ICD10CM": ["E08-E13"]}}
    ]
    pubmed_mock = MagicMock()
    pubmed_mock.enabled = True
    pubmed_mock.search_with_summaries.return_value = []

    synth_mock = MagicMock()
    synth_mock.synthesize.return_value = SynthesisResult(
        synthesized_answer="합성됨 [UMLS] C0011849 풍부한 통합 답변",
        used=True,
        method="gemini",
    )

    pipe = AgenticRAGPipeline(
        base_pipeline=base,
        max_iter=1,
        umls_client=umls_mock,
        pubmed_client=pubmed_mock,
        synthesizer=synth_mock,
    )

    with patch.object(pipe.complexity_agent, "judge", return_value=ComplexityVerdict(is_complex=False)), \
         patch.object(pipe.judge, "judge", return_value=RelevanceVerdict(verdict="PASS", confidence=0.9)):
        result = pipe.agentic_query("ICD-10 cross-walk for diabetes")

    assert result.synthesis_used is True
    assert "합성됨" in result.final_answer
    assert "C0011849" in result.final_answer
    # base_answer 관찰성 보존
    assert result.base_answer_pre_synthesis  # 비어있지 않음
    assert "합성됨" not in result.base_answer_pre_synthesis  # 원본 base는 합성 전


def test_pipeline_synthesis_skipped_when_no_external():
    """외부 결과 없으면 합성 호출 0 + final_answer == base_answer (회귀 0)."""
    from src.retrieval.agentic.query_complexity import ComplexityVerdict
    from src.retrieval.agentic.relevance_judge import RelevanceVerdict
    from src.retrieval.agentic_pipeline import AgenticRAGPipeline

    base = MagicMock()
    base.query.return_value = {
        "answer": "LOCAL only",
        "search_results": [MagicMock(concept_id="73211009", preferred_term="DM")],
        "reformulation": None,
    }
    umls_mock = MagicMock()
    umls_mock.enabled = True
    umls_mock.search_with_cross_walks.return_value = []
    pubmed_mock = MagicMock()
    pubmed_mock.enabled = True
    pubmed_mock.search_with_summaries.return_value = []

    synth_mock = MagicMock()  # 호출 0 검증

    pipe = AgenticRAGPipeline(
        base_pipeline=base,
        max_iter=1,
        umls_client=umls_mock,
        pubmed_client=pubmed_mock,
        synthesizer=synth_mock,
    )

    with patch.object(pipe.complexity_agent, "judge", return_value=ComplexityVerdict(is_complex=False)), \
         patch.object(pipe.judge, "judge", return_value=RelevanceVerdict(verdict="PASS", confidence=0.9)):
        result = pipe.agentic_query("plain query no external")

    assert synth_mock.synthesize.call_count == 0  # 외부 결과 없음 → 호출 0
    assert result.synthesis_used is False
    assert result.final_answer == "LOCAL only"  # 회귀 0


def test_pipeline_synthesis_fallback_preserves_base():
    """합성기 fallback 시 final_answer = base_answer 그대로."""
    from src.retrieval.agentic.query_complexity import ComplexityVerdict
    from src.retrieval.agentic.relevance_judge import RelevanceVerdict
    from src.retrieval.agentic_pipeline import AgenticRAGPipeline

    base = MagicMock()
    base.query.return_value = {
        "answer": "LOCAL ans",
        "search_results": [MagicMock(concept_id="73211009", preferred_term="DM")],
        "reformulation": {"reformulated": "diabetes mellitus", "confidence": 1.0},
    }
    umls_mock = MagicMock()
    umls_mock.enabled = True
    umls_mock.search_with_cross_walks.return_value = [
        {"cui": "C0011849", "name": "Diabetes Mellitus", "cross_walks": {}}
    ]
    pubmed_mock = MagicMock()
    pubmed_mock.enabled = True
    pubmed_mock.search_with_summaries.return_value = []

    synth_mock = MagicMock()
    synth_mock.synthesize.return_value = SynthesisResult(
        synthesized_answer="LOCAL ans\n\n[UMLS Cross-Walk] (외부)\n- C0011849 Diabetes Mellitus",
        used=False,  # fallback
        method="fallback",
        fallback_reason="API down",
    )

    pipe = AgenticRAGPipeline(
        base_pipeline=base,
        max_iter=1,
        umls_client=umls_mock,
        pubmed_client=pubmed_mock,
        synthesizer=synth_mock,
    )

    with patch.object(pipe.complexity_agent, "judge", return_value=ComplexityVerdict(is_complex=False)), \
         patch.object(pipe.judge, "judge", return_value=RelevanceVerdict(verdict="PASS", confidence=0.9)):
        result = pipe.agentic_query("ICD-10 query")

    assert result.synthesis_used is False  # fallback → False
    # final_answer는 합성기 호출 전 base+markdown (이미 sub_results의 answer)
    assert "[UMLS Cross-Walk]" in result.final_answer
    assert "C0011849" in result.final_answer
