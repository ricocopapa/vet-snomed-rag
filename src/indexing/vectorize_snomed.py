"""
SNOMED CT VET 개념을 ChromaDB에 벡터 인덱싱하는 스크립트.

[목적]
- snomed_ct_vet_reference.db의 414,860 concepts를 벡터화
- ChromaDB persistent storage에 저장
- 이후 hybrid_retrieval.py에서 Vector Search 소스로 사용

[실행]
    cd vet-snomed-rag
    source .venv/bin/activate
    python src/indexing/vectorize_snomed.py

[산출물]
    data/chroma_db/ (ChromaDB persistent storage)
"""

import sqlite3
import os
import sys
import time
import json
from pathlib import Path

# 프로젝트 루트 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "snomed_ct_vet.db"
CHROMA_PATH = DATA_DIR / "chroma_db"

# ─── 설정 ───────────────────────────────────────────────
BATCH_SIZE = 500          # ChromaDB add 배치 크기
EMBEDDING_MODEL = "BAAI/bge-m3"  # R-9 Phase 3: multilingual 1024d 교체 (R-9 Phase 2 §2-2 임계 모두 PASS)
COLLECTION_NAME = "snomed_vet_concepts"

# 인덱싱 대상 semantic_tag 필터 (임상 관련 핵심 태그만 우선 인덱싱)
# 전체 인덱싱은 시간이 오래 걸리므로, 임상 핵심 태그를 우선 처리
PRIORITY_TAGS = [
    "disorder",
    "finding",
    "procedure",
    "body structure",
    "substance",
    "observable entity",
    "morphologic abnormality",
    "clinical drug",
    "medicinal product",
    "qualifier value",
    "assessment scale",
    "tumor staging",
]

# organism(종/품종)은 별도 컬렉션으로 분리 가능 — 여기서는 포함
INCLUDE_ORGANISM = True
if INCLUDE_ORGANISM:
    PRIORITY_TAGS.append("organism")


def get_db_connection():
    """SQLite DB 연결. 심볼릭 링크 또는 직접 경로 모두 지원."""
    if DB_PATH.exists():
        return sqlite3.connect(str(DB_PATH))

    # 심볼릭 링크가 없으면 직접 경로 시도
    direct_path = PROJECT_ROOT.parent.parent / "05_Output_Workspace" / "EMR" / "snomed_ct_vet_reference.db"
    if direct_path.exists():
        return sqlite3.connect(str(direct_path))

    print(f"[ERROR] SNOMED DB를 찾을 수 없습니다.")
    print(f"  시도한 경로: {DB_PATH}")
    print(f"  직접 경로: {direct_path}")
    print(f"  → setup_env.sh를 먼저 실행하세요.")
    sys.exit(1)


def load_concepts_from_db(conn, priority_only=True):
    """SNOMED DB에서 개념 데이터를 로드한다.

    [수정 사유: description JOIN + GROUP_CONCAT가 414K×1.48M 조합으로
     10분 이상 소요. concept 테이블 단독 조회로 변경하여 수 초 내 완료.
     동의어는 2차 패스로 상위 결과에만 선택적으로 추가.]

    Returns:
        list of dict: [{concept_id, fsn, semantic_tag, preferred_term, source}, ...]
    """
    cur = conn.cursor()

    # Phase 1: concept 테이블만 조회 (빠름, 수 초 이내)
    if priority_only:
        tag_placeholders = ",".join(["?" for _ in PRIORITY_TAGS])
        query = f"""
            SELECT concept_id, fsn, semantic_tag, preferred_term, source
            FROM concept
            WHERE semantic_tag IN ({tag_placeholders})
        """
        cur.execute(query, PRIORITY_TAGS)
    else:
        query = """
            SELECT concept_id, fsn, semantic_tag, preferred_term, source
            FROM concept
        """
        cur.execute(query)

    rows = cur.fetchall()
    concepts = []
    for row in rows:
        concepts.append({
            "concept_id": row[0],
            "fsn": row[1],
            "semantic_tag": row[2],
            "preferred_term": row[3] or row[1],
            "source": row[4],
            "descriptions": "",  # Phase 2에서 선택적 보강
        })

    # Phase 2: 동의어 보강 (선택적, 배치 처리)
    # 전체에 대해 JOIN하면 느리므로, 인덱싱 시 FSN + preferred_term으로 충분.
    # 동의어가 필요하면 아래 주석을 해제하고 배치 크기를 조절.
    #
    # SYNONYM_BATCH = 1000
    # concept_ids = [c["concept_id"] for c in concepts]
    # synonym_map = {}
    # for i in range(0, len(concept_ids), SYNONYM_BATCH):
    #     batch_ids = concept_ids[i:i+SYNONYM_BATCH]
    #     placeholders = ",".join(["?" for _ in batch_ids])
    #     cur.execute(f"""
    #         SELECT concept_id, GROUP_CONCAT(term, ' | ')
    #         FROM description
    #         WHERE concept_id IN ({placeholders}) AND type = 'SYNONYM'
    #         GROUP BY concept_id
    #     """, batch_ids)
    #     for row in cur.fetchall():
    #         synonym_map[row[0]] = row[1]
    # for c in concepts:
    #     c["descriptions"] = synonym_map.get(c["concept_id"], "")

    return concepts


