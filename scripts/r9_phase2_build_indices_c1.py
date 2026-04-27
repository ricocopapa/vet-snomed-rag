"""scripts/r9_phase2_build_indices_c1.py — R-9 Phase 2 Step 1: C1 BGE-M3 ChromaDB 빌드.

[설계서] docs/20260427_r9_phase2_handoff.md §2-3 Step 1
[목적]   1,000 sample × C1 BGE-M3 (1024d) 임시 ChromaDB 빌드 (R-8 baseline 비교용).

R-8 r8_phase2_build_indices.py 패턴 재사용. MODELS C1 1개로 축소 + dim 1024.

document text (R-8 패턴 동일):
  preferred_term | fsn | Category: semantic_tag

ChromaDB 설정: cosine space, hnsw, batch_size=200, 사전 계산 embedding 직접 주입.

산출:
  data/chroma_phase2_c1_bge_m3/
  graphify_out/r9_phase2_build_summary.json

실행: venv/bin/python scripts/r9_phase2_build_indices_c1.py 2>&1 | tee graphify_out/r9_phase2_build.log
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
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
SAMPLE_PATH = PROJECT_ROOT / "data" / "r8_phase2_sample_concepts.json"
DB_PATH = PROJECT_ROOT / "data" / "snomed_ct_vet.db"

CHROMA_BASES = {
    "C1_bge_m3": PROJECT_ROOT / "data" / "chroma_phase2_c1_bge_m3",
}

COLLECTION_NAME = "phase2_concepts"
BATCH_SIZE = 200


def encode_sentence_transformers(model_name: str, dim_expected: int):
    from sentence_transformers import SentenceTransformer
    print(f"  [load] sentence-transformers: {model_name}", flush=True)
    t0 = time.time()
    model = SentenceTransformer(model_name)
    actual_dim = model.get_sentence_embedding_dimension()
    print(f"  [load] dim={actual_dim} in {time.time()-t0:.1f}s", flush=True)
    assert actual_dim == dim_expected, f"dim mismatch: expect {dim_expected}, got {actual_dim}"

    def _encode(texts: list[str], batch: int = 32) -> np.ndarray:
        return np.asarray(
            model.encode(
                texts, batch_size=batch, normalize_embeddings=False, show_progress_bar=True
            )
        )

    return _encode


# C1 BGE-M3 단독 (Phase 1 옵션 A 채택)
MODELS = [
    ("C1_bge_m3", "BAAI/bge-m3", "st", 1024),
]


def build_documents(samples: list[dict], db_cur) -> tuple[list[str], list[str], list[str], list[dict]]:
    """1,000 sample → ChromaDB ingest 페이로드.

    document text: preferred_term | fsn | Category: semantic_tag
    R-8 build_indices와 정확히 동일 패턴 — 공정 비교 보장.
    """
    ids: list[str] = []
    docs: list[str] = []
    pts: list[str] = []
    metas: list[dict] = []

    for s in samples:
        cid = s["concept_id"]
        pt = s["preferred_term"]
        st = s["semantic_tag"]
        row = db_cur.execute(
            "SELECT fsn, source FROM concept WHERE concept_id = ?", (cid,)
        ).fetchone()
        fsn = row[0] if row and row[0] else pt
        source = row[1] if row else "INT"
        doc = f"{pt} | {fsn} | Category: {st}"
        ids.append(cid)
        docs.append(doc)
        pts.append(pt)
        metas.append({"concept_id": cid, "preferred_term": pt, "fsn": fsn, "semantic_tag": st, "source": source})

    return ids, docs, pts, metas


def build_chroma(model_id: str, embeddings: np.ndarray, ids, docs, metas) -> None:
    import chromadb

    out_path = CHROMA_BASES[model_id]
    if out_path.exists():
        print(f"  [clean] removing existing {out_path}")
        shutil.rmtree(out_path)
    out_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(path=str(out_path))
    col = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    print(f"  [chroma] adding {len(ids)} entries in batches of {BATCH_SIZE}")
    for i in range(0, len(ids), BATCH_SIZE):
        chunk_ids = ids[i : i + BATCH_SIZE]
        chunk_emb = embeddings[i : i + BATCH_SIZE].tolist()
        chunk_docs = docs[i : i + BATCH_SIZE]
        chunk_metas = metas[i : i + BATCH_SIZE]
        col.add(
            ids=chunk_ids,
            embeddings=chunk_emb,
            documents=chunk_docs,
            metadatas=chunk_metas,
        )
        print(f"    [{min(i+BATCH_SIZE, len(ids))}/{len(ids)}]")

    cnt = col.count()
    print(f"  [chroma] count={cnt}")
    assert cnt == len(ids), f"count mismatch {cnt} != {len(ids)}"


def main() -> int:
    if not SAMPLE_PATH.exists():
        print(f"[ERROR] sample 없음: {SAMPLE_PATH} (R-8 Phase 2 자산 필요)", file=sys.stderr)
        return 1

    payload = json.loads(SAMPLE_PATH.read_text())
    samples = payload["samples"]
    print(f"[INFO] loaded {len(samples)} samples")

    db = sqlite3.connect(str(DB_PATH))
    cur = db.cursor()

    ids, docs, pts, metas = build_documents(samples, cur)
    print(f"[INFO] built {len(docs)} document texts")
    print(f"[INFO] sample doc[0]: {docs[0]}")

    overall_t0 = time.time()
    summary: list[dict] = []

    for model_id, hf_id, kind, dim in MODELS:
        print(f"\n=== {model_id} ===")
        t_model = time.time()

        if kind == "st":
            encode = encode_sentence_transformers(hf_id, dim)
        else:
            raise ValueError(kind)

        print(f"  [encode] {len(docs)} docs ...")
        t_enc = time.time()
        emb = encode(docs)
        enc_elapsed = time.time() - t_enc
        print(f"  [encode] done in {enc_elapsed:.1f}s, shape={emb.shape}")
        assert emb.shape == (len(docs), dim), f"unexpected shape {emb.shape}"

        build_chroma(model_id, emb, ids, docs, metas)
        elapsed = time.time() - t_model
        print(f"=== {model_id} TOTAL: {elapsed:.1f}s ===")
        summary.append(
            {
                "model_id": model_id,
                "hf_id": hf_id,
                "kind": kind,
                "dim": dim,
                "n_entries": len(docs),
                "encode_seconds": round(enc_elapsed, 2),
                "total_seconds": round(elapsed, 2),
                "chroma_path": str(CHROMA_BASES[model_id].relative_to(PROJECT_ROOT)),
            }
        )

        # 메모리 해제
        del emb, encode
        import gc

        gc.collect()

    overall_elapsed = time.time() - overall_t0
    print(f"\n=== OVERALL: {overall_elapsed:.1f}s for {len(MODELS)} model ===")

    # build summary 저장
    summary_path = PROJECT_ROOT / "graphify_out" / "r9_phase2_build_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "_metadata": {
                    "handoff": "docs/20260427_r9_phase2_handoff.md §2-3 Step 1",
                    "n_samples": len(samples),
                    "overall_seconds": round(overall_elapsed, 2),
                    "reuses_r8_assets": [
                        "data/r8_phase2_sample_concepts.json",
                        "data/r8_phase2_query_dataset.json",
                        "data/chroma_phase2_baseline/",
                    ],
                },
                "models": summary,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"[OK] Wrote {summary_path.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
