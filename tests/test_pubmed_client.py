"""tests/test_pubmed_client.py — PubMedClient 단위 테스트.

검증 항목:
1. env 미설정 → enabled=True, rps=3
2. env 있음 → rps=10
3. esearch 정상 → PMID list
4. fetch_summaries 정상 → 정규화 (year 4자리, authors max 3, 순서 보존)
5. search_with_summaries 통합
6. 429 → backoff 후 재시도 성공
7. 429 무한 → 빈 결과 (포기)
8. timeout → 빈 결과
9. cache hit (esearch + esummary 각각)
10. 빈 PMID 입력 → 빈 결과
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from src.tools._cache import TTLCache
from src.tools.pubmed_client import PubMedClient


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


# ── 1. env 미설정 → 3 rps ──────────────────────────────────


def test_no_key_uses_3_rps(monkeypatch):
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    client = PubMedClient()
    assert client.enabled is True
    assert client.rps_limit == 3.0


def test_with_key_uses_10_rps():
    client = PubMedClient(api_key="fake-key")
    assert client.rps_limit == 10.0


# ── 2. esearch 정상 ────────────────────────────────────────


def test_esearch_returns_pmid_list(monkeypatch):
    fake = _ok({"esearchresult": {"idlist": ["37123456", "37123457", "37123458"]}})
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake)
    client = PubMedClient(api_key="fake-key")
    pmids = client.search("feline diabetes", top_k=3)
    assert pmids == ["37123456", "37123457", "37123458"]


def test_esearch_empty_query_returns_empty():
    client = PubMedClient(api_key="fake-key")
    assert client.search("   ") == []


# ── 3. fetch_summaries 정규화 ──────────────────────────────


def test_fetch_summaries_normalizes(monkeypatch):
    fake = _ok(
        {
            "result": {
                "37123456": {
                    "title": "Insulin therapy in cats",
                    "source": "Vet J",
                    "pubdate": "2025 Mar 15",
                    "authors": [
                        {"name": "Smith J"},
                        {"name": "Lee K"},
                        {"name": "Park S"},
                        {"name": "Kim H"},  # 4번째 → 잘림
                    ],
                },
                "37123457": {
                    "title": "Feline diabetes review",
                    "source": "JFMS",
                    "pubdate": "2024 Dec",
                    "authors": [{"name": "Doe A"}],
                },
            }
        }
    )
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake)
    client = PubMedClient(api_key="fake-key")
    out = client.fetch_summaries(["37123456", "37123457"])
    assert len(out) == 2
    assert out[0]["pmid"] == "37123456"
    assert out[0]["year"] == "2025"  # 4자리만
    assert len(out[0]["authors"]) == 3  # max 3
    assert out[1]["title"] == "Feline diabetes review"


def test_fetch_summaries_empty_pmids():
    client = PubMedClient(api_key="fake-key")
    assert client.fetch_summaries([]) == []


# ── 4. search_with_summaries 통합 ──────────────────────────


def test_search_with_summaries_integrates(monkeypatch):
    responses = {
        "/esearch.fcgi": _ok({"esearchresult": {"idlist": ["111"]}}),
        "/esummary.fcgi": _ok(
            {
                "result": {
                    "111": {
                        "title": "Test",
                        "source": "Vet J",
                        "pubdate": "2026",
                        "authors": [],
                    }
                }
            }
        ),
    }

    def fake_get(url, params=None, timeout=None):
        for path, resp in responses.items():
            if path in url:
                return resp
        return _http(404)

    monkeypatch.setattr(requests, "get", fake_get)
    client = PubMedClient(api_key="fake-key")
    out = client.search_with_summaries("test", top_k=1)
    assert len(out) == 1
    assert out[0]["pmid"] == "111"
    assert out[0]["source"] == "pubmed"


# ── 5. 429 → backoff 후 재시도 성공 ────────────────────────


def test_429_then_success(monkeypatch):
    """첫 응답 429 → 두 번째 응답 200 (backoff 후 재시도)."""
    responses = [_http(429), _ok({"esearchresult": {"idlist": ["999"]}})]
    call_count = [0]

    def fake_get(*a, **kw):
        idx = call_count[0]
        call_count[0] += 1
        return responses[idx]

    monkeypatch.setattr(requests, "get", fake_get)
    # backoff 0초로 설정해 테스트 시간 단축
    client = PubMedClient(api_key="fake-key", backoff_schedule=[0.0, 0.0, 0.0])
    pmids = client.search("test")
    assert pmids == ["999"]
    assert call_count[0] == 2


def test_429_exhausted_returns_empty(monkeypatch):
    """모든 backoff 소진 → 빈 결과."""
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _http(429))
    client = PubMedClient(api_key="fake-key", backoff_schedule=[0.0, 0.0, 0.0])
    assert client.search("test") == []


# ── 6. timeout → 빈 결과 ───────────────────────────────────


def test_timeout_returns_empty(monkeypatch):
    def raise_timeout(*a, **kw):
        raise requests.Timeout()

    monkeypatch.setattr(requests, "get", raise_timeout)
    client = PubMedClient(api_key="fake-key", timeout=0.1, backoff_schedule=[0.0])
    assert client.search("test") == []


# ── 7. cache hit ───────────────────────────────────────────


def test_cache_hit_skips_request(monkeypatch):
    call_count = [0]
    fake = _ok({"esearchresult": {"idlist": ["111"]}})

    def fake_get(*a, **kw):
        call_count[0] += 1
        return fake

    monkeypatch.setattr(requests, "get", fake_get)
    cache = TTLCache(max_size=10, ttl_seconds=60)
    client = PubMedClient(api_key="fake-key", cache=cache)
    out1 = client.search("test", top_k=1)
    out2 = client.search("test", top_k=1)  # cache hit
    assert call_count[0] == 1
    assert out1 == out2
