"""
하이브리드 검색 엔진: Vector Search + SQL Retrieval + Re-ranking.

[아키텍처]
Track A: Vector Search (의미 기반)
    Query → Embedding → ChromaDB → Top-K 후보
Track B: SQL Retrieval (정확 매칭)
    Query → 키워드 추출 → SQLite LIKE/FTS → 정확 매칭
Merge: Reciprocal Rank Fusion (RRF)
    두 트랙 결과 → 중복 제거 → 가중 점수 → 최종 순위

[실행]
    python src/retrieval/hybrid_search.py --query "feline panleukopenia"
    python src/retrieval/hybrid_search.py --interactive
"""

import sqlite3
import json
import argparse
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "snomed_ct_vet.db"
CHROMA_PATH = DATA_DIR / "chroma_db"

COLLECTION_NAME = "snomed_vet_concepts"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# R-4 (2026-04-26): rerank candidate에서 매핑 부적합 semantic_tag 차단.
# T9 "feline diabetes mellitus" 케이스에서 160303001 "FH: Diabetes mellitus" (situation)이
# rerank Top-1을 차지하던 문제를 차단한다. 11쿼리 expected는 disorder(9)+organism(1)이며
# 모두 비차단 카테고리이므로 회귀 0.
_MAPPING_INELIGIBLE_TAGS = frozenset({
    "situation",
    "context-dependent category",
    "qualifier value",
    "occupation",
    "person",
    "social context",
    "record artifact",
    "foundation metadata concept",
    "core metadata concept",
    "namespace concept",
    "linkage concept",
    "attribute",
    "environment / location",
    "ethnic group",
    "racial group",
    "religion/philosophy",
})


# ─── 데이터 모델 ────────────────────────────────────────

@dataclass
class SearchResult:
    """검색 결과 단일 항목."""
    concept_id: str
    preferred_term: str
    fsn: str
    semantic_tag: str
    source: str  # INT / VET / LOCAL
    score: float = 0.0
    match_type: str = ""  # "vector" / "sql" / "hybrid"
    vector_rank: Optional[int] = None
    sql_rank: Optional[int] = None
    vector_distance: Optional[float] = None
    relationships: list = field(default_factory=list)


# ─── Track A: Vector Search ─────────────────────────────

class VectorSearcher:
    """ChromaDB 기반 의미 검색."""

    def __init__(self):
        import chromadb
        from chromadb.utils import embedding_functions

        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self.client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self.collection = self.client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=self.ef,
        )
        print(f"[Vector] ChromaDB 로드 완료: {self.collection.count():,}건")

    def search(
        self,
        query: str,
        top_k: int = 20,
        where: Optional[dict] = None,
    ) -> list[SearchResult]:
        """의미 기반 벡터 검색.

        Args:
            where: ChromaDB metadata 필터 (예: {"semantic_tag": "disorder"}).
                   species qualifier 쿼리에서 disorder 도메인 한정 시 사용.
        """
        query_kwargs = {"query_texts": [query], "n_results": top_k}
        if where:
            query_kwargs["where"] = where
        results = self.collection.query(**query_kwargs)

        items = []
        for rank, (cid, dist, meta) in enumerate(zip(
            results["ids"][0],
            results["distances"][0],
            results["metadatas"][0],
        ), start=1):
            items.append(SearchResult(
                concept_id=cid,
                preferred_term=meta.get("preferred_term", ""),
                fsn=meta.get("fsn", ""),
                semantic_tag=meta.get("semantic_tag", ""),
                source=meta.get("source", ""),
                score=1.0 / (rank + 60),  # RRF 점수 (k=60)
                match_type="vector",
                vector_rank=rank,
                vector_distance=dist,
            ))
        return items


# ─── Track B: SQL Retrieval ──────────────────────────────

