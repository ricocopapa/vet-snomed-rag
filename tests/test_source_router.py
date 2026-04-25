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


# ── v2.5 Tier B: external_tools 라우팅 ─────────────────────────


class TestExternalToolRouting:
    def test_default_external_tools_empty(self):
        """일반 쿼리 → external_tools=[], use_external_tool=False (Tier A 회귀 0)."""
        agent = SourceRouterAgent()
        r = agent.route("feline diabetes")
        assert r.external_tools == []
        assert r.use_external_tool is False

    def test_icd10_keyword_activates_umls(self):
        agent = SourceRouterAgent()
        r = agent.route("feline diabetes ICD-10 코드")
        assert "umls" in r.external_tools
        assert r.use_external_tool is True
        assert "UMLS 활성" in r.reasoning

    def test_mesh_keyword_activates_umls(self):
        agent = SourceRouterAgent()
        r = agent.route("MeSH term for canine pancreatitis")
        assert "umls" in r.external_tools

    def test_korean_mapping_keyword_activates_umls(self):
        agent = SourceRouterAgent()
        r = agent.route("고양이 당뇨 ICD-10 매핑")
        assert "umls" in r.external_tools

    def test_rare_keyword_activates_pubmed(self):
        agent = SourceRouterAgent()
        r = agent.route("rare feline endocrine disorder")
        assert "pubmed" in r.external_tools
        assert "PubMed 활성" in r.reasoning

    def test_korean_literature_keyword_activates_pubmed(self):
        agent = SourceRouterAgent()
        r = agent.route("개 췌장염 최신 논문")
        assert "pubmed" in r.external_tools

    def test_both_keywords_activate_both_tools(self):
        agent = SourceRouterAgent()
        r = agent.route("ICD-10 cross-walk for rare feline diabetes literature")
        assert "umls" in r.external_tools
        assert "pubmed" in r.external_tools
        assert r.use_external_tool is True

    def test_direct_construction_syncs_use_flag(self):
        """SourceRoute(external_tools=[...]) 직접 생성 시 use_external_tool 자동 True."""
        from src.retrieval.agentic.source_router import SourceRoute

        r = SourceRoute(external_tools=["umls"])
        assert r.use_external_tool is True

    def test_empty_construction_keeps_use_flag_false(self):
        from src.retrieval.agentic.source_router import SourceRoute

        r = SourceRoute()
        assert r.external_tools == []
        assert r.use_external_tool is False
