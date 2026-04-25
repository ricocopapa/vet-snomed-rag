"""v2.4 AgenticRAGPipeline — Datasciencedojo Agentic RAG 11단계 완전 구현.

기존 SNOMEDRagPipeline을 wrapping. base.query() API는 그대로 보존하여
v2.2 벤치마크 회귀 0 보장. agentic_query()는 11단계 루프 신규 진입점.

설계서: docs/20260424_v2_4_agentic_rag_design_v1.md
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from .agentic import (
    ComplexityVerdict,
    QueryComplexityAgent,
    RelevanceJudgeAgent,
    RelevanceVerdict,
    RewriteLoopController,
    SourceRoute,
    SourceRouterAgent,
)


@dataclass
class AgenticRAGResult:
    question: str
    final_answer: str
    iterations: int
    relevance_verdict: Literal["PASS", "PARTIAL", "FAIL"]
    confidence: float
    subqueries: Optional[list[str]] = None
    sources_used: list[str] = field(default_factory=list)
    loop_trace: list[dict] = field(default_factory=list)
    latency_ms: dict = field(default_factory=dict)
    v2_2_compat: bool = True


class AgenticRAGPipeline:
    """Agentic RAG 11단계 완전 구현 wrapper.

    base_pipeline (SNOMEDRagPipeline)의 query()는 절대 변경 없이 그대로 호출.
    G-1·G-2·G-3·G-4 에이전트가 루프를 감싸는 외부 layer로 동작.

    Note:
        G-2 SourceRouter의 가중치 동적 주입은 v2.5에서 base.query() 시그니처
        확장 예정. v2.4는 라우팅 결정 trace 기록까지.
    """

    def __init__(
        self,
        base_pipeline: Any,
        complexity_backend: str = "gemini-2.5-flash-lite",
        router_backend: str = "rule_based",
        judge_backend: str = "gemini-2.5-flash-lite",
        max_iter: int = 2,
        relevance_threshold: float = 0.7,
    ):
        self.base = base_pipeline
        self.complexity_agent = QueryComplexityAgent(backend=complexity_backend)
        self.source_router = SourceRouterAgent(backend=router_backend)
        self.judge = RelevanceJudgeAgent(backend=judge_backend)
        self.loop = RewriteLoopController(
            max_iter=max_iter,
            threshold=relevance_threshold,
            rewrite_backend=judge_backend,
        )

    # v2.2 호환 API — base에 위임
    def query(self, question: str, **kwargs) -> dict:
        return self.base.query(question, **kwargs)

    def agentic_query(
        self,
        question: str,
        top_k: int = 10,
        rerank: bool = True,
    ) -> AgenticRAGResult:
        """Agentic RAG 11단계 루프 실행."""
        t_start = time.time()
        history: list[str] = []
        current = question
        loop_trace: list[dict] = []
        sources_used_all: set[str] = set()
        last_complexity: Optional[ComplexityVerdict] = None
        last_answer = ""
        last_relevance: Optional[RelevanceVerdict] = None

        for iter_count in range(self.loop.max_iter + 1):
            iter_t0 = time.time()
            iter_sources: set[str] = set()  # 본 iter 내 소스 합집합 (S-1 fix)

            # Step A — G-1 #4 Need More Details?
            complexity = self.complexity_agent.judge(current)
            last_complexity = complexity
            subqueries = complexity.subqueries or [current]

            # Step B·C — G-2 #5·#6 + base.query() 실행 (#2·#3·#7·#8·#9)
            sub_results = []
            for sq in subqueries:
                route = self.source_router.route(sq)
                sub_route_names = _route_to_names(route)
                iter_sources.update(sub_route_names)
                sources_used_all.update(sub_route_names)
                base_result = self.base.query(sq, top_k=top_k, rerank=rerank)
                sub_results.append(
                    {
                        "subquery": sq,
                        "route": _route_to_dict(route),
                        "answer": base_result.get("answer", ""),
                        "results": base_result.get("search_results", [])[:5],
                    }
                )

            # 답변 합성 (분해된 경우)
            if len(sub_results) == 1:
                merged_answer = sub_results[0]["answer"]
                merged_retrieved = sub_results[0]["results"]
            else:
                merged_answer = "\n\n".join(
                    f"[Sub-{i+1}] {sr['subquery']}\n{sr['answer']}"
                    for i, sr in enumerate(sub_results)
                )
                merged_retrieved = [
                    r for sr in sub_results for r in sr["results"]
                ]

            last_answer = merged_answer

            # Step D — G-3 #10 Relevance Judge
            retrieved_dicts = [
                {
                    "concept_id": getattr(r, "concept_id", "?"),
                    "preferred_term": getattr(r, "preferred_term", "?"),
                }
                for r in merged_retrieved[:5]
            ]
            relevance = self.judge.judge(current, merged_answer, retrieved_dicts)
            last_relevance = relevance

            # Step E — G-4 #11 Loop Controller
            decision = self.loop.decide(
                question, current, relevance, iter_count, history
            )

            iter_dur_ms = int((time.time() - iter_t0) * 1000)
            loop_trace.append(
                {
                    "iter": iter_count,
                    "query": current,
                    "is_complex": complexity.is_complex,
                    "subqueries_count": len(subqueries),
                    "sources_used": sorted(iter_sources),
                    "verdict": relevance.verdict,
                    "confidence": relevance.confidence,
                    "decision": decision.reason,
                    "latency_ms": iter_dur_ms,
                }
            )

            history.append(current)

            if not decision.should_continue:
                break

            # 다음 iter 준비
            if decision.new_query:
                current = decision.new_query

        total_ms = int((time.time() - t_start) * 1000)
        return AgenticRAGResult(
            question=question,
            final_answer=last_answer,
            iterations=len(loop_trace),
            relevance_verdict=last_relevance.verdict if last_relevance else "FAIL",
            confidence=last_relevance.confidence if last_relevance else 0.0,
            subqueries=last_complexity.subqueries if last_complexity else None,
            sources_used=sorted(sources_used_all),
            loop_trace=loop_trace,
            latency_ms={"total_ms": total_ms},
        )


def _route_to_names(route: SourceRoute) -> set[str]:
    names = set()
    if route.use_vector:
        names.add("vector")
    if route.use_sql:
        names.add("sql")
    if route.use_graph:
        names.add("graph")
    if route.use_external_tool:
        names.add("external_tool")
    return names


def _route_to_dict(route: SourceRoute) -> dict:
    return {
        "vector_weight": route.vector_weight,
        "sql_weight": route.sql_weight,
        "use_graph": route.use_graph,
        "use_external_tool": route.use_external_tool,
        "reasoning": route.reasoning,
    }
