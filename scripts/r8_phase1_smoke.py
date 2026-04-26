"""scripts/r8_phase1_smoke.py — R-8 Phase 1 5쿼리 smoke 비교.

[설계서] docs/20260427_r8_embedder_candidates.md §4-1 Phase 1
[목적]   baseline(all-MiniLM-L6-v2)과 권장 후보 3종(SapBERT [CLS] / SapBERT mean / NeuML)을
         5쿼리 × 5 gold SNOMED concept 매트릭스에서 cosine similarity로 직접 비교한다.

검증 모델:
  M0 baseline       : sentence-transformers/all-MiniLM-L6-v2 (현행, 384d)
  M1 SapBERT [CLS]  : cambridgeltl/SapBERT-from-PubMedBERT-fulltext, [CLS] pooling (768d)
  M2 SapBERT mean   : cambridgeltl/SapBERT-from-PubMedBERT-fulltext, mean pooling (768d)
  M3 NeuML pubmedbert: NeuML/pubmedbert-base-embeddings (768d, sentence-transformers)

5 쿼리 + 5 gold concept (data/snomed_ct_vet.db 검증):
  Q1 feline panleukopenia   ↔ 339181000009108 Feline panleukopenia
  Q2 elbow dysplasia dog    ↔ 309871000009108 Dysplasia of elbow
  Q3 dental extraction      ↔ 55162003        Tooth extraction
  Q4 blood glucose          ↔ 33747003        Glucose measurement, blood
  Q5 German Shepherd        ↔ 42252000        German shepherd dog

성공 기준:
  - 4 모델 × 5 쿼리 × 5 concept = 4 × 25 cosine 매트릭스 출력
  - 각 모델 정답 매칭(diagonal) cosine 평균 + non-diagonal 평균 분리
  - margin = diag_mean - off_diag_mean (높을수록 분별력 우월)
  - Phase 2 진입 권장 모델 1개 선정

실행: venv/bin/python scripts/r8_phase1_smoke.py 2>&1 | tee graphify_out/r8_phase1_smoke.log
"""
from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path
from typing import Callable

import numpy as np

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


