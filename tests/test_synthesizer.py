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


# ── 10. v2.8 R-7: _dedup_external (source별 식별자 dedup) ────


def test_dedup_external_umls_cui():
    from src.retrieval.agentic_pipeline import _dedup_external

    acc = {
        "umls": [
            {"cui": "C0011849", "name": "Diabetes Mellitus"},
            {"cui": "C0011849", "name": "Diabetes Mellitus DUP"},  # cui 중복
            {"cui": "C0027059", "name": "Myocardial Infarction"},
        ]
    }
    out = _dedup_external(acc)
    assert len(out["umls"]) == 2
    assert out["umls"][0]["cui"] == "C0011849"
    assert out["umls"][0]["name"] == "Diabetes Mellitus"  # 첫 등장 보존
    assert out["umls"][1]["cui"] == "C0027059"


def test_dedup_external_pubmed_pmid():
    from src.retrieval.agentic_pipeline import _dedup_external

    acc = {
        "pubmed": [
            {"pmid": "37123456", "title": "T1"},
            {"pmid": "37999999", "title": "T2"},
            {"pmid": "37123456", "title": "T1 DUP"},
        ]
    }
    out = _dedup_external(acc)
    assert len(out["pubmed"]) == 2
    assert {r["pmid"] for r in out["pubmed"]} == {"37123456", "37999999"}


def test_dedup_external_web_url():
    from src.retrieval.agentic_pipeline import _dedup_external

    acc = {
        "web": [
            {"url": "https://example.com/a", "title": "A"},
            {"url": "https://example.com/b", "title": "B"},
            {"url": "https://example.com/a", "title": "A DUP"},
        ]
    }
    out = _dedup_external(acc)
    assert len(out["web"]) == 2
    assert {r["url"] for r in out["web"]} == {
        "https://example.com/a",
        "https://example.com/b",
    }


def test_dedup_external_preserves_no_id_items():
    """식별자 결측 항목은 dedup 대상이 아니라 보존된다."""
    from src.retrieval.agentic_pipeline import _dedup_external

    acc = {
        "umls": [
            {"cui": "", "name": "Anonymous A"},
            {"cui": "", "name": "Anonymous B"},
            {"cui": "C0011849", "name": "DM"},
        ]
    }
    out = _dedup_external(acc)
    assert len(out["umls"]) == 3


# ── 11. v2.8 R-7: multi-iter 누적 — 마지막 iter 외부 미호출이어도 이전 결과 유지 ────


def test_pipeline_accumulates_external_across_iters():
    """첫 iter에서 외부 호출, 두 번째 iter에서 외부 0건이어도 누적 결과로 합성 트리거."""
    from src.retrieval.agentic.loop_controller import LoopDecision
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
    # iter 0: pubmed 호출 후 결과 있음 / iter 1: umls 호출했으나 0건
    umls_mock.search_with_cross_walks.return_value = []
    pubmed_mock = MagicMock()
    pubmed_mock.enabled = True
    iter_pubmed_outs = [
        [{"pmid": "37123456", "year": "2025", "journal": "Vet J", "title": "T1"}],
        [],  # 두 번째 iter: 빈 결과
    ]
    pubmed_mock.search_with_summaries.side_effect = iter_pubmed_outs

    synth_mock = MagicMock()
    synth_mock.synthesize.return_value = SynthesisResult(
        synthesized_answer="합성 [PubMed] PMID 37123456 통합", used=True, method="gemini"
    )

    pipe = AgenticRAGPipeline(
        base_pipeline=base,
        max_iter=2,
        umls_client=umls_mock,
        pubmed_client=pubmed_mock,
        synthesizer=synth_mock,
    )

    # source_router를 강제로 pubmed 호출하도록 mock
    from src.retrieval.agentic.source_router import SourceRoute

    fake_route = SourceRoute(
        use_vector=True,
        use_sql=False,
        use_graph=False,
        use_external_tool=True,
        external_tools=["pubmed"],
        vector_weight=1.0,
        sql_weight=0.0,
        reasoning="test",
    )

    with patch.object(pipe.complexity_agent, "judge", return_value=ComplexityVerdict(is_complex=False)), \
         patch.object(pipe.source_router, "route", return_value=fake_route), \
         patch.object(
             pipe.judge,
             "judge",
             side_effect=[
                 RelevanceVerdict(verdict="PARTIAL", confidence=0.5),  # iter 0
                 RelevanceVerdict(verdict="PASS", confidence=0.9),      # iter 1
             ],
         ), \
         patch.object(
             pipe.loop,
             "decide",
             side_effect=[
                 LoopDecision(should_continue=True, new_query="rare feline endocrine literature 2", reason="rewrite"),
                 LoopDecision(should_continue=False, new_query=None, reason="pass"),
             ],
         ):
        result = pipe.agentic_query("rare feline endocrine literature")

    # iter 1에서 pubmed 0건이지만 누적된 iter 0 결과로 합성 트리거 유지
    assert result.synthesis_used is True
    # 누적 external_results에 iter 0 PMID가 보존됨
    assert any(r.get("pmid") == "37123456" for r in result.external_results.get("pubmed", []))
    # 마지막 iter에 합성기가 누적된 external을 받았어야 함
    last_call_args = synth_mock.synthesize.call_args_list[-1]
    last_external_arg = last_call_args[0][2]  # 3번째 positional arg
    assert "pubmed" in last_external_arg
    assert any(r.get("pmid") == "37123456" for r in last_external_arg["pubmed"])


