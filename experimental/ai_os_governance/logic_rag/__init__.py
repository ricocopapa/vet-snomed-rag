"""Logic RAG PoC — Sionic AI 방법론 자체 구현 (v2.3.4 Roadmap).

Query Decomposition + DAG 위상 정렬 + 재귀 해결 + 답변 합성.
사전 그래프 구축 비용 없이 질의 시점에 동적 지도를 만든다.
"""
from .decompose import decompose_query
from .dag import max_depth, topological_sort
from .solve import run_logic_rag_e2e, solve_dag, solve_subquery, synthesize

__version__ = "0.1.0"
__all__ = [
    "decompose_query",
    "topological_sort",
    "max_depth",
    "solve_dag",
    "solve_subquery",
    "synthesize",
    "run_logic_rag_e2e",
]