QUERIES = [
    ("Q1", "feline panleukopenia", "339181000009108", "Feline panleukopenia"),
    ("Q2", "elbow dysplasia dog", "309871000009108", "Dysplasia of elbow"),
    ("Q3", "dental extraction", "55162003", "Tooth extraction"),
    ("Q4", "blood glucose", "33747003", "Glucose measurement, blood"),
    ("Q5", "German Shepherd", "42252000", "German shepherd dog"),
]


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(x, axis=-1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    return x / norm


def _cosine_matrix(qe: np.ndarray, ce: np.ndarray) -> np.ndarray:
    return _l2_normalize(qe) @ _l2_normalize(ce).T


def encode_sentence_transformers(model_name: str) -> Callable[[list[str]], np.ndarray]:
    from sentence_transformers import SentenceTransformer
    print(f"  [load] sentence-transformers: {model_name} ...", flush=True)
    t0 = time.time()
    model = SentenceTransformer(model_name)
    print(f"  [load] done in {time.time()-t0:.1f}s, dim={model.get_sentence_embedding_dimension()}", flush=True)

    def _encode(texts: list[str]) -> np.ndarray:
        return np.asarray(model.encode(texts, normalize_embeddings=False, show_progress_bar=False))

    return _encode


def encode_huggingface_pooled(
    model_name: str, pooling: str
) -> Callable[[list[str]], np.ndarray]:
    """transformers AutoModel + manual pooling (CLS or mean)."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    assert pooling in {"cls", "mean"}, pooling
    print(f"  [load] transformers: {model_name} (pooling={pooling}) ...", flush=True)
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    dim = model.config.hidden_size
    print(f"  [load] done in {time.time()-t0:.1f}s, dim={dim}", flush=True)

    @torch.no_grad()
    def _encode(texts: list[str]) -> np.ndarray:
        enc = tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=64,
            return_tensors="pt",
        )
        out = model(**enc)
        last = out.last_hidden_state  # (B, T, H)
        if pooling == "cls":
            vec = last[:, 0, :]
        else:
            mask = enc["attention_mask"].unsqueeze(-1).float()
            summed = (last * mask).sum(dim=1)
            denom = mask.sum(dim=1).clamp(min=1e-9)
            vec = summed / denom
        return vec.cpu().numpy()

    return _encode


MODELS = [
    (
        "M0_baseline_all-MiniLM-L6-v2",
        "sentence-transformers/all-MiniLM-L6-v2",
        "st",
        "current default, general English (384d)",
    ),
    (
        "M1_SapBERT_CLS",
        "cambridgeltl/SapBERT-from-PubMedBERT-fulltext",
        "hf-cls",
        "SapBERT [CLS] pooling, UMLS entity linking (768d)",
    ),
    (
        "M2_SapBERT_mean",
        "cambridgeltl/SapBERT-from-PubMedBERT-fulltext",
        "hf-mean",
        "SapBERT mean pooling (768d)",
    ),
    (
        "M3_NeuML_pubmedbert",
        "NeuML/pubmedbert-base-embeddings",
        "st",
        "NeuML PubMedBERT sentence embeddings (768d)",
    ),
]


def evaluate_model(
    model_id: str, hf_id: str, kind: str, desc: str
) -> dict:
    print(f"\n=== {model_id} ===")
    print(f"  source: {hf_id}")
    print(f"  desc:   {desc}")

    if kind == "st":
        encode = encode_sentence_transformers(hf_id)
    elif kind == "hf-cls":
        encode = encode_huggingface_pooled(hf_id, "cls")
    elif kind == "hf-mean":
        encode = encode_huggingface_pooled(hf_id, "mean")
    else:
        raise ValueError(f"unknown kind {kind!r}")

    queries = [q[1] for q in QUERIES]
    concepts = [q[3] for q in QUERIES]

    t0 = time.time()
    qe = encode(queries)
    ce = encode(concepts)
    elapsed = time.time() - t0
    print(f"  encode 10 texts in {elapsed:.2f}s")

    sim = _cosine_matrix(qe, ce)  # (5, 5)
    diag = np.diag(sim)
    off_mask = ~np.eye(5, dtype=bool)
    off = sim[off_mask]
    diag_mean = float(diag.mean())
    off_mean = float(off.mean())
    margin = diag_mean - off_mean

    # 정답 rank — 각 쿼리에서 정답 concept이 5개 중 몇 위?
    ranks = []
    for i in range(5):
        sorted_idx = np.argsort(-sim[i])
        rank = int(np.where(sorted_idx == i)[0][0]) + 1
        ranks.append(rank)
    rank1_count = sum(1 for r in ranks if r == 1)

    print(f"  cosine matrix (rows=queries, cols=concepts):")
    print(f"           {'  '.join(f'C{j+1:<6}' for j in range(5))}")
    for i, q in enumerate(QUERIES):
        row = "  ".join(f"{sim[i,j]:+.4f}" for j in range(5))
        marker = "<-- ✓" if ranks[i] == 1 else f"<-- rank={ranks[i]}"
        print(f"  {q[0]}    {row}   {marker}")

    print(
        f"  diag_mean={diag_mean:.4f}  off_diag_mean={off_mean:.4f}  "
        f"margin={margin:+.4f}  rank-1 hits={rank1_count}/5"
    )

    return {
        "model_id": model_id,
        "hf_id": hf_id,
        "desc": desc,
        "diag_mean": diag_mean,
        "off_diag_mean": off_mean,
        "margin": margin,
        "rank1_hits": rank1_count,
        "ranks": ranks,
        "encode_time_s": elapsed,
        "sim_matrix": sim.tolist(),
    }


def main() -> int:
    print("=" * 78)
    print(" R-8 Phase 1 — 5쿼리 smoke (baseline + SapBERT 2 변형 + NeuML)")
    print("=" * 78)
    print()
    print("쿼리 + gold concept 5쌍:")
    for q in QUERIES:
        print(f"  {q[0]}  '{q[1]}'  ↔  {q[2]} {q[3]}")

    results = []
    for model_id, hf_id, kind, desc in MODELS:
        try:
            r = evaluate_model(model_id, hf_id, kind, desc)
            results.append(r)
        except Exception as e:
            print(f"  [error] {model_id}: {type(e).__name__}: {e}")

    print()
    print("=" * 78)
    print(" 종합 비교 표")
    print("=" * 78)
    print(
        f"  {'model':<32}  {'diag↑':>7}  {'off-diag':>9}  {'margin↑':>8}  {'rank-1':>7}  {'time(s)':>7}"
    )
    for r in results:
        print(
            f"  {r['model_id']:<32}  "
            f"{r['diag_mean']:>+.4f}  {r['off_diag_mean']:>+.4f}   "
            f"{r['margin']:>+.4f}    {r['rank1_hits']}/5    {r['encode_time_s']:>6.2f}"
        )

    if not results:
        print(" (no successful runs)")
        return 1

    best = max(results, key=lambda r: (r["rank1_hits"], r["margin"]))
    print()
    print(f" 권장 (rank-1 hits + margin 최대): {best['model_id']}")
    print(f"    rank-1: {best['rank1_hits']}/5 / margin: {best['margin']:+.4f}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