class SQLRetriever:
    """SQLite 기반 정확/퍼지 검색."""

    def __init__(self):
        # 심볼릭 링크 또는 직접 경로
        if DB_PATH.exists():
            self.db_path = DB_PATH
        else:
            self.db_path = PROJECT_ROOT.parent.parent / "05_Output_Workspace" / "EMR" / "snomed_ct_vet_reference.db"
        # Streamlit ScriptRunner가 별도 스레드에서 쿼리 실행 → check_same_thread=False 필수
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        count = self.conn.execute("SELECT COUNT(*) FROM concept").fetchone()[0]
        print(f"[SQL] SQLite 로드 완료: {count:,}건")

    # 메타 불용어: 의미 없는 쿼리 토큰 (스코어링/매칭에서 제외)
    # - SNOMED 메타 용어 + 일반 영어 관사/전치사/be동사/접속사
    _META_STOPWORDS = {
        "snomed", "sct", "code", "codes", "concept", "concepts", "id", "ids",
        "ct", "coding",
        "the", "a", "an", "of", "for", "to", "is", "and", "or",
        "in", "on", "at", "by", "with", "from", "as", "be", "are", "was", "were",
    }

    def search(self, query: str, top_k: int = 20) -> list[SearchResult]:
        """키워드 기반 SQL 검색.

        검색 전략:
        1. term_normalized = query 전체 정확 매칭 (최고 점수 1.0)
        2. 컨텐츠 토큰 AND LIKE (모든 의미 토큰 포함, 점수 0.8 × length_boost)
        3. 컨텐츠 토큰 OR LIKE (일부 매칭, 점수 비례 × 0.6)

        [수정 2026-04-17] 전체 쿼리 통째 LIKE 제거. 메타 불용어(snomed/code 등)는
        스코어링에서 제외하여 "feline panleukopenia SNOMED code"가 의미 토큰
        "feline"+"panleukopenia"로만 매칭되게 한다.
        """
        cur = self.conn.cursor()
        query_lower = query.lower().strip()
        all_tokens = [t for t in re.split(r'\s+', query_lower) if t]
        content_tokens = [t for t in all_tokens if t not in self._META_STOPWORDS and len(t) >= 2]
        if not content_tokens:
            content_tokens = all_tokens  # 전부 불용어면 원본 유지 (fallback)

        items = {}

        # 전략 1: 전체 쿼리 정확 매칭
        cur.execute("""
            SELECT DISTINCT c.concept_id, c.fsn, c.semantic_tag,
                   c.preferred_term, c.source, d.term
            FROM description d
            JOIN concept c ON d.concept_id = c.concept_id
            WHERE d.term_normalized = ?
            LIMIT ?
        """, (query_lower, top_k))

        for row in cur.fetchall():
            cid = row[0]
            if cid not in items:
                items[cid] = {
                    "concept_id": cid, "fsn": row[1], "semantic_tag": row[2],
                    "preferred_term": row[3] or row[1], "source": row[4],
                    "match_score": 1.0,
                }

        # 토큰별 LIKE 절 생성: 3글자 이하는 word-boundary, 4글자 이상은 substring
        # 이유: "cat"이 "catalase"/"educate"에 substring 매칭되는 false positive 차단
        def _token_clause(token: str) -> tuple[str, list]:
            if len(token) <= 3:
                clause = "(d.term_lower = ? OR d.term_lower LIKE ? OR d.term_lower LIKE ? OR d.term_lower LIKE ?)"
                return clause, [token, f"{token} %", f"% {token}", f"% {token} %"]
            return "d.term_lower LIKE ?", [f"%{token}%"]

        # 전략 2: 컨텐츠 토큰 AND + Graceful Degradation
        # SNOMED CT는 species-agnostic 설계 — "diabetes mellitus in cat"처럼 species
        # qualifier가 포함된 쿼리는 AND 매칭이 0건일 수 있음. 이 경우 가장 짧은
        # 토큰부터 제거하며 N-1, N-2... 재시도. 긴 토큰(질병명)이 보존됨.
        # 점수 = 0.8 × length_boost × (매칭된 토큰 수 / 전체 토큰 수)
        if len(items) < top_k and content_tokens:
            # 길이 내림차순: 긴 토큰(고유 질병명) 우선 유지, 짧은 토큰 먼저 탈락
            sorted_tokens = sorted(content_tokens, key=len, reverse=True)
            total_n = len(sorted_tokens)

            for active_n in range(total_n, 0, -1):
                active = sorted_tokens[:active_n]
                clauses, params = [], []
                for t in active:
                    c, p = _token_clause(t)
                    clauses.append(c)
                    params.extend(p)
                and_clause = " AND ".join(clauses)
                params.append(top_k * 3)
                cur.execute(f"""
                    SELECT DISTINCT c.concept_id, c.fsn, c.semantic_tag,
                           c.preferred_term, c.source, d.term
                    FROM description d
                    JOIN concept c ON d.concept_id = c.concept_id
                    WHERE {and_clause}
                    LIMIT ?
                """, params)
                rows = cur.fetchall()
                if not rows:
                    continue  # 이 레벨 실패 → 더 적은 토큰으로 재시도

                completeness = active_n / total_n  # 1.0 (full) → 1/N (단일)
                for row in rows:
                    cid = row[0]
                    if cid not in items:
                        fsn_len = len(row[1] or "")
                        length_boost = 50.0 / max(50, fsn_len)
                        items[cid] = {
                            "concept_id": cid, "fsn": row[1], "semantic_tag": row[2],
                            "preferred_term": row[3] or row[1], "source": row[4],
                            "match_score": 0.8 * length_boost * completeness,
                        }
                break  # 첫 성공 레벨에서 종료 (더 약한 매칭은 전략 3 OR이 커버)

        # 전략 3: 컨텐츠 토큰 OR (부분 매칭, AND 결과가 부족할 때)
        if len(items) < top_k and content_tokens:
            clauses, params = [], []
            for t in content_tokens:
                c, p = _token_clause(t)
                clauses.append(c)
                params.extend(p)
            or_clause = " OR ".join(clauses)
            params.append(top_k * 3)
            cur.execute(f"""
                SELECT DISTINCT c.concept_id, c.fsn, c.semantic_tag,
                       c.preferred_term, c.source, d.term
                FROM description d
                JOIN concept c ON d.concept_id = c.concept_id
                WHERE {or_clause}
                LIMIT ?
            """, params)

            for row in cur.fetchall():
                cid = row[0]
                if cid not in items:
                    term_lower = (row[5] or "").lower()
                    token_hits = sum(1 for t in content_tokens if t in term_lower)
                    match_score = (token_hits / len(content_tokens)) * 0.6
                    items[cid] = {
                        "concept_id": cid, "fsn": row[1], "semantic_tag": row[2],
                        "preferred_term": row[3] or row[1], "source": row[4],
                        "match_score": match_score,
                    }

        sorted_items = sorted(items.values(), key=lambda x: x["match_score"], reverse=True)[:top_k]

        results = []
        for rank, item in enumerate(sorted_items, start=1):
            results.append(SearchResult(
                concept_id=item["concept_id"],
                preferred_term=item["preferred_term"],
                fsn=item["fsn"],
                semantic_tag=item["semantic_tag"],
                source=item["source"],
                score=1.0 / (rank + 60),  # RRF 점수
                match_type="sql",
                sql_rank=rank,
            ))
        return results

    def get_relationships(self, concept_id: str, max_depth: int = 1) -> list[dict]:
        """특정 개념의 관계를 조회한다 (is-a, finding_site 등)."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT r.source_id, r.destination_id, r.type_id,
                   c_src.preferred_term as src_term,
                   c_dst.preferred_term as dst_term,
                   c_type.preferred_term as type_term
            FROM relationship r
            LEFT JOIN concept c_src ON r.source_id = c_src.concept_id
            LEFT JOIN concept c_dst ON r.destination_id = c_dst.concept_id
            LEFT JOIN concept c_type ON r.type_id = c_type.concept_id
            WHERE r.source_id = ? OR r.destination_id = ?
            LIMIT 30
        """, (concept_id, concept_id))

        rels = []
        for row in cur.fetchall():
            rels.append({
                "source_id": row[0],
                "destination_id": row[1],
                "type_id": row[2],
                "source_term": row[3],
                "destination_term": row[4],
                "type_term": row[5],
            })
        return rels

    def close(self):
        self.conn.close()