def build_document_text(concept):
    """개념 데이터를 임베딩용 텍스트 문서로 변환한다.

    임베딩 품질을 위해 구조화된 텍스트를 생성:
    - FSN (Fully Specified Name)이 핵심 검색 대상
    - preferred_term은 자연어 표현
    - semantic_tag는 카테고리 정보
    - descriptions(동의어)는 검색 범위 확장
    """
    parts = [
        concept["preferred_term"],
        concept["fsn"],
        f"Category: {concept['semantic_tag']}",
    ]
    if concept["descriptions"]:
        # 동의어가 너무 많으면 앞의 5개만
        synonyms = concept["descriptions"].split(" | ")[:5]
        parts.append(f"Synonyms: {', '.join(synonyms)}")
    return " | ".join(parts)


def build_metadata(concept):
    """ChromaDB 메타데이터로 저장할 정보."""
    return {
        "concept_id": concept["concept_id"],
        "fsn": concept["fsn"],
        "semantic_tag": concept["semantic_tag"],
        "preferred_term": concept["preferred_term"],
        "source": concept["source"],  # INT / VET / LOCAL
    }


def create_chroma_collection():
    """ChromaDB 컬렉션을 생성하고 반환한다."""
    import chromadb
    from chromadb.utils import embedding_functions

    # sentence-transformers 임베딩 함수
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    # Persistent client (디스크 저장)
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))

    # 기존 컬렉션이 있으면 삭제 후 재생성
    try:
        client.delete_collection(name=COLLECTION_NAME)
        print(f"  → 기존 컬렉션 '{COLLECTION_NAME}' 삭제")
    except Exception:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"}  # 코사인 유사도
    )

    return client, collection


def index_concepts(collection, concepts):
    """개념 리스트를 배치로 ChromaDB에 인덱싱한다."""
    total = len(concepts)
    print(f"  → 총 {total:,}건 인덱싱 시작 (배치: {BATCH_SIZE})")

    start_time = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = concepts[i:i + BATCH_SIZE]

        ids = [c["concept_id"] for c in batch]
        documents = [build_document_text(c) for c in batch]
        metadatas = [build_metadata(c) for c in batch]

        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        elapsed = time.time() - start_time
        progress = min(i + BATCH_SIZE, total)
        rate = progress / elapsed if elapsed > 0 else 0
        eta = (total - progress) / rate if rate > 0 else 0
        print(f"    [{progress:>7,}/{total:,}] {progress/total*100:.1f}% | "
              f"{rate:.0f} concepts/sec | ETA: {eta:.0f}s")

    elapsed = time.time() - start_time
    print(f"  → 인덱싱 완료: {total:,}건, {elapsed:.1f}초 소요")


def verify_index(collection, test_queries=None):
    """인덱싱 결과를 검증한다."""
    print(f"\n[검증] 컬렉션 상태:")
    print(f"  → 총 문서 수: {collection.count():,}")

    if test_queries is None:
        test_queries = [
            "feline panleukopenia",
            "elbow dysplasia in dogs",
            "dental extraction",
            "blood glucose level",
            "German Shepherd",
        ]

    print(f"\n[검증] 테스트 쿼리 {len(test_queries)}건:")
    for query in test_queries:
        results = collection.query(
            query_texts=[query],
            n_results=3,
        )
        print(f"\n  Q: \"{query}\"")
        for j, (doc_id, dist, meta) in enumerate(zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
        )):
            print(f"    [{j+1}] {meta['preferred_term']}")
            print(f"        concept_id={doc_id} | tag={meta['semantic_tag']} "
                  f"| source={meta['source']} | distance={dist:.4f}")


def save_index_stats(concepts):
    """인덱싱 통계를 JSON으로 저장한다."""
    from collections import Counter
    tag_counts = Counter(c["semantic_tag"] for c in concepts)
    source_counts = Counter(c["source"] for c in concepts)

    stats = {
        "total_indexed": len(concepts),
        "embedding_model": EMBEDDING_MODEL,
        "collection_name": COLLECTION_NAME,
        "indexed_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "by_semantic_tag": dict(tag_counts.most_common()),
        "by_source": dict(source_counts),
        "priority_tags": PRIORITY_TAGS,
    }

    stats_path = DATA_DIR / "index_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"\n[저장] 인덱싱 통계 → {stats_path}")


# ─── 메인 실행 ──────────────────────────────────────────
def main():
    print("=" * 60)
    print(" SNOMED CT VET — ChromaDB 벡터 인덱싱")
    print("=" * 60)

    # 1. DB 연결
    print("\n[1/5] SNOMED DB 연결...")
    conn = get_db_connection()
    print(f"  → DB 연결 성공")

    # 2. 개념 로드
    print("\n[2/5] 임상 핵심 개념 로드 (priority tags)...")
    concepts = load_concepts_from_db(conn, priority_only=True)
    print(f"  → {len(concepts):,}건 로드 완료")
    conn.close()

    if not concepts:
        print("[ERROR] 로드된 개념이 없습니다. DB를 확인하세요.")
        sys.exit(1)

    # 3. ChromaDB 컬렉션 생성
    print("\n[3/5] ChromaDB 컬렉션 생성...")
    client, collection = create_chroma_collection()
    print(f"  → 컬렉션 '{COLLECTION_NAME}' 생성 완료")
    print(f"  → 임베딩 모델: {EMBEDDING_MODEL}")
    print(f"  → 저장 경로: {CHROMA_PATH}")

    # 4. 인덱싱
    print("\n[4/5] 벡터 인덱싱...")
    index_concepts(collection, concepts)

    # 5. 검증
    print("\n[5/5] 인덱싱 검증...")
    verify_index(collection)
    save_index_stats(concepts)

    print("\n" + "=" * 60)
    print(" 인덱싱 완료!")
    print(f" 다음 단계: python src/retrieval/hybrid_search.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
