"""G-1 QueryComplexityAgent 단위 테스트."""
from __future__ import annotations

from unittest.mock import patch

from src.retrieval.agentic.query_complexity import (
    ComplexityVerdict,
    QueryComplexityAgent,
)


class TestRuleBased:
    def test_short_simple_query_is_not_complex(self):
        agent = QueryComplexityAgent(backend="rule_based")
        v = agent.judge("feline diabetes")
        assert v.is_complex is False
        assert v.subqueries is None
        assert v.method == "rule_based"
        assert v.confidence >= 0.8

    def test_long_query_flagged_complex(self):
        agent = QueryComplexityAgent(backend="rule_based")
        q = "이 환자는 당뇨와 췌장염 증상을 동반하며 신부전 의심 소견도 있는 복합 케이스로 SNOMED 태깅 전략을 제안해 주세요"
        v = agent.judge(q)
        assert v.is_complex is True
        assert v.method == "rule_based"

    def test_complex_keyword_triggers_complex(self):
        agent = QueryComplexityAgent(backend="rule_based")
        v = agent.judge("feline diabetes vs parvovirus")
        assert v.is_complex is True

    def test_korean_complex_keyword(self):
        agent = QueryComplexityAgent(backend="rule_based")
        v = agent.judge("당뇨와 췌장염 비교")
        assert v.is_complex is True


class TestGeminiFallback:
    def test_gemini_503_falls_back_to_rule_based(self):
        agent = QueryComplexityAgent(backend="gemini-3.1-flash-lite-preview")
        with patch.object(
            agent, "_gemini_judge", side_effect=RuntimeError("503 UNAVAILABLE")
        ):
            v = agent.judge("feline diabetes")
            assert v.method == "rule_based_fallback"
            assert v.is_complex is False  # 짧은 쿼리는 simple


class TestVerdictDataclass:
    def test_default_fields(self):
        v = ComplexityVerdict(is_complex=False)
        assert v.subqueries is None
        assert v.confidence == 1.0
        assert v.method == "rule_based"
