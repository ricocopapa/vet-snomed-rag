"""scripts/r8_phase2_build_indices.py — R-8 Phase 2 Step 3: 임시 ChromaDB 3개 빌드.

[설계서] docs/20260427_r8_phase2_handoff.md §3-3 Step 3
[목적]   1,000 sample × 3 모델로 임시 ChromaDB 빌드 (공정 비교용 동일 pool).

모델:
  M0 baseline       all-MiniLM-L6-v2          (384d, sentence-transformers)
  M2 SapBERT mean   cambridgeltl/SapBERT-...  (768d, transformers + manual mean pooling)
  M3 NeuML          NeuML/pubmedbert-...      (768d, sentence-transformers)

document text (production vectorize_snomed.py 패턴):
  preferred_term | fsn | Category: semantic_tag

ChromaDB 설정: cosine space, hnsw, batch_size=200, 사전 계산 embedding 직접 주입.

산출:
  data/chroma_phase2_baseline/
  data/chroma_phase2_sapbert_mean/
  data/chroma_phase2_neuml/

실행: venv/bin/python scripts/r8_phase2_build_indices.py 2>&1 | tee graphify_out/r8_phase2_build.log
"""
from __future__ import annotations

import json
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_PATH = PROJECT_ROOT / "data" / "r8_phase2_sample_concepts.json"
DB_PATH = PROJECT_ROOT / "data" / "snomed_ct_vet.db"

CHROMA_BASES = {
    "M0_baseline": PROJECT_ROOT / "data" / "chroma_phase2_baseline",
    "M2_sapbert_mean": PROJECT_ROOT / "data" / "chroma_phase2_sapbert_mean",
    "M3_neuml": PROJECT_ROOT / "data" / "chroma_phase2_neuml",
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


def encode_huggingface_mean(model_name: str, dim_expected: int):
    """transformers AutoModel + mean pooling — Phase 1 패턴 재사용."""
    import torch
    from transformers import AutoModel, AutoTokenizer

    print(f"  [load] transformers: {model_name} (mean pooling)", flush=True)
    t0 = time.time()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    model.eval()
    actual_dim = model.config.hidden_size
    print(f"  [load] dim={actual_dim} in {time.time()-t0:.1f}s", flush=True)
    assert actual_dim == dim_expected, f"dim mismatch: expect {dim_expected}, got {actual_dim}"

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
            if (i // batch) % 5 == 0:
                print(f"    [encode] {i+len(chunk)}/{len(texts)}", flush=True)
        return np.concatenate(all_vecs, axis=0)

    return _encode


MODELS = [
    ("M0_baseline", "sentence-transformers/all-MiniLM-L6-v2", "st", 384),
    ("M2_sapbert_mean", "cambridgeltl/SapBERT-from-PubMedBERT-fulltext", "hf-mean", 768),
    ("M3_neuml", "NeuML/pubmedbert-base-embeddings", "st", 768),
]


def build_documents(samples: list[dict], db_cur) -> tuple[list[str], list[str], list[str], list[dict]]:
    """1,000 sample → ChromaDB ingest 페이로드.

    document text: preferred_term | fsn | Category: semantic_tag
    fsn은 SNOMED DB에서 추가 lookup.
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
        print(f"[ERROR] sample 없음: {SAMPLE_PATH} (Step 1 먼저 실행)", file=sys.stderr)
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
        elif kind == "hf-mean":
            encode = encode_huggingface_mean(hf_id, dim)
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
    print(f"\n=== OVERALL: {overall_elapsed:.1f}s for {len(MODELS)} models ===")

    # build summary 저장
    summary_path = PROJECT_ROOT / "graphify_out" / "r8_phase2_build_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps(
            {
                "_metadata": {
                    "handoff": "docs/20260427_r8_phase2_handoff.md §3-3 Step 3",
                    "n_samples": len(samples),
                    "overall_seconds": round(overall_elapsed, 2),
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
