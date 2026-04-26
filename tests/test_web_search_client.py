"""tests/test_web_search_client.py — TavilyWebSearchClient 단위 테스트.

검증 항목 (≥ 7건):
1. env 미설정 → enabled=False (회귀 0 보장)
2. 키 있음 → enabled=True, 기본 rps
3. invalid search_depth → ValueError
4. search 정상 → 정규화된 list (title/url/content/score/source=tavily)
5. 401 (인증 실패) → 빈 결과 + enabled=False (영구 차단)
6. 429 → backoff 후 재시도 성공
7. 429 exhausted → 빈 결과
8. timeout → 빈 결과
9. cache hit
10. 빈 query → 빈 결과
11. top_k=0 또는 음수 → 빈 결과 (호출 0)
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from src.tools._cache import TTLCache
from src.tools.web_search_client import TavilyWebSearchClient


# ── 응답 fixture ─────────────────────────────────────────────


def _ok(json_data):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = json_data
    return r


def _http(status):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {}
    return r


_FAKE_SEARCH_RESPONSE = {
    "query": "feline diabetes latest news",
    "results": [
        {
            "title": "Latest Feline Diabetes Treatment 2026",
            "url": "https://example.com/article1",
            "content": "Recent advances in feline diabetes management...",
            "score": 0.92,
        },
        {
            "title": "Veterinary Endocrinology Update",
            "url": "https://example.com/article2",
            "content": "New insulin formulations for cats...",
            "score": 0.85,
        },
    ],
    "response_time": 0.5,
    "usage": {"credits": 1},
}


# ── 1. env 미설정 → 비활성 ─────────────────────────────────


def test_no_key_disables_client(monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    client = TavilyWebSearchClient()
    assert client.enabled is False
    assert client.search("anything") == []


# ── 2. 키 있음 → 활성 ──────────────────────────────────────


def test_with_key_is_enabled():
    client = TavilyWebSearchClient(api_key="tvly-fake-key")
    assert client.enabled is True
    assert client.rps_limit == 5.0


# ── 3. invalid search_depth → ValueError ───────────────────


def test_invalid_search_depth_raises():
    with pytest.raises(ValueError):
        TavilyWebSearchClient(api_key="tvly-fake", search_depth="ultra-bogus")


# ── 4. search 정상 → 정규화 ────────────────────────────────


def test_search_returns_normalized_results(monkeypatch):
    fake = _ok(_FAKE_SEARCH_RESPONSE)
    monkeypatch.setattr(requests, "post", lambda *a, **kw: fake)
    client = TavilyWebSearchClient(api_key="tvly-fake-key")
    out = client.search("feline diabetes latest news", top_k=2)
    assert len(out) == 2
    assert out[0]["title"] == "Latest Feline Diabetes Treatment 2026"
    assert out[0]["url"] == "https://example.com/article1"
    assert out[0]["content"].startswith("Recent advances")
    assert out[0]["score"] == pytest.approx(0.92)
    assert out[0]["source"] == "tavily"
    assert out[1]["score"] == pytest.approx(0.85)


def test_search_authorization_header(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["body"] = json
        return _ok(_FAKE_SEARCH_RESPONSE)

    monkeypatch.setattr(requests, "post", fake_post)
    client = TavilyWebSearchClient(api_key="tvly-real-secret")
    client.search("query", top_k=3)
    assert captured["url"].endswith("/search")
    assert captured["headers"]["Authorization"] == "Bearer tvly-real-secret"
    assert captured["body"]["query"] == "query"
    assert captured["body"]["max_results"] == 3
    assert captured["body"]["search_depth"] == "basic"


# ── 5. 401 → 빈 결과 + 영구 차단 ───────────────────────────


def test_401_disables_client(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _http(401))
    client = TavilyWebSearchClient(api_key="tvly-bad-key", backoff_schedule=[0.0])
    assert client.search("test") == []
    # 영구 차단 — 재호출도 빈 결과
    assert client.enabled is False
    assert client.search("test2") == []


# ── 6. 429 → backoff 후 재시도 성공 ────────────────────────


def test_429_then_success(monkeypatch):
    responses = [_http(429), _ok(_FAKE_SEARCH_RESPONSE)]
    call_count = [0]

    def fake_post(*a, **kw):
        idx = call_count[0]
        call_count[0] += 1
        return responses[idx]

    monkeypatch.setattr(requests, "post", fake_post)
    client = TavilyWebSearchClient(api_key="tvly-fake-key", backoff_schedule=[0.0, 0.0, 0.0])
    out = client.search("test")
    assert len(out) == 2
    assert call_count[0] == 2


# ── 7. 429 exhausted → 빈 결과 ─────────────────────────────


def test_429_exhausted_returns_empty(monkeypatch):
    monkeypatch.setattr(requests, "post", lambda *a, **kw: _http(429))
    client = TavilyWebSearchClient(api_key="tvly-fake-key", backoff_schedule=[0.0, 0.0, 0.0])
    assert client.search("test") == []


# ── 8. timeout → 빈 결과 ───────────────────────────────────


def test_timeout_returns_empty(monkeypatch):
    def raise_timeout(*a, **kw):
        raise requests.Timeout()

    monkeypatch.setattr(requests, "post", raise_timeout)
    client = TavilyWebSearchClient(
        api_key="tvly-fake-key", timeout=0.1, backoff_schedule=[0.0]
    )
    assert client.search("test") == []


# ── 9. cache hit ───────────────────────────────────────────


def test_cache_hit_skips_request(monkeypatch):
    call_count = [0]
    fake = _ok(_FAKE_SEARCH_RESPONSE)

    def fake_post(*a, **kw):
        call_count[0] += 1
        return fake

    monkeypatch.setattr(requests, "post", fake_post)
    cache = TTLCache(max_size=10, ttl_seconds=60)
    client = TavilyWebSearchClient(api_key="tvly-fake-key", cache=cache)
    out1 = client.search("query", top_k=2)
    out2 = client.search("query", top_k=2)  # cache hit
    assert call_count[0] == 1
    assert out1 == out2


# ── 10. 빈 query / top_k=0 → 빈 결과 (호출 0) ──────────────


def test_empty_query_returns_empty():
    client = TavilyWebSearchClient(api_key="tvly-fake-key")
    assert client.search("   ") == []


def test_top_k_zero_returns_empty(monkeypatch):
    call_count = [0]

    def fake_post(*a, **kw):
        call_count[0] += 1
        return _ok(_FAKE_SEARCH_RESPONSE)

    monkeypatch.setattr(requests, "post", fake_post)
    client = TavilyWebSearchClient(api_key="tvly-fake-key")
    assert client.search("test", top_k=0) == []
    assert call_count[0] == 0  # 호출 0 보장
