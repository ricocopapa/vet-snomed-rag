"""
BGE Reranker: BAAI/bge-reranker-v2-m3 기반 크로스인코더 재정렬 모듈.

[설계 원칙]
- Feature flag: HybridSearchEngine.search(rerank=False) 기본값 유지 → v1.0 경로 완전 동일 보장
- 리랭커 지연 로딩: enable_rerank=False면 모델 가중치 로드 없음
- sentence-transformers CrossEncoder API 사용 (기존 의존성 재활용, 추가 패키지 불필요)
- Top-20 후보 → CrossEncoder 점수 계산 → Top-5 반환

[BAAI/bge-reranker-v2-m3 선택 근거]
- MIT 라이선스, HuggingFace 공식 모델
- 다국어 지원 (한국어 포함) → T9 '고양이 당뇨' 같은 한국어 쿼리에도 적용 가능
- CrossEncoder API 직접 지원: sentence_transformers.CrossEncoder로 로드 가능

[실행 흐름]
    query: str
    candidates: list[SearchResult]   ← hybrid_search.py에서 Top-20 전달
        ↓
    CrossEncoder.predict([(query, candidate.preferred_term), ...])
        ↓
    rerank_scores 기준 내림차순 정렬
        ↓
    top_n 반환 (기본 5)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.retrieval.hybrid_search import SearchResult


# ─── 리랭커 결과 타입 ────────────────────────────────────

@dataclass
class RerankedResult:
    """리랭킹 결과 단일 항목 (원본 SearchResult + rerank 점수)."""
    concept_id: str
    preferred_term: str
    fsn: str
    semantic_tag: str
    source: str
    score: float           # 원본 하이브리드 점수 (RRF)
    rerank_score: float    # CrossEncoder 점수
    match_type: str
    vector_rank: Optional[int] = None
    sql_rank: Optional[int] = None
    vector_distance: Optional[float] = None
    relationships: list = None

    def __post_init__(self):
        if self.relationships is None:
            self.relationships = []


# ─── BGE Reranker 래퍼 ──────────────────────────────────

class BGEReranker:
    """BAAI/bge-reranker-v2-m3 기반 크로스인코더 재정렬기.

    sentence-transformers의 CrossEncoder API를 사용하므로
    추가 패키지 설치 없이 기존 requirements.txt(sentence-transformers>=2.7.0)만으로 동작.

    사용 예시:
        reranker = BGEReranker()
        reranked = reranker.rerank("feline panleukopenia", candidates, top_n=5)
    """

    MODEL_NAME = "BAAI/bge-reranker-v2-m3"

    def __init__(self, device: Optional[str] = None):
        """CrossEncoder 모델을 로드한다.

        Args:
            device: "cpu" / "cuda" / "mps". None이면 자동 감지.
        """
        from sentence_transformers import CrossEncoder  # type: ignore
        import torch

        if device is None:
            if torch.cuda.is_available():
                device = "cuda"
            elif torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"

        print(f"[Reranker] {self.MODEL_NAME} 로드 중... (device={device})")
        t0 = time.perf_counter()
        self._model = CrossEncoder(self.MODEL_NAME, device=device)
        elapsed = int((time.perf_counter() - t0) * 1000)
        print(f"[Reranker] 로드 완료 ({elapsed}ms)")
        self._device = device

    def rerank(
        self,
        query: str,
        candidates: list,       # list[SearchResult]
        top_n: int = 5,
    ) -> list:
        """후보 목록을 CrossEncoder 점수로 재정렬한다.

        Args:
            query: 원본 검색 쿼리 (전처리 전)
            candidates: hybrid_search 결과 list[SearchResult] (Top-20)
            top_n: 반환할 상위 결과 수 (기본 5)

        Returns:
            list[RerankedResult] - rerank_score 내림차순, 길이 min(top_n, len(candidates))
        """
        if not candidates:
            return []

        # CrossEncoder 입력: (query, document) 쌍
        # document = preferred_term + " " + fsn (더 풍부한 컨텍스트)
        pairs = []
        for c in candidates:
            doc = c.preferred_term
            if c.fsn and c.fsn != c.preferred_term:
                doc = f"{c.preferred_term} ({c.fsn})"
            pairs.append((query, doc))

        # 배치 예측 (반환값: numpy array of float)
        scores = self._model.predict(pairs)

        # SearchResult → RerankedResult 변환 + 점수 부착
        reranked = []
        for cand, rs in zip(candidates, scores):
            reranked.append(RerankedResult(
                concept_id=cand.concept_id,
                preferred_term=cand.preferred_term,
                fsn=cand.fsn,
                semantic_tag=cand.semantic_tag,
                source=cand.source,
                score=cand.score,          # 원본 RRF 점수 보존
                rerank_score=float(rs),
                match_type=cand.match_type,
                vector_rank=cand.vector_rank,
                sql_rank=cand.sql_rank,
                vector_distance=cand.vector_distance,
                relationships=cand.relationships or [],
            ))

        # rerank_score 내림차순 정렬
        reranked.sort(key=lambda x: x.rerank_score, reverse=True)

        return reranked[:top_n]


# ─── 지연 로딩 싱글턴 ────────────────────────────────────

_RERANKER_INSTANCE: Optional[BGEReranker] = None


def get_reranker(device: Optional[str] = None) -> BGEReranker:
    """BGEReranker 싱글턴을 반환한다 (최초 호출 시 로드).

    HybridSearchEngine에서 enable_rerank=True일 때만 호출됨.
    enable_rerank=False 경로에서는 절대 호출되지 않으므로 모델 로드 오버헤드 없음.
    """
    global _RERANKER_INSTANCE
    if _RERANKER_INSTANCE is None:
        _RERANKER_INSTANCE = BGEReranker(device=device)
    return _RERANKER_INSTANCE
