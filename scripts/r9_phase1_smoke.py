"""scripts/r9_phase1_smoke.py — R-9 Phase 1 7쿼리 smoke 다국어 임베더 비교.

[설계서] docs/20260427_r9_multilingual_handoff.md §3 Task Definition (R9-1~R9-6 default a/b/b/b/a/c)
[목적]   R-8 Phase 2에서 한국어 11쿼리 3 모델 모두 MRR=0 노출. 다국어 임베더(BGE-M3 / multilingual-e5-large)가
         좁은 candidate pool에서 한국어→영어 cross-lingual 매칭을 발현하는지 1차 검증.

검증 모델:
  M0 baseline       : sentence-transformers/all-MiniLM-L6-v2 (현행, 384d, 영문 단일)
  C1 BGE-M3         : BAAI/bge-m3 (1024d, 100+ langs, dense+sparse+colbert)
  C2 ml-e5-large    : intfloat/multilingual-e5-large (1024d, 100+ langs)

7 쿼리 (R-8 r8_phase2_query_dataset.json 첫 11건에서 R9-3=b 권장 default 추출):
  영어 4건:
    T1  feline panleukopenia SNOMED code     ↔ 339181000009108 Feline panleukopenia
    T3  diabetes mellitus in cat             ↔ 73211009        Diabetes mellitus
    T5  chronic kidney disease in cat        ↔ 709044004       Chronic kidney disease
    T8  diabetes mellitus type 1             ↔ 46635009        Diabetes mellitus type 1
  한국어 3건:
    T9  고양이 당뇨                          ↔ 73211009        Diabetes mellitus
    T10 개 췌장염                            ↔ 75694006        Pancreatitis
    T11 고양이 범백혈구감소증 SNOMED 코드    ↔ 339181000009108 Feline panleukopenia

→ unique gold concept 5개 (T3·T9 = 73211009 / T1·T11 = 339181000009108)
→ 평가 매트릭스: 7 쿼리 × 5 unique candidate concept

성공 기준 (P1-S1 ~ P1-S7, 핸드오프 §3-5):
  - C1 또는 C2 한국어 3건 중 ≥ 1 적중 (rank-1, M0=0 대비 발현)
  - C1 또는 C2 영어 4건 모두 rank 1-3 유지 (영어 무손실 가드)
  - 산출: scripts/r9_phase1_smoke.py + graphify_out/r9_phase1_smoke.{json,log} + docs/20260427_r9_phase1_smoke.md

E5-large prefix 처리:
  intfloat/multilingual-e5-large 권장 prefix — query는 "query: " / passage는 "passage: ".
  BGE-M3, baseline은 prefix 불필요. 모델별 wrapper로 분기.

실행: venv/bin/python scripts/r9_phase1_smoke.py 2>&1 | tee graphify_out/r9_phase1_smoke.log
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings
from pathlib import Path
from typing import Callable

import numpy as np

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# (qid, query_text, language, gold_concept_id, gold_term)
QUERIES = [
    ("T1",  "feline panleukopenia SNOMED code", "en", "339181000009108", "Feline panleukopenia"),
    ("T3",  "diabetes mellitus in cat",         "en", "73211009",        "Diabetes mellitus"),
    ("T5",  "chronic kidney disease in cat",    "en", "709044004",       "Chronic kidney disease"),
    ("T8",  "diabetes mellitus type 1",         "en", "46635009",        "Diabetes mellitus type 1"),
    ("T9",  "고양이 당뇨",                      "ko", "73211009",        "Diabetes mellitus"),
    ("T10", "개 췌장염",                        "ko", "75694006",        "Pancreatitis"),
    ("T11", "고양이 범백혈구감소증 SNOMED 코드", "ko", "339181000009108", "Feline panleukopenia"),
]

# 5 unique candidate concept (preferred_term 기준)
CANDIDATES = [
    ("339181000009108", "Feline panleukopenia"),
    ("73211009",        "Diabetes mellitus"),
    ("709044004",       "Chronic kidney disease"),
    ("46635009",        "Diabetes mellitus type 1"),
    ("75694006",        "Pancreatitis"),
]
CONCEPT_ID_TO_IDX = {cid: i for i, (cid, _) in enumerate(CANDIDATES)}


def _l2_normalize(x: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(x, axis=-1, keepdims=True)
    norm = np.where(norm == 0, 1.0, norm)
    return x / norm


def _cosine_matrix(qe: np.ndarray, ce: np.ndarray) -> np.ndarray:
    return _l2_normalize(qe) @ _l2_normalize(ce).T


def encode_st_plain(model_name: str) -> Callable[[list[str], str], np.ndarray]:
    """sentence-transformers, prefix 미적용. baseline + BGE-M3 용."""
    from sentence_transformers import SentenceTransformer
    print(f"  [load] sentence-transformers: {model_name} ...", flush=True)
    t0 = time.time()
    model = SentenceTransformer(model_name)
    print(f"  [load] done in {time.time()-t0:.1f}s, dim={model.get_sentence_embedding_dimension()}", flush=True)

    def _encode(texts: list[str], role: str) -> np.ndarray:
        del role  # 미사용
        return np.asarray(model.encode(texts, normalize_embeddings=False, show_progress_bar=False))

    return _encode


def encode_st_e5(model_name: str) -> Callable[[list[str], str], np.ndarray]:
    """sentence-transformers + e5 prefix. role='query'/'passage'."""
    from sentence_transformers import SentenceTransformer
    print(f"  [load] sentence-transformers (e5 prefix): {model_name} ...", flush=True)
    t0 = time.time()
    model = SentenceTransformer(model_name)
    print(f"  [load] done in {time.time()-t0:.1f}s, dim={model.get_sentence_embedding_dimension()}", flush=True)

    def _encode(texts: list[str], role: str) -> np.ndarray:
        if role == "query":
            prefixed = [f"query: {t}" for t in texts]
        elif role == "passage":
            prefixed = [f"passage: {t}" for t in texts]
        else:
            raise ValueError(f"unknown role {role!r}")
        return np.asarray(model.encode(prefixed, normalize_embeddings=False, show_progress_bar=False))

    return _encode


MODELS = [
    (
        "M0_baseline_all-MiniLM-L6-v2",
        "sentence-transformers/all-MiniLM-L6-v2",
        "st-plain",
        "current production, English-only (384d)",
    ),
    (
        "C1_BGE-M3",
        "BAAI/bge-m3",
        "st-plain",
        "BGE-M3 dense, 100+ langs, no prefix (1024d)",
    ),
    (
        "C2_ml-e5-large",
        "intfloat/multilingual-e5-large",
        "st-e5",
        "multilingual-e5-large, query/passage prefix (1024d)",
    ),
]


def evaluate_model(
    model_id: str, hf_id: str, kind: str, desc: str
) -> dict:
    print(f"\n=== {model_id} ===")
    print(f"  source: {hf_id}")
    print(f"  desc:   {desc}")

    if kind == "st-plain":
        encode = encode_st_plain(hf_id)
    elif kind == "st-e5":
        encode = encode_st_e5(hf_id)
    else:
        raise ValueError(f"unknown kind {kind!r}")

    queries = [q[1] for q in QUERIES]
    concepts = [c[1] for c in CANDIDATES]

    t0 = time.time()
    qe = encode(queries, "query")
    ce = encode(concepts, "passage")
    elapsed = time.time() - t0
    nq, nc = len(queries), len(concepts)
    print(f"  encode {nq+nc} texts in {elapsed:.2f}s")

    sim = _cosine_matrix(qe, ce)  # (7, 5)

    # rank: 각 쿼리에서 정답 concept이 5개 중 몇 위?
    ranks = []
    correct_idxs = []
    for i, q in enumerate(QUERIES):
        gold_id = q[3]
        gold_idx = CONCEPT_ID_TO_IDX[gold_id]
        correct_idxs.append(gold_idx)
        sorted_idx = np.argsort(-sim[i])
        rank = int(np.where(sorted_idx == gold_idx)[0][0]) + 1
        ranks.append(rank)

    # 영어 / 한국어 분리 통계
    en_ranks = [ranks[i] for i, q in enumerate(QUERIES) if q[2] == "en"]
    ko_ranks = [ranks[i] for i, q in enumerate(QUERIES) if q[2] == "ko"]
    en_rank1_hits = sum(1 for r in en_ranks if r == 1)
    ko_rank1_hits = sum(1 for r in ko_ranks if r == 1)
    en_rank13_hits = sum(1 for r in en_ranks if r <= 3)
    ko_rank13_hits = sum(1 for r in ko_ranks if r <= 3)

    # gold-cosine (정답 매칭 cosine 평균)
    gold_cos = float(np.mean([sim[i, correct_idxs[i]] for i in range(nq)]))
    # off-gold cosine (오답 매칭 cosine 평균)
    off_cos_vals = []
    for i in range(nq):
        for j in range(nc):
            if j != correct_idxs[i]:
                off_cos_vals.append(sim[i, j])
    off_cos = float(np.mean(off_cos_vals))
    margin = gold_cos - off_cos

    print(f"  cosine matrix (rows=queries, cols=candidates):")
    cand_short = [c[1][:18] for c in CANDIDATES]
    print(f"          {'  '.join(f'{n:<18}' for n in cand_short)}")
    for i, q in enumerate(QUERIES):
        row = "  ".join(f"{sim[i,j]:+.4f}{'★' if j == correct_idxs[i] else ' '}{'':12}"[:20] for j in range(nc))
        marker = "✓" if ranks[i] == 1 else f"rank={ranks[i]}"
        print(f"  {q[0]:<3} {q[2]} {row}  <-- {marker}")

    print(
        f"  gold_cos={gold_cos:.4f}  off_cos={off_cos:.4f}  margin={margin:+.4f}"
    )
    print(
        f"  영어 4건 rank-1: {en_rank1_hits}/4  rank≤3: {en_rank13_hits}/4  "
        f"한국어 3건 rank-1: {ko_rank1_hits}/3  rank≤3: {ko_rank13_hits}/3"
    )

    return {
        "model_id": model_id,
        "hf_id": hf_id,
        "desc": desc,
        "gold_cos_mean": gold_cos,
        "off_cos_mean": off_cos,
        "margin": margin,
        "ranks": ranks,
        "en_rank1_hits": en_rank1_hits,
        "en_rank13_hits": en_rank13_hits,
        "ko_rank1_hits": ko_rank1_hits,
        "ko_rank13_hits": ko_rank13_hits,
        "en_total": len(en_ranks),
        "ko_total": len(ko_ranks),
        "encode_time_s": elapsed,
        "sim_matrix": sim.tolist(),
    }


def main() -> int:
    print("=" * 90)
    print(" R-9 Phase 1 — 7쿼리 smoke (baseline + BGE-M3 + multilingual-e5-large)")
    print("=" * 90)
    print()
    print("쿼리 (영어 4 + 한국어 3):")
    for q in QUERIES:
        print(f"  {q[0]:<3} [{q[2]}] '{q[1]}'  ↔  {q[3]} {q[4]}")
    print()
    print("Candidate concepts (5 unique):")
    for i, c in enumerate(CANDIDATES):
        print(f"  C{i+1}  {c[0]:<18} {c[1]}")

    results = []
    for model_id, hf_id, kind, desc in MODELS:
        try:
            r = evaluate_model(model_id, hf_id, kind, desc)
            results.append(r)
        except Exception as e:
            print(f"  [error] {model_id}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()

    print()
    print("=" * 90)
    print(" 종합 비교 표 (per-language rank-1 hits)")
    print("=" * 90)
    print(
        f"  {'model':<32}  {'gold↑':>7}  {'off↓':>7}  {'margin↑':>8}  "
        f"{'en rank1':>9}  {'ko rank1':>9}  {'time(s)':>8}"
    )
    for r in results:
        print(
            f"  {r['model_id']:<32}  "
            f"{r['gold_cos_mean']:>+.4f}  {r['off_cos_mean']:>+.4f}   "
            f"{r['margin']:>+.4f}    "
            f"{r['en_rank1_hits']:>2}/{r['en_total']:<5}    "
            f"{r['ko_rank1_hits']:>2}/{r['ko_total']:<5}    "
            f"{r['encode_time_s']:>6.2f}"
        )

    if not results:
        print(" (no successful runs)")
        return 1

    # JSON 저장
    out = {
        "_meta": {
            "phase": "R-9 Phase 1",
            "handoff": "docs/20260427_r9_multilingual_handoff.md",
            "default_choices": {
                "R9-1": "a (proceed)",
                "R9-2": "b (C1 + C2)",
                "R9-3": "b (T1·T3·T5·T8 en + T9·T10·T11 ko = 7)",
                "R9-4": "b (user-decision gate before Phase 2)",
                "R9-5": "a (ko hits >= 1 Phase 1)",
                "R9-6": "c (.gitignore + retain)",
            },
            "queries": [
                {"qid": q[0], "text": q[1], "language": q[2], "gold_id": q[3], "gold_term": q[4]}
                for q in QUERIES
            ],
            "candidates": [{"id": c[0], "term": c[1]} for c in CANDIDATES],
        },
        "results": results,
    }
    out_path = PROJECT_ROOT / "graphify_out" / "r9_phase1_smoke.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[json] {out_path.relative_to(PROJECT_ROOT)} saved")

    # Phase 2 진입 결정 (R9-5=a: ko rank-1 hits >= 1)
    print()
    print("=" * 90)
    print(" §3-2 판단 기준 1:1 PASS/FAIL")
    print("=" * 90)
    any_ko_hit = any(r["ko_rank1_hits"] >= 1 for r in results if r["model_id"] != "M0_baseline_all-MiniLM-L6-v2")
    en_no_loss = any(
        r["en_rank13_hits"] == r["en_total"] for r in results if r["model_id"] != "M0_baseline_all-MiniLM-L6-v2"
    )
    print(f"  [한국어 적중 ≥ 1] C1/C2 중 ≥ 1 한국어 rank-1: {'PASS ✓' if any_ko_hit else 'FAIL ✗'}")
    print(f"  [영어 무손실]    C1/C2 중 ≥ 1 영어 rank≤3 4/4: {'PASS ✓' if en_no_loss else 'FAIL ✗'}")
    if any_ko_hit and en_no_loss:
        print("  → Phase 2 진입 권고 (사용자 결정 게이트 R9-4=b)")
    else:
        print("  → R-9 폐기 또는 후보 재검토 권고")

    return 0


if __name__ == "__main__":
    sys.exit(main())
