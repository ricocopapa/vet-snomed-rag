"""v2.5 Tier A smoke test — 백엔드 분기 실행 시그니처 검증.

검증 항목:
1. rag_pipeline.SNOMEDRagPipeline.query() 시그니처에 source_route 파라미터 존재
2. agentic.SourceRoute import 정상
3. AgenticRAGPipeline 모듈 import + base.query() 호출 인자 source_route=route 포함
4. SourceRoute weight·use_graph 분기가 query() 본문에 반영됨 (정적 검사)

본 smoke는 인덱스/LLM 호출 없이 import + 정적 검증만 수행.
실측 회귀는 scripts/run_regression.py 별도 실행.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def check(name: str, cond: bool, detail: str = "") -> bool:
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    return cond


def main() -> int:
    print("v2.5 Tier A smoke — Agentic RAG 백엔드 분기 실행")
    print("=" * 60)
    fails = 0

    # ── #1 SourceRoute import ────────────────────────────────
    try:
        from src.retrieval.agentic.source_router import SourceRoute, SourceRouterAgent
        sr_ok = True
    except Exception as e:
        sr_ok = False
        print(f"  [FAIL] SourceRoute import — {e}")
    fails += 0 if check("#1 SourceRoute / SourceRouterAgent import", sr_ok) else 1
    if not sr_ok:
        return 1

    # ── #2 SNOMEDRagPipeline.query() 시그니처 ─────────────────
    from src.retrieval.rag_pipeline import SNOMEDRagPipeline
    sig = inspect.signature(SNOMEDRagPipeline.query)
    has_param = "source_route" in sig.parameters
    fails += 0 if check(
        "#2 SNOMEDRagPipeline.query()에 source_route 파라미터 존재",
        has_param,
        f"params={list(sig.parameters)}",
    ) else 1

    if has_param:
        p = sig.parameters["source_route"]
        default_none = p.default is None
        fails += 0 if check(
            "#3 source_route default = None (v2.4 회귀 0 보장)",
            default_none,
            f"default={p.default!r}",
        ) else 1

    # ── #4 AgenticRAGPipeline import + 호출 인자 검증 ─────────
    try:
        from src.retrieval.agentic_pipeline import AgenticRAGPipeline
        ap_ok = True
    except Exception as e:
        ap_ok = False
        print(f"  [FAIL] AgenticRAGPipeline import — {e}")
    fails += 0 if check("#4 AgenticRAGPipeline import", ap_ok) else 1

    # ── #5 정적 본문 검사: agentic_pipeline에서 base.query()에 source_route 전달 ─
    ap_path = PROJECT_ROOT / "src" / "retrieval" / "agentic_pipeline.py"
    src = ap_path.read_text(encoding="utf-8")
    has_route_pass = "source_route=route" in src
    fails += 0 if check(
        "#5 agentic_pipeline.py에서 base.query()로 source_route 전달",
        has_route_pass,
    ) else 1

    # ── #6 정적 본문 검사: rag_pipeline에서 weight 동적 주입 ───
    rp_path = PROJECT_ROOT / "src" / "retrieval" / "rag_pipeline.py"
    rsrc = rp_path.read_text(encoding="utf-8")
    has_vw = "vector_weight=_vw" in rsrc
    has_sw = "sql_weight=_sw" in rsrc
    has_use_graph = "_use_graph" in rsrc and "if _use_graph:" in rsrc
    fails += 0 if check("#6a rag_pipeline.py vector_weight=_vw", has_vw) else 1
    fails += 0 if check("#6b rag_pipeline.py sql_weight=_sw", has_sw) else 1
    fails += 0 if check("#6c rag_pipeline.py if _use_graph: 분기", has_use_graph) else 1

    # ── #7 SourceRoute 데이터클래스 필드 확인 ────────────────
    expected_fields = {"use_vector", "use_sql", "use_graph", "use_external_tool",
                       "vector_weight", "sql_weight", "reasoning"}
    sr_fields = set(SourceRoute.__dataclass_fields__.keys())
    fails += 0 if check(
        "#7 SourceRoute 필드 완비",
        expected_fields.issubset(sr_fields),
        f"missing={expected_fields - sr_fields}",
    ) else 1

    # ── #8 SourceRouterAgent.route() 동작 (룰 기반, LLM 미호출) ──
    router = SourceRouterAgent(backend="rule_based")
    r_ko = router.route("고양이 당뇨")
    r_id = router.route("SNOMED code 73211009")
    r_graph = router.route("당뇨의 상위 개념")
    fails += 0 if check(
        "#8a 한국어 자연어 → vector-heavy",
        r_ko.vector_weight > r_ko.sql_weight,
        f"vw={r_ko.vector_weight}, sw={r_ko.sql_weight}",
    ) else 1
    fails += 0 if check(
        "#8b concept_id 패턴 → sql-heavy",
        r_id.sql_weight > r_id.vector_weight,
        f"vw={r_id.vector_weight}, sw={r_id.sql_weight}",
    ) else 1
    fails += 0 if check(
        "#8c 상위/하위 키워드 → use_graph=True",
        r_graph.use_graph is True,
    ) else 1

    print("=" * 60)
    if fails == 0:
        print(f"RESULT: PASS (0 failures)")
        return 0
    else:
        print(f"RESULT: FAIL ({fails} failures)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
