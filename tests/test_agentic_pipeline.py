"""AgenticRAGPipeline E2E 시나리오 테스트.

base_pipeline + Gemini agents 모두 mock 처리.
실제 Gemini·ChromaDB 호출은 Wave 4 벤치마크에서 수행.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.retrieval.agentic.query_complexity import ComplexityVerdict
from src.retrieval.agentic.relevance_judge import RelevanceVerdict
from src.retrieval.agentic_pipeline import AgenticRAGPipeline, AgenticRAGResult


def _make_base_mock(answer: str = "Feline diabetes mellitus 73211009"):
    base = MagicMock()
    base.query.return_value = {
        "question": "stub",
        "answer": answer,
        "search_results": [
            MagicMock(concept_id="73211009", preferred_term="Diabetes mellitus"),
        ],
    }
    return base


class TestSimpleQueryFlow:
    def test_simple_query_passes_in_one_iter(self):
        base = _make_base_mock()
        pipe = AgenticRAGPipeline(base_pipeline=base, max_iter=2)

        with patch.object(
            pipe.complexity_agent,
            "judge",
            return_value=ComplexityVerdict(is_complex=False, subqueries=None),
        ), patch.object(
            pipe.judge,
            "judge",
            return_value=RelevanceVerdict(verdict="PASS", confidence=0.9),
        ):
            result = pipe.agentic_query("feline diabetes")

        assert isinstance(result, AgenticRAGResult)
        assert result.iterations == 1
        assert result.relevance_verdict == "PASS"
        assert result.confidence == 0.9
        assert result.subqueries is None
        # base.query는 1회 호출 (1 sub × 1 iter)
        assert base.query.call_count == 1


class TestComplexQueryFlow:
    def test_complex_query_decomposes_and_passes(self):
        base = _make_base_mock()
        pipe = AgenticRAGPipeline(base_pipeline=base, max_iter=2)

        with patch.object(
            pipe.complexity_agent,
            "judge",
            return_value=ComplexityVerdict(
                is_complex=True,
                subqueries=["feline diabetes SNOMED", "feline pancreatitis SNOMED"],
            ),
        ), patch.object(
            pipe.judge,
            "judge",
            return_value=RelevanceVerdict(verdict="PASS", confidence=0.85),
        ):
            result = pipe.agentic_query("feline diabetes and pancreatitis")

        assert result.iterations == 1
        assert result.subqueries == [
            "feline diabetes SNOMED",
            "feline pancreatitis SNOMED",
        ]
        # 2 subqueries × 1 iter = 2 base.query 호출
        assert base.query.call_count == 2


class TestRewriteLoopFlow:
    def test_partial_triggers_rewrite_then_pass(self):
        base = _make_base_mock()
        pipe = AgenticRAGPipeline(base_pipeline=base, max_iter=2)

        # iter 0: PARTIAL → iter 1: PASS
        verdicts = iter(
            [
                RelevanceVerdict(
                    verdict="PARTIAL", confidence=0.5, missing_aspects=["mechanism"]
                ),
                RelevanceVerdict(verdict="PASS", confidence=0.85),
            ]
        )

        with patch.object(
            pipe.complexity_agent,
            "judge",
            return_value=ComplexityVerdict(is_complex=False),
        ), patch.object(
            pipe.judge, "judge", side_effect=lambda *a, **kw: next(verdicts)
        ), patch.object(
            pipe.loop, "_rewrite", return_value="feline diabetes mechanism"
        ):
            result = pipe.agentic_query("feline diabetes")

        assert result.iterations == 2
        assert result.relevance_verdict == "PASS"
        assert len(result.loop_trace) == 2


class TestMaxIterTermination:
    def test_max_iter_reached_returns_last_state(self):
        base = _make_base_mock()
        pipe = AgenticRAGPipeline(base_pipeline=base, max_iter=2)

        # 매 iter마다 다른 쿼리 반환 (cycle detection 회피)
        rewrites = iter(["rewritten alpha mechanism", "rewritten beta diagnosis"])

        with patch.object(
            pipe.complexity_agent,
            "judge",
            return_value=ComplexityVerdict(is_complex=False),
        ), patch.object(
            pipe.judge,
            "judge",
            return_value=RelevanceVerdict(
                verdict="PARTIAL", confidence=0.4, missing_aspects=["x"]
            ),
        ), patch.object(
            pipe.loop, "_rewrite", side_effect=lambda *a, **kw: next(rewrites)
        ):
            result = pipe.agentic_query("ambiguous original query")

        # max_iter=2이므로 iter 0, 1, 2 까지 (3회), 마지막에 max_iter 종료
        assert result.iterations == 3
        assert result.relevance_verdict == "PARTIAL"
        # 마지막 iter의 decision에 max_iter 사유 포함
        assert "max_iter" in result.loop_trace[-1]["decision"]


class TestSourcesTraceAccumulation:
    def test_sources_used_accumulates_across_iters(self):
        base = _make_base_mock()
        pipe = AgenticRAGPipeline(base_pipeline=base, max_iter=2)

        with patch.object(
            pipe.complexity_agent,
            "judge",
            return_value=ComplexityVerdict(is_complex=False),
        ), patch.object(
            pipe.judge,
            "judge",
            return_value=RelevanceVerdict(verdict="PASS", confidence=0.9),
        ):
            result = pipe.agentic_query("73211009")  # SQL-heavy 라우팅

        # 기본 라우팅: vector + sql + graph 모두 활성 (graph 기본 True)
        assert "sql" in result.sources_used
        assert "vector" in result.sources_used
        # 단일 iter PASS 종료
        assert result.iterations == 1


class TestV22Compat:
    def test_query_method_delegates_to_base(self):
        base = _make_base_mock()
        pipe = AgenticRAGPipeline(base_pipeline=base, max_iter=2)
        out = pipe.query("test", top_k=10)
        # base.query 한번 호출, AgenticRAGResult 아닌 dict 반환
        assert isinstance(out, dict)
        assert "answer" in out
