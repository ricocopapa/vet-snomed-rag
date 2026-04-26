"""TTLCache — LRU + TTL 결합 캐시.

UMLS / PubMed 외부 API 클라이언트가 공유. rate limit 보호 + latency 절감 목적.

[설계 결정]
- OrderedDict 기반 LRU (move_to_end로 최근 사용 추적)
- 항목별 만료 시각 저장 (now > expiry → 자동 삭제)
- threading.Lock 으로 동시 접근 보호 (단일 프로세스 + 향후 병렬 fetch 대비)
- 최대 용량 초과 시 가장 오래된(LRU) 항목 evict
- 타입 일반화 (Any) — 모든 직렬화 가능한 객체 저장

[설계서] docs/20260425_v2_5_tier_b_external_tools_design_v1.md §3-3
"""
from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Optional


class TTLCache:
    """LRU + TTL 결합 캐시. thread-safe.

    Args:
        max_size: 최대 항목 수. 초과 시 LRU evict.
        ttl_seconds: 항목별 유효 시간(초). 만료 시 get()이 None 반환 + 삭제.

    Example:
        cache = TTLCache(max_size=1000, ttl_seconds=86400)
        cache.set("cui:C0011849", {"preferred": "Diabetes Mellitus"})
        result = cache.get("cui:C0011849")  # 24h 내면 hit
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 86400):
        if max_size < 1:
            raise ValueError("max_size must be >= 1")
        if ttl_seconds < 1:
            raise ValueError("ttl_seconds must be >= 1")
        self._cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max = max_size
        self._ttl = ttl_seconds
        self._lock = Lock()

    def get(self, key: str) -> Optional[Any]:
        """key 조회. miss 또는 TTL 만료 시 None."""
        with self._lock:
            if key not in self._cache:
                return None
            expiry, value = self._cache[key]
            if time.time() > expiry:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        """key=value 저장. 용량 초과 시 LRU evict."""
        with self._lock:
            expiry = time.time() + self._ttl
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (expiry, value)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._cache)

    def __contains__(self, key: str) -> bool:
        return self.get(key) is not None
