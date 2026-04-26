"""tests/test_cache.py — TTLCache 단위 테스트.

검증 항목 (6):
1. set/get 정상 hit
2. miss → None
3. update 시 move_to_end (LRU 순서 갱신)
4. max_size 초과 → 가장 오래된 항목 evict
5. TTL 만료 → None + 자동 삭제
6. clear / __len__ / __contains__
"""
from __future__ import annotations

import pytest

from src.tools._cache import TTLCache


def test_set_and_get_hit():
    cache = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("k1", {"v": 1})
    assert cache.get("k1") == {"v": 1}


def test_get_miss_returns_none():
    cache = TTLCache(max_size=10, ttl_seconds=60)
    assert cache.get("nonexistent") is None


def test_update_moves_to_end():
    """key 재set 시 LRU 순서 끝으로 갱신되어 evict 회피."""
    cache = TTLCache(max_size=2, ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    # a 재접근 → a가 최근 사용
    cache.set("a", 11)
    # 새 항목 추가 → 가장 오래된 b가 evict
    cache.set("c", 3)
    assert cache.get("a") == 11  # 살아있음
    assert cache.get("b") is None  # evict됨
    assert cache.get("c") == 3


def test_max_size_evicts_oldest():
    cache = TTLCache(max_size=3, ttl_seconds=60)
    cache.set("k1", 1)
    cache.set("k2", 2)
    cache.set("k3", 3)
    assert len(cache) == 3
    cache.set("k4", 4)  # k1 evict
    assert len(cache) == 3
    assert cache.get("k1") is None
    assert cache.get("k2") == 2
    assert cache.get("k3") == 3
    assert cache.get("k4") == 4


def test_ttl_expiry(monkeypatch):
    """TTL 만료 후 get() → None + 자동 삭제."""
    fake_time = [1000.0]

    def faketime():
        return fake_time[0]

    monkeypatch.setattr("src.tools._cache.time.time", faketime)
    cache = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("k1", "value")
    assert cache.get("k1") == "value"
    # 60초 경과 직전 → 살아있음
    fake_time[0] = 1059.5
    assert cache.get("k1") == "value"
    # 60초+ 경과 → 만료
    fake_time[0] = 1061.0
    assert cache.get("k1") is None
    assert len(cache) == 0  # 자동 삭제 확인


def test_clear_and_dunder_methods():
    cache = TTLCache(max_size=10, ttl_seconds=60)
    cache.set("k1", 1)
    cache.set("k2", 2)
    assert len(cache) == 2
    assert "k1" in cache
    assert "missing" not in cache

    cache.clear()
    assert len(cache) == 0
    assert "k1" not in cache


def test_invalid_args():
    with pytest.raises(ValueError):
        TTLCache(max_size=0)
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=0)
