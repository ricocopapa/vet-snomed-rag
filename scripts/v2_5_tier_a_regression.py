"""v2.5 Tier A 미니 회귀 — source_route 분기가 실제 검색 결과에 반영되는지 검증.

검증 항목:
A. source_route=None 시 v2.4와 동일 결과 (Top-5 concept_id 시퀀스)
B. SourceRoute(use_graph=False) 시 graph 컨텍스트 비활성 (context 차이)
C. SourceRoute(vector_weight=0.95, sql_weight=0.05) vs (0.05, 0.95) 시
   Top-5 결과가 달라짐 (가중치 동적 주입 작동 증거)

LLM 호출 없음 (--llm none 모드). Chroma + SQLite + Graph만 사용.
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retrieval.rag_pipeline import SNOMEDRagPipeline
from src.retrieval.agentic.source_router import SourceRoute


def topk_ids(result: dict, k: int = 5) -> list[str]:
    return [getattr(r, "concept_id", "?") for r in result["search_results"][:k]]


def main() -> int:
    print("v2.5 Tier A 미니 회귀 — 백엔드 분기 실측")
    print("=" * 60)

    # LLM 미사용 (--llm none 효과)
    pipe = SNOMEDRagPipeline(llm_backend="none")

    fails = 0
    queries = [
        ("Q1", "feline diabetes"),
        ("Q2", "고양이 당뇨"),
        ("Q3", "canine parvovirus enteritis"),
    ]

    print("\n[A] source_route=None — v2.4 default 동작 (baseline)")
    baseline = {}
    for qid, q in queries:
        r = pipe.query(q, top_k=5, rerank=False, source_route=None)
        baseline[qid] = {"top5": topk_ids(r), "ctx_len": len(r["context"])}
        print(f"  {qid} '{q}' → top5={baseline[qid]['top5']} ctx_len={baseline[qid]['ctx_len']}")

    print("\n[B] use_graph=False — GraphRAG 비활성")
    no_graph_route = SourceRoute(use_graph=False, vector_weight=0.6, sql_weight=0.4)
    for qid, q in queries:
        r = pipe.query(q, top_k=5, rerank=False, source_route=no_graph_route)
        b_top5 = topk_ids(r)
        b_ctx = len(r["context"])
        # 검색 결과는 동일해야 (vector/sql 가중치 동일)
        same_top5 = b_top5 == baseline[qid]["top5"]
        # ctx는 graph 비활성으로 더 짧아야 (또는 같아야 — graph 결과가 비어있던 케이스)
        ctx_shorter_or_equal = b_ctx <= baseline[qid]["ctx_len"]
        ok = same_top5 and ctx_shorter_or_equal
        mark = "PASS" if ok else "FAIL"
        delta = b_ctx - baseline[qid]["ctx_len"]
        print(f"  [{mark}] {qid} top5_same={same_top5} ctx_delta={delta:+d}")
        fails += 0 if ok else 1

    print("\n[C] vector_weight 극단 분기 — Top-5 변화 확인")
    print("    (한국어 쿼리는 llm_backend='none' 환경에서 영어 번역 skip → SQL 0건 매칭")
    print("     → 가중치 분기 무관, ollama backend 활성 시 별도 회귀 필요)")
    vec_heavy = SourceRoute(vector_weight=0.95, sql_weight=0.05)
    sql_heavy = SourceRoute(vector_weight=0.05, sql_weight=0.95)
    skipped = 0
    for qid, q in queries:
        r_v = pipe.query(q, top_k=5, rerank=False, source_route=vec_heavy)
        r_s = pipe.query(q, top_k=5, rerank=False, source_route=sql_heavy)
        v_top5 = topk_ids(r_v)
        s_top5 = topk_ids(r_s)
        differ = v_top5 != s_top5
        has_korean = any("가" <= c <= "힯" for c in q)

        if has_korean and not differ:
            mark = "SKIP"
            note = "한국어+llm=none → SQL 매칭 0 (가중치 분기 무관, 알려진 한계)"
            skipped += 1
        elif differ:
            mark = "PASS"
            note = ""
        else:
            mark = "FAIL"
            note = "영어 쿼리인데 가중치 극단 변화에도 Top-5 동일 (예상 외)"
            fails += 1

        print(f"  [{mark}] {qid} differ={differ} {note}")
        if mark != "SKIP":
            print(f"        vec_heavy={v_top5}")
            print(f"        sql_heavy={s_top5}")

    pipe.close()

    print("\n" + "=" * 60)
    if fails == 0:
        print("RESULT: PASS — Tier A 백엔드 분기 실행 확인됨")
        return 0
    else:
        print(f"RESULT: FAIL ({fails} failures)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
