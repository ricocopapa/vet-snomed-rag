#!/usr/bin/env python3
"""
Day 3 A1 후속: 11쿼리 × 4모드 전체 회귀 측정 스크립트.

4모드:
  M1: rerank=False, reformulator="none"       (v1.0 baseline 재현)
  M2: rerank=False, reformulator="gemini"     (reformulator only)
  M3: rerank=True,  reformulator="none"       (rerank only)
  M4: rerank=True,  reformulator="gemini"     (v2.0 후보)

각 쿼리 3회 측정 → 평균 latency 계산 (총 11×4×3 = 132회 실행).

출력: benchmark/reranker_regression_raw.json
"""

import json
import os
import sys
import time
from pathlib import Path
from statistics import mean, quantiles

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .env 로드
env_path = PROJECT_ROOT / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

from src.retrieval.rag_pipeline import SNOMEDRagPipeline

# 회귀 세트 로드
REGRESSION_JSON = PROJECT_ROOT / "graphify_out" / "regression_metrics.json"
with open(REGRESSION_JSON) as f:
    queries = json.load(f)

# 모드 정의
MODES = [
    {"mode_id": "M1", "label": "rerank=False, reformulator=none",   "rerank": False, "reformulator": "none"},
    {"mode_id": "M2", "label": "rerank=False, reformulator=gemini",  "rerank": False, "reformulator": "gemini"},
    {"mode_id": "M3", "label": "rerank=True,  reformulator=none",    "rerank": True,  "reformulator": "none"},
    {"mode_id": "M4", "label": "rerank=True,  reformulator=gemini",  "rerank": True,  "reformulator": "gemini"},
]

REPEATS = 3  # 각 쿼리 반복 횟수


def build_pipeline(rerank: bool, reformulator: str) -> SNOMEDRagPipeline:
    """모드별 파이프라인을 생성한다."""
    return SNOMEDRagPipeline(
        llm_backend="none",
        reformulator_backend=reformulator,
        enable_rerank=rerank,
    )


def measure_query(pipeline: SNOMEDRagPipeline, q: dict, rerank: bool, repeats: int) -> dict:
    """단일 쿼리를 repeats회 측정하여 통계를 반환한다."""
    query_text = q["query_text"]
    expected_id = q.get("expected_concept_id")

    latencies = []
    top1_ids = []
    top1_terms = []
    rank_of_corrects = []

    for _ in range(repeats):
        t0 = time.perf_counter()
        result = pipeline.query(query_text, top_k=10, rerank=rerank)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        results = result.get("search_results", [])

        top1_id = results[0].concept_id if results else None
        top1_term = results[0].preferred_term if results else None

        # 정답 순위 계산
        rank = None
        if expected_id:
            for i, r in enumerate(results, 1):
                if r.concept_id == expected_id:
                    rank = i
                    break

        latencies.append(elapsed_ms)
        top1_ids.append(top1_id)
        top1_terms.append(top1_term)
        rank_of_corrects.append(rank)

    # 대표값: 3회 중 마지막 top1 (warm cache)
    top1_id = top1_ids[-1]
    top1_term = top1_terms[-1]
    rank = rank_of_corrects[-1]

    # PASS/FAIL/NA 판정
    if expected_id is None:
        verdict = "NA"
    elif top1_id == expected_id:
        verdict = "PASS"
    else:
        verdict = "FAIL"

    # MRR (Mean Reciprocal Rank): rank 기반
    if rank is not None:
        mrr_contribution = 1.0 / rank
    elif expected_id is None:
        mrr_contribution = None  # NA 쿼리는 MRR 계산에서 제외
    else:
        mrr_contribution = 0.0

    return {
        "top1_concept_id": top1_id,
        "top1_term": top1_term,
        "rank_of_correct": rank,
        "verdict": verdict,
        "mrr_contribution": mrr_contribution,
        "latency_all_ms": latencies,
        "latency_avg_ms": int(mean(latencies)),
        "latency_p50_ms": int(sorted(latencies)[len(latencies)//2]),
        "reformulation": result.get("reformulation"),
    }


def run_all():
    raw_results = []
    all_latencies_by_mode = {m["mode_id"]: [] for m in MODES}

    for mode in MODES:
        mode_id = mode["mode_id"]
        label = mode["label"]
        rerank_flag = mode["rerank"]
        reformulator = mode["reformulator"]

        print(f"\n{'='*60}")
        print(f"  모드: {mode_id} ({label})")
        print(f"{'='*60}")

        pipeline = build_pipeline(rerank=rerank_flag, reformulator=reformulator)

        mode_results = []
        for q in queries:
            qid = q["query_id"]
            qtext = q["query_text"]
            print(f"  [{qid}] {qtext[:50]}...", end=" ", flush=True)

            qr = measure_query(pipeline, q, rerank=rerank_flag, repeats=REPEATS)
            qr["query_id"] = qid
            qr["query_text"] = qtext
            qr["expected_concept_id"] = q.get("expected_concept_id")
            qr["mode_id"] = mode_id

            print(f"→ {qr['verdict']:4s} | top1={qr['top1_term'][:30] if qr['top1_term'] else 'N/A'} | {qr['latency_avg_ms']}ms")

            mode_results.append(qr)
            all_latencies_by_mode[mode_id].extend(qr["latency_all_ms"])

        pipeline.close()
        raw_results.append({
            "mode": mode,
            "queries": mode_results,
        })

    # p95 latency 계산
    for mode_data in raw_results:
        mid = mode_data["mode"]["mode_id"]
        lats = sorted(all_latencies_by_mode[mid])
        n = len(lats)
        p50 = lats[n//2]
        p95_idx = int(n * 0.95)
        p95 = lats[min(p95_idx, n-1)]
        mode_data["latency_summary"] = {
            "all_count": n,
            "p50_ms": p50,
            "p95_ms": p95,
            "avg_ms": int(mean(lats)),
        }

        # PASS/FAIL/NA 집계 (NA 제외한 집계)
        verdicts = [q["verdict"] for q in mode_data["queries"]]
        na_count = verdicts.count("NA")
        evaluable = [v for v in verdicts if v != "NA"]
        pass_count = evaluable.count("PASS")
        fail_count = evaluable.count("FAIL")

        # MRR (NA 쿼리 제외)
        mrr_contribs = [q["mrr_contribution"] for q in mode_data["queries"] if q["mrr_contribution"] is not None]
        mrr = mean(mrr_contribs) if mrr_contribs else 0.0

        mode_data["summary"] = {
            "total_queries": len(queries),
            "na_count": na_count,
            "evaluable_count": len(evaluable),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "pass_rate": f"{pass_count}/{len(evaluable)}",
            "mrr": round(mrr, 4),
        }

        print(f"\n[{mid}] 요약: PASS {pass_count}/{len(evaluable)} | MRR={mrr:.4f} | p95={p95}ms | p50={p50}ms")

    # 저장
    out_path = PROJECT_ROOT / "benchmark" / "reranker_regression_raw.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)

    print(f"\n원시 데이터 저장 완료: {out_path}")
    return raw_results


if __name__ == "__main__":
    run_all()