# ─── Merge: Reciprocal Rank Fusion ──────────────────────

def reciprocal_rank_fusion(
    vector_results: list[SearchResult],
    sql_results: list[SearchResult],
    k: int = 60,
    vector_weight: float = 0.4,
    sql_weight: float = 0.6,
) -> list[SearchResult]:
    """두 트랙의 결과를 RRF로 병합한다.

    Args:
        k: RRF 상수 (기본 60). 순위가 높을수록 점수가 급격히 감소.
        vector_weight: 벡터 검색 가중치.
        sql_weight: SQL 검색 가중치.
    """
    merged = {}

    # Track A 반영
    for item in vector_results:
        cid = item.concept_id
        if cid not in merged:
            merged[cid] = SearchResult(
                concept_id=cid,
                preferred_term=item.preferred_term,
                fsn=item.fsn,
                semantic_tag=item.semantic_tag,
                source=item.source,
                match_type="hybrid",
                vector_rank=item.vector_rank,
                vector_distance=item.vector_distance,
            )
        merged[cid].score += vector_weight * (1.0 / (item.vector_rank + k))
        merged[cid].vector_rank = item.vector_rank

    # Track B 반영
    for item in sql_results:
        cid = item.concept_id
        if cid not in merged:
            merged[cid] = SearchResult(
                concept_id=cid,
                preferred_term=item.preferred_term,
                fsn=item.fsn,
                semantic_tag=item.semantic_tag,
                source=item.source,
                match_type="hybrid",
                sql_rank=item.sql_rank,
            )
        merged[cid].score += sql_weight * (1.0 / (item.sql_rank + k))
        merged[cid].sql_rank = item.sql_rank

    # 점수 기준 정렬
    return sorted(merged.values(), key=lambda x: x.score, reverse=True)


