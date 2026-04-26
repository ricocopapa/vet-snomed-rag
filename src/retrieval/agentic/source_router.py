"""G-2 SourceRouterAgent — Agentic RAG Step #5·#6 "Which Source?"

쿼리·서브쿼리별 어떤 소스(Vector/SQL/Graph/External Tool)를 사용할지 동적 결정.

v2.5 Tier B: external_tools 필드 + UMLS/PubMed 라우팅 룰 추가.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SourceRoute:
    use_vector: bool = True
    use_sql: bool = True
    use_graph: bool = True
    use_external_tool: bool = False
    vector_weight: float = 0.6
    sql_weight: float = 0.4
    # v2.5 Tier B: 활성 외부 도구 식별자 list (예: ["umls", "pubmed"])
    external_tools: list[str] = field(default_factory=list)
    reasoning: str = ""

    def __post_init__(self):
        # external_tools가 직접 주입된 경우 use_external_tool 자동 동기화
        if self.external_tools and not self.use_external_tool:
            self.use_external_tool = True


# 패턴 → 라우팅 룰
_SQL_HEAVY_PATTERNS = [
    re.compile(r"\b\d{6,}\b"),  # concept_id (6자리 이상 숫자)
    re.compile(r"SNOMED\s*code", re.IGNORECASE),
    re.compile(r"concept[_\s]?id", re.IGNORECASE),
]

_VECTOR_HEAVY_PATTERNS = [
    re.compile(r"[가-힣]"),  # 한국어 자연어
    re.compile(r"증상|통증|이상|의심", re.IGNORECASE),
]

_GRAPH_TRIGGER_PATTERNS = [
    re.compile(r"상위\s*개념|하위\s*개념|관계|연관|유사\s*질환"),
    re.compile(r"parent|child|related|similar", re.IGNORECASE),
    re.compile(r"상위|하위|계층"),
]

# v2.5 Tier B: UMLS cross-walk 키워드
_UMLS_PATTERNS = [
    re.compile(r"\bICD[-_ ]?(10|11)(?:CM)?\b", re.IGNORECASE),
    re.compile(r"\bMeSH\b", re.IGNORECASE),
    re.compile(r"\bRxNorm\b", re.IGNORECASE),
    re.compile(r"\bUMLS\b", re.IGNORECASE),
    re.compile(r"cross[-_ ]?walk", re.IGNORECASE),
    re.compile(r"매핑|크로스워크|코드\s*변환|코드\s*매핑"),
]

# v2.5 Tier B: PubMed evidence/희귀 키워드
_PUBMED_PATTERNS = [
    re.compile(r"\b(emerging|novel|rare|recent)\b", re.IGNORECASE),
    re.compile(r"신규|최신|희귀|드문"),
    re.compile(r"\b(literature|evidence|study|paper)\b", re.IGNORECASE),
    re.compile(r"논문|문헌|증거"),
]

# v2.7 R-3: Web Search (Tavily) — 일반 웹/뉴스 신뢰성 보강 키워드
# 주의: PubMed 패턴과 일부 키워드 겹침(최신/recent). PubMed가 더 도메인-특이하므로
# Web 트리거는 PubMed보다 좁게 — '뉴스/웹/검색' 명시 키워드 + '가이드라인/규제' 위주.
_WEB_PATTERNS = [
    re.compile(r"\b(news|breaking|web\s+search|google)\b", re.IGNORECASE),
    re.compile(r"뉴스|웹\s*검색|구글"),
    re.compile(r"\b(guideline|regulation|FDA|EMA|recall)\b", re.IGNORECASE),
    re.compile(r"가이드라인|규제|허가|리콜"),
]


class SourceRouterAgent:
    """Agentic RAG #5·#6 Which Source? 동적 소스 라우팅.

    rule_based 기본. 향후 backend='gemini' 옵션으로 복잡 판단 가능.
    """

    def __init__(self, backend: str = "rule_based"):
        self.backend = backend

    def route(self, query: str) -> SourceRoute:
        """쿼리 → SourceRoute 결정."""
        route = SourceRoute()
        reasons = []

        # SQL 가중 트리거
        if any(p.search(query) for p in _SQL_HEAVY_PATTERNS):
            route.vector_weight = 0.3
            route.sql_weight = 0.7
            reasons.append("SQL-heavy (concept_id/SNOMED code 패턴)")

        # Vector 가중 트리거 (SQL-heavy 아닌 경우)
        elif any(p.search(query) for p in _VECTOR_HEAVY_PATTERNS):
            route.vector_weight = 0.7
            route.sql_weight = 0.3
            reasons.append("Vector-heavy (한국어 자연어/증상)")

        else:
            reasons.append("기본 균형(0.6/0.4)")

        # Graph 활성 트리거 (독립)
        if any(p.search(query) for p in _GRAPH_TRIGGER_PATTERNS):
            route.use_graph = True
            reasons.append("Graph 활성 (관계/계층 키워드)")
        # Graph 기본은 True 유지 (기존 vet-snomed-rag 파이프라인과 호환)

        # v2.5 Tier B + v2.7 R-3: 외부 도구 라우팅
        external: list[str] = []
        if any(p.search(query) for p in _UMLS_PATTERNS):
            external.append("umls")
            reasons.append("UMLS 활성 (cross-walk 키워드)")
        if any(p.search(query) for p in _PUBMED_PATTERNS):
            external.append("pubmed")
            reasons.append("PubMed 활성 (신규/희귀/문헌 키워드)")
        if any(p.search(query) for p in _WEB_PATTERNS):
            external.append("web")
            reasons.append("Web 활성 (뉴스/가이드라인/규제 키워드)")
        if external:
            route.external_tools = external
            route.use_external_tool = True
        else:
            route.use_external_tool = False

        route.reasoning = " / ".join(reasons)
        return route
