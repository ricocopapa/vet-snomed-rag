"""G-2 SourceRouterAgent 단위 테스트."""
from __future__ import annotations

from src.retrieval.agentic.source_router import SourceRouterAgent


class TestRouting:
    def test_concept_id_query_is_sql_heavy(self):
        agent = SourceRouterAgent()
        r = agent.route("73211009")
        assert r.sql_weight >= 0.7
        assert r.vector_weight <= 0.3
        assert "SQL-heavy" in r.reasoning

    def test_snomed_code_phrase_is_sql_heavy(self):
        agent = SourceRouterAgent()
        r = agent.route("feline diabetes SNOMED code")
        assert r.sql_weight >= 0.7

    def test_korean_natural_query_is_vector_heavy(self):
        agent = SourceRouterAgent()
        r = agent.route("고양이 당뇨 증상")
        assert r.vector_weight >= 0.7
        assert r.sql_weight <= 0.3
        assert "Vector-heavy" in r.reasoning

    def test_graph_trigger_activates_graph(self):
        agent = SourceRouterAgent()
        r = agent.route("feline diabetes의 상위 개념")
        assert r.use_graph is True
        assert "Graph 활성" in r.reasoning

    def test_default_balance_for_plain_query(self):
        agent = SourceRouterAgent()
        r = agent.route("pancreatitis in dog")
        # 한국어 없음, SQL-heavy 패턴 없음 → 기본 0.6/0.4
        assert abs(r.vector_weight - 0.6) < 0.01
        assert abs(r.sql_weight - 0.4) < 0.01
