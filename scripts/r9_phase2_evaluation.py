"""scripts/r9_phase2_evaluation.py — R-9 Phase 2 Step 2: C1 vs M0 baseline 100쿼리 평가.

[설계서] docs/20260427_r9_phase2_handoff.md §2-3 Step 2
[목적]   C1 BGE-M3 (1024d) vs M0 baseline all-MiniLM-L6-v2 (384d) — 1,000-pool × 100쿼리.

R-8 r8_phase2_evaluation.py 패턴 재사용. MODELS C1 + baseline (M0 ChromaDB R-8 재사용).
판단 기준 §2-2 R-9 적용 (한국어 hits 1차 + 영어 무손실 2차).

지표:
  rank_of_correct: gold concept_id가 top-10 안 몇 위 (없으면 11+, reciprocal=0)
  MRR@10  = mean(1 / rank if rank ≤ 10 else 0)
  Recall@10 = (rank ≤ 10) 비율
  Recall@5  = (rank ≤ 5)  비율

§2-2 판단 기준:
  ① 한국어 hits@10 ≥ 5/11
  ② 영어  hits@10 ≥ 89/89 (R-8 baseline 동일)
  ③ MRR@10 / Recall@10 (참고 절대값)

산출:
  graphify_out/r9_phase2_metrics.json (per-query + aggregated + decision)

실행: venv/bin/python scripts/r9_phase2_evaluation.py 2>&1 | tee graphify_out/r9_phase2_eval.log
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERY_PATH = PROJECT_ROOT / "data" / "r8_phase2_query_dataset.json"
SAMPLE_PATH = PROJECT_ROOT / "data" / "r8_phase2_sample_concepts.json"
OUT_PATH = PROJECT_ROOT / "graphify_out" / "r9_phase2_metrics.json"

CHROMA_PATHS = {
    "M0_baseline": PROJECT_ROOT / "data" / "chroma_phase2_baseline",  # R-8 재사용
    "C1_bge_m3":   PROJECT_ROOT / "data" / "chroma_phase2_c1_bge_m3",
}

COLLECTION_NAME = "phase2_concepts"
TOP_K = 10


def encode_sentence_transformers(model_name: str):
    from sentence_transformers import SentenceTransformer
    print(f"  [load] {model_name}")
    model = SentenceTransformer(model_name)

    def _encode(texts: list[str]) -> np.ndarray:
        return np.asarray(model.encode(texts, normalize_embeddings=False, show_progress_bar=False))

    return _encode


MODELS = [
    ("M0_baseline", "sentence-transformers/all-MiniLM-L6-v2", "st"),
    ("C1_bge_m3",   "BAAI/bge-m3",                            "st"),
]


def evaluate_model(model_id: str, hf_id: str, kind: str, queries: list[dict]) -> list[dict]:
    import chromadb

    print(f"\n=== {model_id} ===")
    if kind == "st":
        encode = encode_sentence_transformers(hf_id)
    else:
        raise ValueError(kind)

    query_texts = [q["query_text"] for q in queries]
    t0 = time.time()
    qe = encode(query_texts)
    print(f"  [encode] {len(query_texts)} queries in {time.time()-t0:.1f}s, shape={qe.shape}")

    client = chromadb.PersistentClient(path=str(CHROMA_PATHS[model_id]))
    col = client.get_collection(name=COLLECTION_NAME)
    print(f"  [chroma] collection count={col.count()}")

    results = []
    for q, vec in zip(queries, qe):
        res = col.query(
            query_embeddings=[vec.tolist()],
            n_results=TOP_K,
        )
        top_ids = res["ids"][0]
        top_dists = res["distances"][0]
        gold = q["gold_concept_id"]
        rank = (top_ids.index(gold) + 1) if gold in top_ids else (TOP_K + 1)
        results.append(
            {
                "qid": q["qid"],
                "query_text": q["query_text"],
                "category": q["category"],
                "language": q.get("language", "en"),
                "gold_concept_id": gold,
                "rank_of_correct": rank,
                "in_top10": rank <= TOP_K,
                "in_top5": rank <= 5,
                "top_1_id": top_ids[0],
                "top_1_distance": float(top_dists[0]),
                "model_id": model_id,
            }
        )

    return results


def aggregate(results: list[dict]) -> dict:
    """전체 + 카테고리별 + 언어별 metric."""
    n = len(results)
    if n == 0:
        return {}

    def _metrics(rs: list[dict]) -> dict:
        if not rs:
            return {"n": 0}
        n_ = len(rs)
        mrr = sum((1.0 / r["rank_of_correct"]) if r["rank_of_correct"] <= TOP_K else 0.0 for r in rs) / n_
        rec10 = sum(1 for r in rs if r["in_top10"]) / n_
        rec5 = sum(1 for r in rs if r["in_top5"]) / n_
        return {
            "n": n_,
            "MRR@10": round(mrr, 4),
            "Recall@10": round(rec10, 4),
            "Recall@5": round(rec5, 4),
            "hits@10": sum(1 for r in rs if r["in_top10"]),
            "hits@5": sum(1 for r in rs if r["in_top5"]),
        }

    overall = _metrics(results)
    by_cat: dict[str, dict] = {}
    for cat in sorted({r["category"] for r in results}):
        by_cat[cat] = _metrics([r for r in results if r["category"] == cat])
    by_lang: dict[str, dict] = {}
    for lang in sorted({r["language"] for r in results}):
        by_lang[lang] = _metrics([r for r in results if r["language"] == lang])

    return {"overall": overall, "by_category": by_cat, "by_language": by_lang}


def evaluate_decision(agg: dict[str, dict]) -> dict:
    """§2-2 판단 기준 1:1 PASS/FAIL.

    R-9 임계:
      ① 한국어 hits@10 ≥ 5/11
      ② 영어  hits@10 ≥ 89/89
      참고: MRR@10 / Recall@10 baseline 절대 비교 (PASS 조건 아님, 정보)
    """
    base = agg["M0_baseline"]
    base_overall = base["overall"]
    base_lang = base["by_language"]

    base_ko_hits = base_lang.get("ko", {}).get("hits@10", 0)
    base_ko_n = base_lang.get("ko", {}).get("n", 11)
    base_en_hits = base_lang.get("en", {}).get("hits@10", 0)
    base_en_n = base_lang.get("en", {}).get("n", 89)

    decisions: list[dict] = []
    for model_id in ("C1_bge_m3",):
        ov = agg[model_id]["overall"]
        ml = agg[model_id]["by_language"]

        ko_hits = ml.get("ko", {}).get("hits@10", 0)
        ko_n = ml.get("ko", {}).get("n", 11)
        en_hits = ml.get("en", {}).get("hits@10", 0)
        en_n = ml.get("en", {}).get("n", 89)

        c_ko = ko_hits >= 5
        c_en = en_hits >= 89

        decisions.append(
            {
                "model_id": model_id,
                "korean_hits@10": ko_hits,
                "korean_n": ko_n,
                "korean_threshold (>=5)": 5,
                "Korean_PASS": c_ko,
                "english_hits@10": en_hits,
                "english_n": en_n,
                "english_threshold (>=89)": 89,
                "English_PASS": c_en,
                "MRR@10": ov["MRR@10"],
                "baseline_MRR@10": base_overall["MRR@10"],
                "Recall@10": ov["Recall@10"],
                "baseline_Recall@10": base_overall["Recall@10"],
                "ALL_PASS_for_phase3": c_ko and c_en,
            }
        )

    return {
        "baseline": {
            "overall": base_overall,
            "korean_hits@10": base_ko_hits,
            "korean_n": base_ko_n,
            "english_hits@10": base_en_hits,
            "english_n": base_en_n,
        },
        "candidates": decisions,
    }


def main() -> int:
    if not QUERY_PATH.exists():
        print(f"[ERROR] query 없음: {QUERY_PATH}", file=sys.stderr)
        return 1
    if not SAMPLE_PATH.exists():
        print(f"[ERROR] sample 없음: {SAMPLE_PATH}", file=sys.stderr)
        return 1
    for model_id, path in CHROMA_PATHS.items():
        if not path.exists():
            print(f"[ERROR] ChromaDB 없음: {path} (Step 1 r9_phase2_build_indices_c1.py 먼저 실행)", file=sys.stderr)
            return 1

    queries = json.loads(QUERY_PATH.read_text())["queries"]
    print(f"[INFO] loaded {len(queries)} queries")

    all_results: dict[str, list[dict]] = {}
    aggregated: dict[str, dict] = {}
    for model_id, hf_id, kind in MODELS:
        results = evaluate_model(model_id, hf_id, kind, queries)
        all_results[model_id] = results
        aggregated[model_id] = aggregate(results)

        # console summary
        ov = aggregated[model_id]["overall"]
        ml = aggregated[model_id]["by_language"]
        ko_hits = ml.get("ko", {}).get("hits@10", 0)
        ko_n = ml.get("ko", {}).get("n", 0)
        en_hits = ml.get("en", {}).get("hits@10", 0)
        en_n = ml.get("en", {}).get("n", 0)
        print(
            f"  [agg] MRR@10={ov['MRR@10']}  Recall@10={ov['Recall@10']}  Recall@5={ov['Recall@5']}  "
            f"ko={ko_hits}/{ko_n}  en={en_hits}/{en_n}"
        )

    decision = evaluate_decision(aggregated)

    print("\n=== DECISION (§2-2 판단 기준) ===")
    base = decision["baseline"]
    print(
        f"baseline: MRR@10={base['overall']['MRR@10']}  Recall@10={base['overall']['Recall@10']}  "
        f"ko={base['korean_hits@10']}/{base['korean_n']}  en={base['english_hits@10']}/{base['english_n']}"
    )
    for c in decision["candidates"]:
        marks = []
        marks.append(f"ko hits={'✓' if c['Korean_PASS'] else '✗'}({c['korean_hits@10']}/{c['korean_n']} vs ≥5)")
        marks.append(f"en hits={'✓' if c['English_PASS'] else '✗'}({c['english_hits@10']}/{c['english_n']} vs ≥89)")
        marks.append(f"MRR@10={c['MRR@10']} (baseline {c['baseline_MRR@10']})")
        marks.append(f"Recall@10={c['Recall@10']} (baseline {c['baseline_Recall@10']})")
        verdict = "PASS" if c["ALL_PASS_for_phase3"] else "FAIL"
        print(f"  {c['model_id']:18s} → {verdict}  | " + "  ".join(marks))

    payload = {
        "_metadata": {
            "handoff": "docs/20260427_r9_phase2_handoff.md §2-3 Step 2",
            "n_queries": len(queries),
            "n_samples": 1000,
            "top_k": TOP_K,
            "models": [m[0] for m in MODELS],
            "thresholds_R9": {
                "korean_hits@10": ">= 5/11",
                "english_hits@10": ">= 89/89",
            },
        },
        "per_query": all_results,
        "aggregated": aggregated,
        "decision_2_2": decision,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Wrote {OUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