# ─── Vector 전처리: 구어체 species qualifier 제거 ────────

# 제거 대상: 구어체 종명
# 보존 대상: 공식 SNOMED 라틴계 형용사 (feline, canine, bovine 등)
_COLLOQUIAL_SPECIES = (
    "cats", "cat", "dogs", "dog", "pigs", "pig",
    "cows", "cow", "horses", "horse", "sheep",
    "goats", "goat", "chickens", "chicken",
    "rabbits", "rabbit", "ferrets", "ferret",
    "birds", "bird", "fish",
)

# 복수형이 단수보다 먼저 매칭되도록 길이 내림차순 정렬
_COLLOQUIAL_SPECIES_SORTED = sorted(_COLLOQUIAL_SPECIES, key=len, reverse=True)

_SPECIES_JOINED = "|".join(_COLLOQUIAL_SPECIES_SORTED)

# 패턴 1: 전치사 + 구어체 종명 (원본 쿼리용)
#   "diabetes mellitus in cat" → "diabetes mellitus"
_SPECIES_PREP_PATTERN = re.compile(
    r"\b(in|of|for|from)\s+(" + _SPECIES_JOINED + r")\b",
    re.IGNORECASE,
)

# 패턴 2: 쿼리 끝에 단독으로 오는 구어체 종명 (불용어 제거 후 쿼리용)
#   rag_pipeline.preprocess_query 가 "in"을 제거하면
#   "diabetes mellitus in cat" → "diabetes mellitus cat" 이 된다.
#   이 경우 임상 용어(≥2 단어) 뒤에 종명이 단독으로 끝나면 제거한다.
#   단, "cat bite"처럼 종명이 수식어 역할인 경우는 제외 — 이를 구분하기 위해
#   종명 앞 토큰이 임상 의미어(≥4글자)일 때만 제거한다.
_SPECIES_TRAILING_PATTERN = re.compile(
    r"(?<=\S)\s+(" + _SPECIES_JOINED + r")$",
    re.IGNORECASE,
)


def preprocess_for_vector(query: str) -> str:
    """Vector 검색용 쿼리 전처리.

    구어체 species qualifier(in cat, in dogs, 또는 불용어 제거 후 trailing cat 등)를
    제거하여 임상 개념 임베딩에 species 노이즈가 섞이지 않게 한다.

    규칙:
    - 패턴1: 전치사(in/of/for/from) + 구어체 종명 → 제거
    - 패턴2: 쿼리 끝 단독 구어체 종명이고 앞 단어가 임상어(≥4글자)이면 제거
    - "cat bite", "dog food" 처럼 종명이 첫 번째 위치이거나 앞 단어가 단음절이면 보존
    - feline/canine/bovine 등 공식 SNOMED 형용사는 제거하지 않음
    """
    # 패턴1: 전치사 + 종명
    cleaned = _SPECIES_PREP_PATTERN.sub("", query).strip()

    # 패턴2: trailing 종명 (앞 단어가 임상어인 경우만)
    m = _SPECIES_TRAILING_PATTERN.search(cleaned)
    if m:
        # 종명 바로 앞 단어를 추출하여 임상어 여부 판단 (≥4글자이면 임상어로 간주)
        before_species = cleaned[:m.start()].strip()
        last_word_before = before_species.split()[-1] if before_species.split() else ""
        if len(last_word_before) >= 4:
            cleaned = before_species

    # 연속 공백 정규화
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned


