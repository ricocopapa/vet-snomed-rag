"""G-2 SourceRouterAgent — Agentic RAG Step #5·#6 "Which Source?"

쿼리·서브쿼리별 어떤 소스(Vector/SQL/Graph/External Tool)를 사용할지 동적 결정.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SourceRoute:
    use_vector: bool = True
    use_sql: bool = True
    use_graph: bool = True
    use_external_tool: bool = False
    vector_weight: float = 0.6
    sql_weight: float = 0.4
    reasoning: str = ""


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

        # External tool (미구현, 향후 확장 훅)
        route.use_external_tool = False

        route.reasoning = " / ".join(reasons)
        return route
