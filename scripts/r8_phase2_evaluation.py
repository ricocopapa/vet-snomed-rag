"""scripts/r8_phase2_evaluation.py — R-8 Phase 2 Step 4: 100쿼리 평가.

[설계서] docs/20260427_r8_phase2_handoff.md §3-3 Step 4
[목적]   3 임시 ChromaDB(M0/M2/M3) × 100쿼리 → MRR@10 / Recall@10 / Recall@5 산출.

지표:
  rank_of_correct: gold concept_id가 top-10 안 몇 위 (없으면 11+, 즉 reciprocal=0)
  MRR@10  = mean(1 / rank if rank ≤ 10 else 0)
  Recall@10 = (rank ≤ 10) 비율
  Recall@5  = (rank ≤ 5)  비율 (vet-specific 카테고리 가드용)

산출:
  graphify_out/r8_phase2_metrics.json  (per-query + aggregated)

판단 기준 (§3-2):
  MRR@10                ≥ baseline × 1.05
  Recall@10             ≥ baseline (동일 or 향상)
  vet-specific Recall@5 ≥ baseline × 0.95

실행: venv/bin/python scripts/r8_phase2_evaluation.py 2>&1 | tee graphify_out/r8_phase2_eval.log
"""
from __future__ import annotations

import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUERY_PATH = PROJECT_ROOT / "data" / "r8_phase2_query_dataset.json"
SAMPLE_PATH = PROJECT_ROOT / "data" / "r8_phase2_sample_concepts.json"
OUT_PATH = PROJECT_ROOT / "graphify_out" / "r8_phase2_metrics.json"

CHROMA_PATHS = {
    "M0_baseline": PROJECT_ROOT / "data" / "chroma_phase2_baseline",
    "M2_sapbert_mean": PROJECT_ROOT / "data" / "chroma_phase2_sapbert_mean",
    "M3_neuml": PROJECT_ROOT / "data" / "chroma_phase2_neuml",
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


def encode_huggingface_mean(model_name: str):
    import torch
    from transformers import AutoModel, AutoTokenizer

    print(f"  [load] {model_name} (mean pooling)")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()

    @torch.no_grad()
    def _encode(texts: list[str], batch: int = 32) -> np.ndarray:
        all_vecs = []
        for i in range(0, len(texts), batch):
            chunk = texts[i : i + batch]
            enc = tokenizer(
                chunk, padding=True, truncation=True, max_length=64, return_tensors="pt"
            )
            out = model(**enc)
            last = out.last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).float()
            summed = (last * mask).sum(dim=1)
            denom = mask.sum(dim=1).clamp(min=1e-9)
            vec = (summed / denom).cpu().numpy()
            all_vecs.append(vec)
        return np.concatenate(all_vecs, axis=0)

    return _encode


MODELS = [
    ("M0_baseline", "sentence-transformers/all-MiniLM-L6-v2", "st"),
    ("M2_sapbert_mean", "cambridgeltl/SapBERT-from-PubMedBERT-fulltext", "hf-mean"),
    ("M3_neuml", "NeuML/pubmedbert-base-embeddings", "st"),
]


def evaluate_model(model_id: str, hf_id: str, kind: str, queries: list[dict]) -> list[dict]:
    import chromadb

    print(f"\n=== {model_id} ===")
    if kind == "st":
        encode = encode_sentence_transformers(hf_id)
    elif kind == "hf-mean":
        encode = encode_huggingface_mean(hf_id)
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
    """전체 + 카테고리별 metric."""
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
    """§3-2 판단 기준 1:1 PASS/FAIL."""
    base = agg["M0_baseline"]["overall"]
    base_mrr = base["MRR@10"]
    base_rec10 = base["Recall@10"]

    decisions: list[dict] = []
    for model_id in ("M2_sapbert_mean", "M3_neuml"):
        ov = agg[model_id]["overall"]
        cat_vet = agg[model_id]["by_category"].get("vet-specific", {})
        base_cat_vet = agg["M0_baseline"]["by_category"].get("vet-specific", {})

        mrr = ov["MRR@10"]
        rec10 = ov["Recall@10"]
        vet_rec5 = cat_vet.get("Recall@5", 0)
        base_vet_rec5 = base_cat_vet.get("Recall@5", 1e-9)

        c1 = mrr >= base_mrr * 1.05
        c2 = rec10 >= base_rec10
        c3 = vet_rec5 >= base_vet_rec5 * 0.95

        decisions.append(
            {
                "model_id": model_id,
                "mrr@10": mrr,
                "baseline_mrr@10": base_mrr,
                "mrr_threshold (×1.05)": round(base_mrr * 1.05, 4),
                "MRR_PASS": c1,
                "recall@10": rec10,
                "baseline_recall@10": base_rec10,
                "Recall_PASS": c2,
                "vet_recall@5": vet_rec5,
                "baseline_vet_recall@5": base_vet_rec5,
                "vet_threshold (×0.95)": round(base_vet_rec5 * 0.95, 4),
                "Vet_PASS": c3,
                "ALL_PASS_for_phase3": c1 and c2 and c3,
            }
        )

    return {"baseline": {"MRR@10": base_mrr, "Recall@10": base_rec10}, "candidates": decisions}


def main() -> int:
    if not QUERY_PATH.exists():
        print(f"[ERROR] query 없음: {QUERY_PATH}", file=sys.stderr)
        return 1
    if not SAMPLE_PATH.exists():
        print(f"[ERROR] sample 없음: {SAMPLE_PATH}", file=sys.stderr)
        return 1
    for model_id, path in CHROMA_PATHS.items():
        if not path.exists():
            print(f"[ERROR] ChromaDB 없음: {path} (Step 3 먼저 실행)", file=sys.stderr)
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
        print(f"  [agg] MRR@10={ov['MRR@10']}  Recall@10={ov['Recall@10']}  Recall@5={ov['Recall@5']}")

    decision = evaluate_decision(aggregated)

    print("\n=== DECISION ===")
    print(f"baseline MRR@10={decision['baseline']['MRR@10']}, Recall@10={decision['baseline']['Recall@10']}")
    for c in decision["candidates"]:
        marks = []
        marks.append(f"MRR={'✓' if c['MRR_PASS'] else '✗'}({c['mrr@10']} vs ≥{c['mrr_threshold (×1.05)']})")
        marks.append(f"Rec10={'✓' if c['Recall_PASS'] else '✗'}({c['recall@10']} vs ≥{c['baseline_recall@10']})")
        marks.append(f"VetRec5={'✓' if c['Vet_PASS'] else '✗'}({c['vet_recall@5']} vs ≥{c['vet_threshold (×0.95)']})")
        verdict = "PASS" if c["ALL_PASS_for_phase3"] else "FAIL"
        print(f"  {c['model_id']:18s} → {verdict}  | " + "  ".join(marks))

    payload = {
        "_metadata": {
            "handoff": "docs/20260427_r8_phase2_handoff.md §3-3 Step 4",
            "n_queries": len(queries),
            "n_samples": 1000,
            "top_k": TOP_K,
            "models": [m[0] for m in MODELS],
        },
        "per_query": all_results,
        "aggregated": aggregated,
        "decision_3_2": decision,
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] Wrote {OUT_PATH.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