# ─── 하이브리드 검색 엔진 ───────────────────────────────

# Reranker 설정 상수
_RERANK_CANDIDATE_K = 20   # rerank=True 시 1차 후보 수
_RERANK_TOP_N = 5          # rerank=True 시 최종 반환 수


class HybridSearchEngine:
    """Vector + SQL 하이브리드 검색 엔진.

    v2.0 추가: enable_rerank 파라미터 및 search() rerank 옵션.
    기본값 False → v1.0 코드 경로 완전 동일 유지 (regression 0 보장).
    rerank=True → Top-20 검색 후 BGEReranker → Top-5 반환.
    """

    def __init__(self, enable_rerank: bool = False):
        """초기화.

        Args:
            enable_rerank: True면 BGEReranker 모델을 지연 로딩 준비 상태로 전환.
                           False(기본)면 Reranker 관련 코드 완전 비활성화.
        """
        print("=" * 60)
        print(" Hybrid Search Engine 초기화")
        print("=" * 60)
        self.vector = VectorSearcher()
        self.sql = SQLRetriever()
        self._enable_rerank = enable_rerank
        self._reranker = None  # 지연 로딩: rerank=True 첫 호출 시 초기화
        print("[Hybrid] 초기화 완료\n")

    def _get_reranker(self):
        """BGEReranker 싱글턴을 반환한다 (최초 호출 시 모델 로드)."""
        if self._reranker is None:
            from src.retrieval.reranker import get_reranker
            self._reranker = get_reranker()
        return self._reranker

    def search(
        self,
        query: str,
        top_k: int = 10,
        vector_weight: float = 0.4,
        sql_weight: float = 0.6,
        include_relationships: bool = True,
        rerank: bool = False,
    ) -> list[SearchResult]:
        """하이브리드 검색을 실행한다.

        Args:
            rerank: True이면 BGEReranker로 재정렬 후 Top-5 반환.
                    False(기본)이면 v1.0과 완전 동일한 코드 경로.
                    rerank=True는 enable_rerank=True로 초기화된 엔진에서만 동작.
        """
        # ── v1.0 코드 경로 (rerank=False, 변경 없음) ─────────────────
        # Vector 전처리: 구어체 species qualifier 제거 (SQL은 원본 쿼리 유지)
        vector_query = preprocess_for_vector(query)
        species_removed = vector_query != query
        if species_removed:
            print(f"  [Vector 전처리] \"{query}\" → \"{vector_query}\"")

        # 2-track 전략: species qualifier가 있던 쿼리 = disorder 의도 강함
        # → Chroma metadata 필터로 disorder 한정 Vector 검색 추가 (Agent B 실측: 거리 0.49→0.39 개선)
        # rerank=True일 때는 더 많은 후보(_RERANK_CANDIDATE_K)를 가져옴
        candidate_k = _RERANK_CANDIDATE_K if (rerank and self._enable_rerank) else top_k
        vector_results = self.vector.search(vector_query, top_k=candidate_k * 2)
        if species_removed:
            disorder_results = self.vector.search(
                vector_query, top_k=candidate_k, where={"semantic_tag": "disorder"}
            )
            # 중복 제거하며 disorder 결과를 앞쪽에 병합 (RRF rank 보존)
            seen = {r.concept_id for r in disorder_results}
            merged_disorder = list(disorder_results) + [r for r in vector_results if r.concept_id not in seen]
            vector_results = merged_disorder[: candidate_k * 2]

        sql_results = self.sql.search(query, top_k=candidate_k * 2)

        # RRF 병합
        merged = reciprocal_rank_fusion(
            vector_results, sql_results,
            vector_weight=vector_weight,
            sql_weight=sql_weight,
        )[:candidate_k]

        # ── v2.0 Reranker 경로 (rerank=True일 때만 실행) ──────────────
        if rerank and self._enable_rerank:
            # R-4: 매핑 부적합 semantic_tag(situation 등) candidate에서 차단
            filtered_before = len(merged)
            merged = [r for r in merged if r.semantic_tag not in _MAPPING_INELIGIBLE_TAGS]
            if filtered_before > len(merged):
                print(f"  [R-4 filter] {filtered_before - len(merged)}건 매핑 부적합 tag 제외")
            reranker = self._get_reranker()
            reranked = reranker.rerank(query, merged, top_n=_RERANK_TOP_N)
            if reranked:
                # RerankedResult → SearchResult 호환: 관계 정보 추가
                if include_relationships:
                    for r in reranked[:3]:
                        r.relationships = self.sql.get_relationships(r.concept_id)
                print(f"  [Reranker] Top-{len(merged)} → Top-{len(reranked)} 재정렬 완료")
                return reranked  # type: ignore[return-value]
            # reranker가 빈 결과 반환 시 v1.0 경로 fallback

        # ── v1.0 경로 계속 (rerank=False 또는 reranker 실패 fallback) ──
        # 관계 정보 추가 (상위 결과만)
        if include_relationships:
            for result in merged[:3]:
                result.relationships = self.sql.get_relationships(result.concept_id)

        return merged

    def print_results(self, query: str, results: list[SearchResult]):
        """검색 결과를 포맷팅하여 출력한다."""
        print(f"\n{'─' * 60}")
        print(f"  Query: \"{query}\"")
        print(f"  Results: {len(results)}건")
        print(f"{'─' * 60}")

        for i, r in enumerate(results, 1):
            # 매칭 소스 표시
            sources = []
            if r.vector_rank:
                sources.append(f"V#{r.vector_rank}")
            if r.sql_rank:
                sources.append(f"S#{r.sql_rank}")
            source_str = "+".join(sources)

            print(f"\n  [{i}] {r.preferred_term}")
            print(f"      FSN: {r.fsn}")
            print(f"      ID: {r.concept_id} | Tag: {r.semantic_tag} | "
                  f"Source: {r.source} | Score: {r.score:.6f} | Match: {source_str}")

            if r.vector_distance is not None:
                print(f"      Vector Distance: {r.vector_distance:.4f}")

            # 관계 정보 (상위 3개만 표시)
            if r.relationships:
                print(f"      Relationships ({len(r.relationships)}건):")
                for rel in r.relationships[:5]:
                    direction = "→" if rel["source_id"] == r.concept_id else "←"
                    other_term = rel["destination_term"] if direction == "→" else rel["source_term"]
                    print(f"        {direction} [{rel['type_term']}] {other_term}")

    def close(self):
        self.sql.close()


