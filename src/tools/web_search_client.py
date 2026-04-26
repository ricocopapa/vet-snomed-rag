"""Tavily Web Search 클라이언트 — v2.7 R-3 외부 도구 (Tier C).

Tavily Search REST API.

[엔드포인트]
- Base: https://api.tavily.com
- POST /search → query → results[{title, url, content, score}]
- 인증: `Authorization: Bearer {TAVILY_API_KEY}`

[가격 / Rate]
- Free: 1,000 credits/month (카드 불필요)
- Basic Search: 1 credit/호출, Advanced: 2 credits/호출
- Pay As You Go: $0.008/credit
- 명시적 rps 제한 없음 → 보수적으로 토큰 버킷 5 rps 적용 (예방적)
- 429 응답 시 exponential backoff (1·2·4s, 3회 후 포기)

[안전장치]
- env 미설정 시 enabled=False → 호출 0 (회귀 0 보장)
- 401 (인증 실패) → 빈 결과 + enabled=False (이후 호출 차단)
- 모든 네트워크 오류 / non-2xx → 빈 결과 (graceful fallback)
- LRU+TTL cache 24h (TTLCache 재사용)

[패턴 출처] src/tools/pubmed_client.py (v2.5 Tier B)
[설계 근거] docs/20260427_v2_7_roadmap_handoff.md §3-3
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

TAVILY_BASE = "https://api.tavily.com"
DEFAULT_TIMEOUT = 8.0
DEFAULT_TOP_K = 5
DEFAULT_RATE_RPS = 5.0
SUPPORTED_DEPTHS = ("basic", "fast", "advanced")


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


class TavilyWebSearchClient:
    """Tavily Search 클라이언트.

    Args:
        api_key: 명시 키. None이면 env TAVILY_API_KEY에서 로드. 빈 값이면 enabled=False.
        timeout: 요청 타임아웃 (초).
        cache: 외부 주입 cache. None이면 자체 TTLCache.
        rate_rps: 초당 요청 한도 (예방적 보수치). default 5 rps.
        backoff_schedule: 429 발생 시 재시도 간격 (초). default [1, 2, 4].
        search_depth: 'basic' / 'fast' / 'advanced'. default 'basic' (1 credit).
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        cache: Optional[TTLCache] = None,
        rate_rps: float = DEFAULT_RATE_RPS,
        backoff_schedule: Optional[list[float]] = None,
        search_depth: str = "basic",
    ):
        self.api_key = api_key if api_key is not None else os.environ.get("TAVILY_API_KEY", "")
        self.timeout = timeout
        self.cache = cache or TTLCache(max_size=1000, ttl_seconds=86400)
        self._bucket = _TokenBucket(rate=rate_rps)
        self._backoff = list(backoff_schedule) if backoff_schedule is not None else [1.0, 2.0, 4.0]
        if search_depth not in SUPPORTED_DEPTHS:
            raise ValueError(
                f"search_depth must be one of {SUPPORTED_DEPTHS}, got {search_depth!r}"
            )
        self.search_depth = search_depth
        self._enabled = bool(self.api_key)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def rps_limit(self) -> float:
        return self._bucket.rate

    def _post(self, path: str, body: dict) -> Optional[requests.Response]:
        """rate limit + 429 backoff POST. 모든 실패 → None.

        401 (인증 실패) 발생 시 enabled=False로 영구 차단.
        """
        if not self._enabled:
            return None
        url = f"{TAVILY_BASE}{path}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        for attempt in range(len(self._backoff) + 1):
            self._bucket.acquire()
            try:
                r = requests.post(url, json=body, headers=headers, timeout=self.timeout)
            except requests.Timeout:
                logger.warning("Tavily timeout %.1fs path=%s", self.timeout, path)
                return None
            except requests.RequestException as e:
                logger.warning("Tavily request failure path=%s err=%s", path, e)
                return None

            if r.status_code == 401:
                # 키 invalid → 영구 차단
                logger.warning("Tavily 401 unauthorized — disabling client")
                self._enabled = False
                return None

            if r.status_code == 429 and attempt < len(self._backoff):
                wait = self._backoff[attempt]
                logger.warning(
                    "Tavily 429 backoff %.1fs (attempt %d/%d)",
                    wait, attempt + 1, len(self._backoff),
                )
                time.sleep(wait)
                continue
            return r
        logger.warning("Tavily 429 after %d retries — give up", len(self._backoff))
        return None

    def search(
        self,
        query: str,
        top_k: int = DEFAULT_TOP_K,
        topic: str = "general",
    ) -> list[dict]:
        """Web 검색 → 정규화된 결과 list.

        Args:
            query: 검색 쿼리.
            top_k: 0~20 결과. Tavily max_results.
            topic: 'general' / 'news'.

        Returns:
            [{"title", "url", "content", "score", "source": "tavily"}]
            실패 / 빈 응답 / disabled → [].
        """
        if not self._enabled:
            return []
        if not query.strip():
            return []
        # top_k 클램프 (Tavily 제한)
        top_k = max(0, min(top_k, 20))
        if top_k == 0:
            return []

        cache_key = f"search:{self.search_depth}:{topic}:{top_k}:{query}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        body = {
            "query": query,
            "max_results": top_k,
            "search_depth": self.search_depth,
            "topic": topic,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
        }
        r = self._post("/search", body)
        if r is None or r.status_code != 200:
            return []
        try:
            data = r.json()
        except ValueError:
            return []
        raw_results = data.get("results", []) or []
        if not isinstance(raw_results, list):
            return []
        normalized: list[dict] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            normalized.append(
                {
                    "title": item.get("title", "") or "",
                    "url": item.get("url", "") or "",
                    "content": item.get("content", "") or "",
                    "score": float(item.get("score", 0.0) or 0.0),
                    "source": "tavily",
                }
            )
        self.cache.set(cache_key, normalized)
        return normalized
