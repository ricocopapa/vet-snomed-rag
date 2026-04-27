"""scripts/v3_1_korean_extension_validation.py — v3.1 한국어 dataset 확장 1차 검증.

[목적]   R-9 Phase 2 정직 지적사항 — N-ko-03 백내장·N-ko-04 녹내장 (1,000-pool 미해소) +
         기타 한국어 dataset (Phase 2 N-ko-01~08 + T9·T10·T11 = 11건)을 본 production
         파이프라인 (BGE-M3 + 한국어 사전 + Gemini reformulate + BGE-rerank-v2-m3) RERANK=1
         환경에서 측정. 사전(v1.2: 백내장·녹내장 등록 확인) 통합 효과 정량.

[가설]   Phase 2 단독 BGE-M3에서 미해소된 백내장·녹내장이 한국어 사전 v1.2 (cataract/glaucoma
         등록) 거치면 영어 매핑 → BGE-M3 영어 매칭 정확 → PASS 가능성 높음.

[측정]   11쿼리 × backend(none + gemini) × RERANK=1 → rank @1·@5·@10 + production hits 비율

산출:    graphify_out/v3_1_korean_extension.json + .log
실행:    RERANK=1 venv/bin/python scripts/v3_1_korean_extension_validation.py
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.retrieval.rag_pipeline import SNOMEDRagPipeline


# 한국어 11쿼리 (R-8 r8_phase2_query_dataset.json에서 language=ko 추출)
KOREAN_QUERIES = [
    ("T9",      "고양이 당뇨",                           "73211009"),
    ("T10",     "개 췌장염",                             "75694006"),
    ("T11",     "고양이 범백혈구감소증 SNOMED 코드",     "339181000009108"),
    ("N-ko-01", "갑상선 기능 저하증",                    "40930008"),
    ("N-ko-02", "갑상선 기능 항진증",                    "34486009"),
    ("N-ko-03", "백내장",                                "193570009"),  # ★ Phase 2 단독 미해소
    ("N-ko-04", "녹내장",                                "23986001"),   # ★ Phase 2 단독 미해소
    ("N-ko-05", "외이염",                                "3135009"),
    ("N-ko-06", "심장 잡음",                             "88610006"),
    ("N-ko-07", "고관절 이형성증",                       "52781008"),
    ("N-ko-08", "림프종",                                "118600007"),
]

ENABLE_RERANK = os.environ.get("RERANK", "").lower() in ("1", "true", "yes")
if ENABLE_RERANK:
    print("[INFO] RERANK=1 — BGEReranker 활성")
else:
    print("[WARN] RERANK 미설정 — RERANK=1 환경변수 권장 (production 파이프라인 일치)")


def find_rank(search_results, expected: str) -> int:
    """expected concept_id가 search_results의 몇 위인지 반환. 없으면 11."""
    for i, r in enumerate(search_results):
        if r.concept_id == expected:
            return i + 1
    return 11


def measure_backend(reformulator_backend: str) -> list[dict]:
    print(f"\n{'='*70}")
    print(f" Reformulator backend: {reformulator_backend}")
    print(f"{'='*70}")

    pipeline = SNOMEDRagPipeline(
        llm_backend="none",
        reformulator_backend=reformulator_backend,
        enable_rerank=ENABLE_RERANK,
    )

    rows = []
    for qid, qtext, gold in KOREAN_QUERIES:
        # Gemini Free Tier rate limit (5 RPM = 12s 간격, 13s 보수)
        if reformulator_backend == "gemini":
            time.sleep(13)

        print(f"\n[{qid}] {qtext}  (gold: {gold})")
        try:
            t0 = time.perf_counter()
            result = pipeline.query(qtext, top_k=10, rerank=ENABLE_RERANK)
            latency = int((time.perf_counter() - t0) * 1000)

            search_results = result["search_results"]
            rank = find_rank(search_results, gold)
            top1 = search_results[0].concept_id if search_results else "N/A"
            top1_term = search_results[0].preferred_term if search_results else ""
            verdict = "PASS" if rank == 1 else (f"rank={rank}")
            print(f"  [{reformulator_backend}] top1={top1} ({top1_term}) rank={rank} verdict={verdict} ({latency}ms)")

            row = {
                "qid": qid,
                "query": qtext,
                "gold": gold,
                "backend": reformulator_backend,
                "rank": rank,
                "top1_id": top1,
                "top1_term": top1_term,
                "in_top1": rank == 1,
                "in_top5": rank <= 5,
                "in_top10": rank <= 10,
                "latency_ms": latency,
            }
            if reformulator_backend == "gemini" and result.get("reformulation"):
                ref = result["reformulation"]
                row.update({
                    "reformulated": ref.get("reformulated"),
                    "confidence": ref.get("confidence"),
                })
            rows.append(row)
        except Exception as e:
            print(f"  [{reformulator_backend}] ERROR: {type(e).__name__}: {e}")
            rows.append({
                "qid": qid,
                "query": qtext,
                "gold": gold,
                "backend": reformulator_backend,
                "error": f"{type(e).__name__}: {e}",
            })

    return rows


def main() -> int:
    all_rows = []
    for backend in ("none", "gemini"):
        try:
            all_rows.extend(measure_backend(backend))
        except Exception as e:
            print(f"[ERROR] backend={backend} 초기화 실패: {e}")

    # 집계
    print(f"\n{'='*70}")
    print(" 종합 결과 (한국어 11쿼리 production 회귀 RERANK=1)")
    print(f"{'='*70}")
    for backend in ("none", "gemini"):
        bb = [r for r in all_rows if r.get("backend") == backend and "rank" in r]
        if not bb:
            continue
        rank1 = sum(1 for r in bb if r["rank"] == 1)
        rank5 = sum(1 for r in bb if r["rank"] <= 5)
        rank10 = sum(1 for r in bb if r["rank"] <= 10)
        print(f"  [{backend:6s}] rank-1: {rank1:>2}/{len(bb)}  rank≤5: {rank5}/{len(bb)}  rank≤10: {rank10}/{len(bb)}")

    print(f"\n{'─'*70}")
    print(" Phase 2 단독 미해소 (백내장·녹내장) production 결과")
    print(f"{'─'*70}")
    for qid in ("N-ko-03", "N-ko-04"):
        for backend in ("none", "gemini"):
            for r in all_rows:
                if r.get("qid") == qid and r.get("backend") == backend and "rank" in r:
                    verdict = "PASS ★" if r["rank"] == 1 else f"rank={r['rank']}"
                    print(f"  {qid:8s} [{backend:6s}] {verdict}  top1={r['top1_id']} ({r.get('top1_term','')[:40]})")

    # JSON 저장
    out_path = PROJECT_ROOT / "graphify_out" / "v3_1_korean_extension.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "purpose": "v3.1 R-1 한국어 11쿼리 production 회귀 (백내장·녹내장 통합 검증)",
            "source": "R-8 r8_phase2_query_dataset.json korean-reformulate 11건",
            "rerank": ENABLE_RERANK,
            "embedder": "BAAI/bge-m3 (production)",
            "production_pipeline": "BGE-M3 + Korean dictionary (vet_term_dictionary_ko_en.json v1.2) + Gemini reformulate (gemini backend) + BGE-rerank-v2-m3",
        },
        "queries": [{"qid": q[0], "query": q[1], "gold": q[2]} for q in KOREAN_QUERIES],
        "results": all_rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[저장] {out_path.relative_to(PROJECT_ROOT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