# ─── CLI 실행 ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SNOMED VET 하이브리드 검색")
    parser.add_argument("--query", "-q", type=str, help="검색 쿼리")
    parser.add_argument("--interactive", "-i", action="store_true", help="인터랙티브 모드")
    parser.add_argument("--top-k", "-k", type=int, default=10, help="상위 결과 수")
    parser.add_argument("--json", action="store_true", help="JSON 출력")
    args = parser.parse_args()

    engine = HybridSearchEngine()

    if args.interactive:
        print("\n[인터랙티브 모드] 'q' 입력 시 종료\n")
        while True:
            query = input("검색> ").strip()
            if query.lower() in ("q", "quit", "exit"):
                break
            if not query:
                continue
            results = engine.search(query, top_k=args.top_k)
            engine.print_results(query, results)

    elif args.query:
        results = engine.search(args.query, top_k=args.top_k)
        if args.json:
            output = [
                {
                    "concept_id": r.concept_id,
                    "preferred_term": r.preferred_term,
                    "fsn": r.fsn,
                    "semantic_tag": r.semantic_tag,
                    "source": r.source,
                    "score": r.score,
                    "vector_rank": r.vector_rank,
                    "sql_rank": r.sql_rank,
                }
                for r in results
            ]
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            engine.print_results(args.query, results)

    else:
        # 기본 데모 쿼리
        demo_queries = [
            "feline panleukopenia virus infection",
            "canine elbow dysplasia",
            "dental extraction in cats",
            "blood glucose measurement",
            "bovine viral diarrhea",
        ]
        for q in demo_queries:
            results = engine.search(q, top_k=5)
            engine.print_results(q, results)

    engine.close()


if __name__ == "__main__":
    main()