# ── 12. v2.8 R-7: synthesis_method / synthesis_fallback_reason 노출 ────


def test_pipeline_exposes_synthesis_method_and_reason():
    """fallback 시 method='fallback' + fallback_reason이 AgenticRAGResult에 노출."""
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
        synthesized_answer="base preserved",
        used=False,
        method="fallback",
        fallback_reason="ClientError: 429 RESOURCE_EXHAUSTED",
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

    assert result.synthesis_used is False
    assert result.synthesis_method == "fallback"
    assert "429" in result.synthesis_fallback_reason


# ── 13. v2.8 R-7: 429 retry 성공 ────────────────────────────


def test_synthesize_429_retry_succeeds(monkeypatch):
    """첫 호출 429 → retryDelay 따라 sleep → 재시도 성공."""
    agent = ExternalSynthesizerAgent()
    fake_response = MagicMock()
    fake_response.text = "retry 성공 합성"

    fake_client = MagicMock()
    err = RuntimeError(
        "ClientError: 429 RESOURCE_EXHAUSTED retryDelay: '2s'"
    )
    fake_client.models.generate_content.side_effect = [err, fake_response]

    sleeps: list = []
    monkeypatch.setattr("src.retrieval.agentic.synthesizer.time.sleep", lambda s: sleeps.append(s))

    with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
         patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=False):
        with patch("google.genai.Client", return_value=fake_client):
            result = agent.synthesize(
                query="q",
                base_answer="base",
                external_results={"umls": [{"cui": "C1", "name": "X"}]},
            )

    assert result.used is True
    assert result.method == "gemini"
    assert result.synthesized_answer == "retry 성공 합성"
    assert sleeps and sleeps[0] >= 2  # retryDelay 따라 대기


# ── 14. v2.8.1 R-7.1: 프롬프트 강화 + 식별자 요약 누적 노출 ────


def test_synth_prompt_has_strict_citation_directive():
    """_SYNTH_PROMPT에 모든 식별자 누락 없이 인용 강제 문구 포함 (R-7.1 핵심)."""
    from src.retrieval.agentic.synthesizer import _SYNTH_PROMPT

    assert "단 하나도 누락 없이" in _SYNTH_PROMPT
    assert "외부 식별자 N개 모두 인용" in _SYNTH_PROMPT
    assert "Web URL" in _SYNTH_PROMPT


def test_format_summary_exposes_all_accumulated_umls_up_to_10():
    """multi-iter 누적 5건 시 LLM 입력에 5건 모두 노출 (v2.8 시점 [:3] 자르기 결함 회복)."""
    ext = {
        "umls": [
            {"cui": f"C0{i:06d}", "name": f"Concept {i}", "cross_walks": {}}
            for i in range(1, 6)  # 5건
        ]
    }
    s = _format_external_summary(ext)
    for i in range(1, 6):
        assert f"C0{i:06d}" in s, f"누적 {i}번째 cui 누락"


def test_format_summary_includes_web_urls():
    """v2.8.1: web 식별자도 요약에 포함 (v2.7 Tier C 정합)."""
    ext = {
        "web": [
            {"url": "https://example.com/aaha-2026", "title": "AAHA Guidelines"},
            {"url": "https://example.com/fda-recall", "title": "FDA Recall"},
        ]
    }
    s = _format_external_summary(ext)
    assert "[Web]" in s
    assert "https://example.com/aaha-2026" in s
    assert "https://example.com/fda-recall" in s


def test_synthesize_passes_all_5_umls_to_llm_prompt():
    """multi-iter 누적 시 합성기 호출 시 LLM prompt에 5건 cui 모두 포함되어야 한다 (T12 시나리오)."""
    agent = ExternalSynthesizerAgent()
    fake_response = MagicMock()
    fake_response.text = (
        "통합답변. C0000001 + C0000002 + C0000003 + C0000004 + C0000005 모두 통합. "
        "(외부 식별자 5개 모두 인용)"
    )
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    captured_prompts = []
    def _capture(model, contents):
        captured_prompts.append(contents)
        return fake_response
    fake_client.models.generate_content.side_effect = _capture

    ext = {
        "umls": [
            {"cui": f"C000000{i}", "name": f"Concept {i}", "cross_walks": {}}
            for i in range(1, 6)
        ]
    }

    with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
         patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=False):
        with patch("google.genai.Client", return_value=fake_client):
            result = agent.synthesize(query="q", base_answer="base", external_results=ext)

    assert result.used is True
    # prompt에 5건 cui 모두 포함되어야 함
    prompt_text = captured_prompts[0]
    for i in range(1, 6):
        assert f"C000000{i}" in prompt_text, f"prompt에 cui C000000{i} 누락 — 합성 LLM이 인용 불가능"


def test_parse_retry_delay_variants():
    """_parse_retry_delay 정규식 — 'retryDelay: 15.0s' 와 'retry in 14s' 모두 파싱."""
    from src.retrieval.agentic.synthesizer import _parse_retry_delay

    assert _parse_retry_delay("retryDelay: '15.030921765s'") == pytest.approx(15.03, abs=0.01)
    assert _parse_retry_delay("Please retry in 14.7s") == pytest.approx(14.7, abs=0.01)
    assert _parse_retry_delay("Please retry in 5s") == 5.0
    assert _parse_retry_delay("no retry hint here") is None


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
