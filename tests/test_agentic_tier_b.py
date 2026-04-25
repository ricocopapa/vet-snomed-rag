"""tests/test_agentic_tier_b.py — v2.5 Tier B 통합 smoke.

mock base pipeline + mock UMLS/PubMed 클라이언트로
external_tools 분기 호출이 실제로 일어나는지 검증.

검증 항목:
1. external_tools=[] (일반 쿼리) → UMLS·PubMed 호출 0 (Tier A 회귀 0)
2. ICD-10 키워드 → UMLS 호출 발생, PubMed 호출 0
3. "최신 논문" 키워드 → PubMed 호출 발생, UMLS 호출 0
4. 둘 다 활성 키워드 → 둘 다 호출
5. UMLS 비활성 (enabled=False) → 라우터가 활성해도 호출 0 (graceful skip)
6. PubMed 비활성 → 라우터가 활성해도 호출 0
7. external_results 필드가 AgenticRAGResult에 정상 채워짐
8. final_answer에 [UMLS Cross-Walk] / [PubMed Evidence] markdown 섹션 포함
9. sources_used에 "umls"/"pubmed" 정확한 이름 등장 (external_tool 일반명 아님)
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.retrieval.agentic.query_complexity import ComplexityVerdict
from src.retrieval.agentic.relevance_judge import RelevanceVerdict
from src.retrieval.agentic_pipeline import AgenticRAGPipeline


def _make_base_mock():
    base = MagicMock()
    base.query.return_value = {
        "question": "stub",
        "answer": "Local SNOMED 답변",
        "search_results": [
            MagicMock(concept_id="73211009", preferred_term="Diabetes mellitus"),
        ],
    }
    return base


def _make_umls_mock(enabled: bool = True):
    """search_with_cross_walks를 mock한 UMLSClient stub."""
    m = MagicMock()
    m.enabled = enabled
    m.search_with_cross_walks = MagicMock(
        return_value=[
            {
                "cui": "C0011849",
                "name": "Diabetes Mellitus",
                "semantic_types": ["Disease"],
                "cross_walks": {"ICD10CM": ["E11.9"], "MSH": ["D003924"]},
                "source": "umls",
            }
        ]
        if enabled
        else []
    )
    return m


def _make_pubmed_mock(enabled: bool = True):
    """search_with_summaries를 mock한 PubMedClient stub."""
    m = MagicMock()
    m.enabled = enabled
    m.search_with_summaries = MagicMock(
        return_value=[
            {
                "pmid": "37123456",
                "title": "Insulin therapy in cats",
                "journal": "Vet J",
                "year": "2025",
                "authors": ["Smith J", "Lee K"],
                "source": "pubmed",
            }
        ]
        if enabled
        else []
    )
    return m


def _make_pipe(umls=None, pubmed=None):
    """기본 mock 클라이언트 + complexity·judge mock된 파이프라인."""
    base = _make_base_mock()
    pipe = AgenticRAGPipeline(
        base_pipeline=base,
        max_iter=1,
        umls_client=umls if umls is not None else _make_umls_mock(),
        pubmed_client=pubmed if pubmed is not None else _make_pubmed_mock(),
    )
    return pipe, base


def _patch_agents(pipe):
    return patch.object(
        pipe.complexity_agent,
        "judge",
        return_value=ComplexityVerdict(is_complex=False),
    ), patch.object(
        pipe.judge,
        "judge",
        return_value=RelevanceVerdict(verdict="PASS", confidence=0.9),
    )


# ── 1. 일반 쿼리 → 외부 호출 0 (Tier A 회귀 0) ─────────────────


def test_plain_query_zero_external_calls():
    pipe, base = _make_pipe()
    cm, jm = _patch_agents(pipe)
    with cm, jm:
        result = pipe.agentic_query("feline diabetes")  # external 키워드 없음
    assert pipe.umls.search_with_cross_walks.call_count == 0
    assert pipe.pubmed.search_with_summaries.call_count == 0
    assert result.external_results == {}


# ── 2. ICD-10 키워드 → UMLS만 ─────────────────────────────────


def test_icd10_keyword_triggers_umls_only():
    pipe, base = _make_pipe()
    cm, jm = _patch_agents(pipe)
    with cm, jm:
        result = pipe.agentic_query("feline diabetes ICD-10 코드")
    assert pipe.umls.search_with_cross_walks.call_count == 1
    assert pipe.pubmed.search_with_summaries.call_count == 0
    assert "umls" in result.external_results
    assert "[UMLS Cross-Walk]" in result.final_answer
    assert "C0011849" in result.final_answer
    assert "ICD10CM" in result.final_answer
    assert "umls" in result.sources_used


# ── 3. 최신/희귀 키워드 → PubMed만 ─────────────────────────────


def test_literature_keyword_triggers_pubmed_only():
    pipe, base = _make_pipe()
    cm, jm = _patch_agents(pipe)
    with cm, jm:
        result = pipe.agentic_query("rare feline endocrine literature")
    assert pipe.pubmed.search_with_summaries.call_count == 1
    assert pipe.umls.search_with_cross_walks.call_count == 0
    assert "pubmed" in result.external_results
    assert "[PubMed Evidence]" in result.final_answer
    assert "37123456" in result.final_answer
    assert "pubmed" in result.sources_used


# ── 4. 둘 다 활성 ──────────────────────────────────────────────


def test_both_keywords_trigger_both():
    pipe, base = _make_pipe()
    cm, jm = _patch_agents(pipe)
    with cm, jm:
        result = pipe.agentic_query("ICD-10 cross-walk for rare diabetes literature")
    assert pipe.umls.search_with_cross_walks.call_count == 1
    assert pipe.pubmed.search_with_summaries.call_count == 1
    assert "umls" in result.external_results
    assert "pubmed" in result.external_results
    assert "[UMLS Cross-Walk]" in result.final_answer
    assert "[PubMed Evidence]" in result.final_answer


# ── 5. UMLS 비활성 → 라우터 활성해도 호출 0 ───────────────────


def test_umls_disabled_skips_call():
    pipe, base = _make_pipe(umls=_make_umls_mock(enabled=False))
    cm, jm = _patch_agents(pipe)
    with cm, jm:
        result = pipe.agentic_query("feline diabetes ICD-10")  # UMLS 트리거
    # 라우터는 umls 결정했지만 enabled=False라 실제 호출 0
    assert pipe.umls.search_with_cross_walks.call_count == 0
    assert "[UMLS Cross-Walk]" not in result.final_answer
    assert "umls" not in result.external_results


# ── 6. PubMed 비활성 → 라우터 활성해도 호출 0 ─────────────────


def test_pubmed_disabled_skips_call():
    pipe, base = _make_pipe(pubmed=_make_pubmed_mock(enabled=False))
    cm, jm = _patch_agents(pipe)
    with cm, jm:
        result = pipe.agentic_query("rare diabetes 최신 논문")  # PubMed 트리거
    assert pipe.pubmed.search_with_summaries.call_count == 0
    assert "[PubMed Evidence]" not in result.final_answer
    assert "pubmed" not in result.external_results


# ── 7. external 결과가 비어있을 때 markdown 미추가 ────────────


def test_empty_external_results_no_markdown():
    """external 클라이언트가 빈 list 반환 시 markdown 섹션 추가 안 함."""
    umls = MagicMock()
    umls.enabled = True
    umls.search_with_cross_walks = MagicMock(return_value=[])
    pipe, base = _make_pipe(umls=umls)
    cm, jm = _patch_agents(pipe)
    with cm, jm:
        result = pipe.agentic_query("ICD-10 코드")
    assert pipe.umls.search_with_cross_walks.call_count == 1
    assert "[UMLS Cross-Walk]" not in result.final_answer
    assert "umls" not in result.external_results  # 빈 결과는 보관 안 함
