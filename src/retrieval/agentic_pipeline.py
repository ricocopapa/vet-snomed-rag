"""v2.4/2.5 AgenticRAGPipeline — Datasciencedojo Agentic RAG 11단계 완전 구현.

기존 SNOMEDRagPipeline을 wrapping. base.query() API는 그대로 보존하여
v2.2 벤치마크 회귀 0 보장. agentic_query()는 11단계 루프 신규 진입점.

v2.5 Tier B: ⑥ Sources의 "Tools & APIs" 분기 활성화. SourceRouter 결정에 따라
UMLS / PubMed 외부 도구를 호출하여 base.answer에 markdown 섹션으로 합류.

설계서:
- v2.4: docs/20260424_v2_4_agentic_rag_design_v1.md
- v2.5 Tier B: docs/20260425_v2_5_tier_b_external_tools_design_v1.md
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from .agentic import (
    ComplexityVerdict,
    ExternalSynthesizerAgent,
    QueryComplexityAgent,
    RelevanceJudgeAgent,
    RelevanceVerdict,
    RewriteLoopController,
    SourceRoute,
    SourceRouterAgent,
)
from src.tools.pubmed_client import PubMedClient
from src.tools.umls_client import UMLSClient
from src.tools.web_search_client import TavilyWebSearchClient


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
    # v2.8 R-7: 모든 iter 누적 외부 도구 결과 (source별 식별자 dedup)
    external_results: dict = field(default_factory=dict)
    # v2.6 N-1: 마지막 iter의 sub_results (search_results 노출용 — 회귀 측정 베이스)
    last_sub_results: list[dict] = field(default_factory=list)
    # v2.6 N-3: 외부 도구 결과 LLM 합성이 실제로 적용됐는지 (한 iter라도 적용 시 True)
    synthesis_used: bool = False
    # v2.6 N-3: 합성 전 base_answer (관찰성, 합성 답변과 비교 가능)
    base_answer_pre_synthesis: str = ""
    # v2.8 R-7: 합성 시도 결과 관찰성 (skip / gemini / fallback)
    synthesis_method: str = "skip"
    # v2.8 R-7: 합성 fallback 사유 (429 quota / empty response / API error 등)
    synthesis_fallback_reason: str = ""
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
        complexity_backend: str = "gemini-3.1-flash-lite-preview",
        router_backend: str = "rule_based",
        judge_backend: str = "gemini-3.1-flash-lite-preview",
        synthesizer_backend: str = "gemini-3.1-flash-lite-preview",
        max_iter: int = 2,
        relevance_threshold: float = 0.7,
        umls_client: Optional[UMLSClient] = None,
        pubmed_client: Optional[PubMedClient] = None,
        web_client: Optional[TavilyWebSearchClient] = None,
        synthesizer: Optional[ExternalSynthesizerAgent] = None,
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
        # v2.5 Tier B + v2.7 R-3: 외부 도구 클라이언트 (env 기반 자동 init, 키 미설정 시 비활성)
        self.umls = umls_client if umls_client is not None else UMLSClient()
        self.pubmed = pubmed_client if pubmed_client is not None else PubMedClient()
        self.web = web_client if web_client is not None else TavilyWebSearchClient()
        # v2.6 N-3: 외부 결과 LLM 합성기 (DI 가능)
        self.synthesizer = synthesizer if synthesizer is not None else ExternalSynthesizerAgent(
            backend=synthesizer_backend
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

        # v2.8 R-7: 모든 iter 외부 결과를 누적 (마지막 iter만 보존하던 last_external 폐기)
        accumulated_external: dict[str, list] = {}
        last_sub_results: list[dict] = []
        last_synthesis_used: bool = False
        last_base_answer_pre_synthesis: str = ""
        last_synthesis_method: str = "skip"
        last_synthesis_fallback_reason: str = ""
        for iter_count in range(self.loop.max_iter + 1):
            iter_t0 = time.time()
            iter_sources: set[str] = set()  # 본 iter 내 소스 합집합 (S-1 fix)

            # Step A — G-1 #4 Need More Details?
            complexity = self.complexity_agent.judge(current)
            last_complexity = complexity
            subqueries = complexity.subqueries or [current]

            # Step B·C — G-2 #5·#6 + base.query() 실행 (#2·#3·#7·#8·#9)
            # v2.5 Tier A: 라우터 결정값(route)을 base.query()로 전달 → 실제 백엔드 분기 실행
            # v2.5 Tier B: route.external_tools에 따라 UMLS/PubMed 호출 → base.answer에 markdown 합류
            sub_results = []
            iter_external: dict[str, list] = {}
            for sq in subqueries:
                route = self.source_router.route(sq)
                sub_route_names = _route_to_names(route)
                iter_sources.update(sub_route_names)
                sources_used_all.update(sub_route_names)
                base_result = self.base.query(
                    sq, top_k=top_k, rerank=rerank, source_route=route
                )

                # v2.5 Tier B: 외부 도구 호출 (route.external_tools 분기)
                # v2.6 N-1 fix: UMLS는 라우팅 트리거 키워드("ICD-10 cross-walk", "매핑" 등)가
                # 포함된 raw subquery에 0건 반환. reformulator가 정제한 의학 용어를 사용.
                ext_query = sq
                ref = base_result.get("reformulation")
                if ref and ref.get("reformulated") and ref.get("confidence", 0) >= 0.5:
                    ext_query = ref["reformulated"]

                sub_external: dict = {}
                answer_with_external = base_result.get("answer", "")
                if "umls" in route.external_tools and self.umls.enabled:
                    umls_out = self.umls.search_with_cross_walks(ext_query, top_k=1)
                    if umls_out:
                        sub_external["umls"] = umls_out
                        iter_external.setdefault("umls", []).extend(umls_out)
                        answer_with_external = (
                            answer_with_external + "\n\n" + _format_umls_md(umls_out)
                        )
                if "pubmed" in route.external_tools and self.pubmed.enabled:
                    pubmed_out = self.pubmed.search_with_summaries(ext_query, top_k=3)
                    if pubmed_out:
                        sub_external["pubmed"] = pubmed_out
                        iter_external.setdefault("pubmed", []).extend(pubmed_out)
                        answer_with_external = (
                            answer_with_external + "\n\n" + _format_pubmed_md(pubmed_out)
                        )
                if "web" in route.external_tools and self.web.enabled:
                    web_out = self.web.search(ext_query, top_k=5)
                    if web_out:
                        sub_external["web"] = web_out
                        iter_external.setdefault("web", []).extend(web_out)
                        answer_with_external = (
                            answer_with_external + "\n\n" + _format_web_md(web_out)
                        )

                sub_results.append(
                    {
                        "subquery": sq,
                        "route": _route_to_dict(route),
                        "answer": answer_with_external,
                        "results": base_result.get("search_results", [])[:5],
                        "external": sub_external,
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

            # v2.8 R-7: 본 iter external을 누적에 합치고 source별 식별자 dedup
            for tool, items in iter_external.items():
                accumulated_external.setdefault(tool, []).extend(items)
            accumulated_external = _dedup_external(accumulated_external)

            # v2.6 N-3 + v2.8 R-7: 누적 external 기반 LLM 합성. 비어있으면 skip(회귀 0).
            base_answer_pre_synth = merged_answer
            synthesis_used_this_iter = False
            if accumulated_external and any(accumulated_external.values()):
                synth = self.synthesizer.synthesize(
                    question, merged_answer, accumulated_external
                )
                if synth.used:
                    merged_answer = synth.synthesized_answer
                    synthesis_used_this_iter = True
                last_synthesis_method = synth.method
                last_synthesis_fallback_reason = synth.fallback_reason

            last_answer = merged_answer

            # Step D — G-3 #10 Relevance Judge (합성된 답변 평가)
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
                    "external_counts": {tool: len(v) for tool, v in iter_external.items()},
                    "verdict": relevance.verdict,
                    "confidence": relevance.confidence,
                    "decision": decision.reason,
                    "latency_ms": iter_dur_ms,
                }
            )
            # v2.6 N-1: 마지막 iter의 sub_results 보존 (search_results 노출용)
            last_sub_results = sub_results
            # v2.8 R-7: synthesis_used는 단조 유지 — 한 iter라도 합성 적용되면 True 유지
            if synthesis_used_this_iter:
                last_synthesis_used = True
            last_base_answer_pre_synthesis = base_answer_pre_synth

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
            external_results=accumulated_external,
            last_sub_results=last_sub_results,
            synthesis_used=last_synthesis_used,
            base_answer_pre_synthesis=last_base_answer_pre_synthesis,
            synthesis_method=last_synthesis_method,
            synthesis_fallback_reason=last_synthesis_fallback_reason,
        )


def _route_to_names(route: SourceRoute) -> set[str]:
    names = set()
    if route.use_vector:
        names.add("vector")
    if route.use_sql:
        names.add("sql")
    if route.use_graph:
        names.add("graph")
    # v2.5 Tier B: 정확한 외부 도구 이름 사용 (예: "umls", "pubmed")
    if route.external_tools:
        names.update(route.external_tools)
    elif route.use_external_tool:
        names.add("external_tool")
    return names


def _format_umls_md(results: list[dict]) -> str:
    """UMLS 결과 → markdown 섹션."""
    lines = ["[UMLS Cross-Walk] (외부)"]
    for r in results:
        cui = r.get("cui", "")
        name = r.get("name", "")
        lines.append(f"- {cui} {name}".rstrip())
        xw = r.get("cross_walks") or {}
        if xw:
            xw_str = " / ".join(
                f"{src}: {','.join(codes[:3])}" for src, codes in xw.items()
            )
            lines.append(f"  {xw_str}")
    return "\n".join(lines)


def _format_pubmed_md(results: list[dict]) -> str:
    """PubMed 결과 → markdown 섹션."""
    lines = ["[PubMed Evidence] (외부)"]
    for r in results:
        year = r.get("year", "")
        journal = r.get("journal", "")
        title = r.get("title", "")
        pmid = r.get("pmid", "")
        authors = r.get("authors") or []
        if len(authors) > 1:
            author_str = f"{authors[0]} et al."
        elif authors:
            author_str = authors[0]
        else:
            author_str = ""
        meta = " — ".join(
            x for x in [f"{year} {journal}".strip(), title, f"PMID {pmid}", author_str] if x
        )
        lines.append(f"- {meta}")
    return "\n".join(lines)


def _format_web_md(results: list[dict]) -> str:
    """Tavily Web Search 결과 → markdown 섹션 (v2.7 R-3)."""
    lines = ["[Web Search] (외부)"]
    for r in results:
        title = (r.get("title") or "").strip()
        url = (r.get("url") or "").strip()
        score = r.get("score", 0.0)
        content = (r.get("content") or "").strip()
        # 본문 200자 cut, 줄바꿈 제거
        snippet = content.replace("\n", " ")[:200]
        if snippet and len(content) > 200:
            snippet += "…"
        meta = f"- [{title}]({url})" if url else f"- {title}"
        if score:
            meta += f" (score={score:.2f})"
        lines.append(meta)
        if snippet:
            lines.append(f"  {snippet}")
    return "\n".join(lines)


def _dedup_external(acc: dict[str, list]) -> dict[str, list]:
    """v2.8 R-7: 누적 external_results에서 source별 식별자 기준 dedup.

    - umls: cui
    - pubmed: pmid
    - web: url
    - 그 외: 그대로 유지 (식별자 미정)
    식별자 결측 항목은 제거하지 않고 보존(첫 등장 순서 유지).
    """
    keys = {"umls": "cui", "pubmed": "pmid", "web": "url"}
    result: dict[str, list] = {}
    for tool, items in acc.items():
        id_key = keys.get(tool)
        if id_key is None:
            result[tool] = list(items)
            continue
        seen: set = set()
        uniq: list = []
        for r in items:
            v = (r or {}).get(id_key, "")
            if v and v in seen:
                continue
            if v:
                seen.add(v)
            uniq.append(r)
        result[tool] = uniq
    return result


def _route_to_dict(route: SourceRoute) -> dict:
    return {
        "vector_weight": route.vector_weight,
        "sql_weight": route.sql_weight,
        "use_graph": route.use_graph,
        "use_external_tool": route.use_external_tool,
        "reasoning": route.reasoning,
    }
