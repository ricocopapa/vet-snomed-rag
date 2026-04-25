"""PubMed E-utilities 클라이언트 — v2.5 Tier B 외부 도구.

NCBI Entrez E-utilities API (esearch + esummary).

[엔드포인트]
- Base: https://eutils.ncbi.nlm.nih.gov/entrez/eutils
- esearch.fcgi  → PMID 검색
- esummary.fcgi → PMID → 메타데이터 (title/journal/year/authors)
- 인증: &api_key={NCBI_API_KEY} (선택)

[Rate limit]
- 키 없음: 3 rps / 키 있음: 10 rps
- 위반 시 429 → exponential backoff (1·2·4s, 3회 후 포기)

[안전장치]
- API 키 미설정도 enabled=True (3 rps 모드로 동작)
- 모든 네트워크 오류 / non-2xx → 빈 결과 (graceful fallback)
- 토큰 버킷 rate limiter (thread-safe)
- LRU+TTL cache 24h

[설계서] docs/20260425_v2_5_tier_b_external_tools_design_v1.md §3-3
"""
from __future__ import annotations

import logging
import os
import time
from threading import Lock
from typing import Optional

import requests

from src.tools._cache import TTLCache

logger = logging.getLogger(__name__)

PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_TIMEOUT = 3.0
DEFAULT_TOP_K = 3
RATE_WITH_KEY = 10.0
RATE_WITHOUT_KEY = 3.0


class _TokenBucket:
    """thread-safe 토큰 버킷. acquire()는 1 토큰을 소비하며 부족 시 sleep."""

    def __init__(self, rate: float, capacity: Optional[float] = None):
        self.rate = rate
        self.capacity = capacity if capacity is not None else rate
        self.tokens = self.capacity
        self.last = time.monotonic()
        self.lock = Lock()

    def acquire(self) -> None:
        with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last = now
            if self.tokens < 1:
                wait = (1 - self.tokens) / self.rate
                time.sleep(wait)
                self.tokens = 0
                self.last = time.monotonic()
            else:
                self.tokens -= 1


class PubMedClient:
    """NCBI E-utilities 클라이언트.

    Args:
        api_key: 명시 키. None이면 env NCBI_API_KEY에서 로드. 빈 값이면 3 rps 모드.
        timeout: 요청 타임아웃 (초).
        cache: 외부 주입 cache. None이면 자체 TTLCache.
        backoff_schedule: 429 발생 시 재시도 간격 (초). 기본 [1, 2, 4].
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        cache: Optional[TTLCache] = None,
        backoff_schedule: Optional[list[float]] = None,
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("NCBI_API_KEY", "")
        self.timeout = timeout
        self.cache = cache or TTLCache(max_size=1000, ttl_seconds=86400)
        rate = RATE_WITH_KEY if self.api_key else RATE_WITHOUT_KEY
        self._bucket = _TokenBucket(rate=rate)
        self._backoff = list(backoff_schedule) if backoff_schedule is not None else [1.0, 2.0, 4.0]
        self._enabled = True

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def rps_limit(self) -> float:
        return self._bucket.rate

    def _request(self, path: str, params: dict) -> Optional[requests.Response]:
        """rate limit + 429 backoff GET. 모든 실패 → None."""
        params = dict(params)
        if self.api_key:
            params["api_key"] = self.api_key
        params.setdefault("tool", "vet-snomed-rag")
        url = f"{PUBMED_BASE}{path}"

        for attempt in range(len(self._backoff) + 1):
            self._bucket.acquire()
            try:
                r = requests.get(url, params=params, timeout=self.timeout)
            except requests.Timeout:
                logger.warning("PubMed timeout %.1fs path=%s", self.timeout, path)
                return None
            except requests.RequestException as e:
                logger.warning("PubMed request failure path=%s err=%s", path, e)
                return None

            if r.status_code == 429 and attempt < len(self._backoff):
                wait = self._backoff[attempt]
                logger.warning(
                    "PubMed 429 backoff %.1fs (attempt %d/%d)",
                    wait, attempt + 1, len(self._backoff),
                )
                time.sleep(wait)
                continue
            return r
        logger.warning("PubMed 429 after %d retries — give up", len(self._backoff))
        return None

    def search(self, query: str, top_k: int = DEFAULT_TOP_K) -> list[str]:
        """esearch → PMID 리스트."""
        if not query.strip():
            return []
        cache_key = f"esearch:{query}:{top_k}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        r = self._request(
            "/esearch.fcgi",
            params={"db": "pubmed", "term": query, "retmode": "json", "retmax": top_k},
        )
        if r is None or r.status_code != 200:
            return []
        try:
            data = r.json()
        except ValueError:
            return []
        pmids = data.get("esearchresult", {}).get("idlist", []) or []
        self.cache.set(cache_key, pmids)
        return pmids

    def fetch_summaries(self, pmids: list[str]) -> list[dict]:
        """esummary → 메타데이터 정규화 list (PMID 순서 보존)."""
        if not pmids:
            return []
        ids = ",".join(pmids)
        cache_key = f"esummary:{ids}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        r = self._request(
            "/esummary.fcgi",
            params={"db": "pubmed", "id": ids, "retmode": "json"},
        )
        if r is None or r.status_code != 200:
            return []
        try:
            data = r.json()
        except ValueError:
            return []
        result = data.get("result", {})
        if not isinstance(result, dict):
            return []
        normalized = []
        for pmid in pmids:
            entry = result.get(pmid)
            if not isinstance(entry, dict):
                continue
            authors_raw = entry.get("authors") or []
            authors = [
                a.get("name", "")
                for a in authors_raw
                if isinstance(a, dict)
            ][:3]
            normalized.append(
                {
                    "pmid": pmid,
                    "title": entry.get("title", ""),
                    "journal": entry.get("source", ""),
                    "year": (entry.get("pubdate", "") or "")[:4],
                    "authors": authors,
                    "source": "pubmed",
                }
            )
        self.cache.set(cache_key, normalized)
        return normalized

    def search_with_summaries(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
    ) -> list[dict]:
        """검색 + 요약 합본 (RAG context 합류용)."""
        pmids = self.search(query, top_k=top_k)
        if not pmids:
            return []
        return self.fetch_summaries(pmids)
