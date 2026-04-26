"""tests/test_umls_client.py — UMLSClient 단위 테스트.

검증 항목:
1. env 미설정 → enabled=False, search() = []
2. mock 정상 응답 → search 정규화 결과
3. mock 401 → enabled=False + 후속 호출 즉시 빈 결과
4. mock 429 → 빈 결과 (enabled 유지)
5. mock timeout → 빈 결과
6. cache hit — 동일 쿼리 재호출 시 requests.get 0회 추가
7. get_cross_walks 정규화 (URL code 정제, dedupe, sort)
8. search_with_cross_walks 합산본 검증
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import requests

from src.tools._cache import TTLCache
from src.tools.umls_client import UMLSClient


# ── 응답 fixture ────────────────────────────────────────────


def _ok(json_data):
    r = MagicMock()
    r.status_code = 200
    r.json.return_value = json_data
    r.raise_for_status = MagicMock()
    return r


def _http(status):
    r = MagicMock()
    r.status_code = status
    r.json.return_value = {}
    return r


# ── 1. env 미설정 → 자동 비활성 ──────────────────────────────


def test_env_missing_disables_client(monkeypatch):
    monkeypatch.delenv("UMLS_API_KEY", raising=False)
    client = UMLSClient()
    assert client.enabled is False
    assert client.search("diabetes") == []
    assert client.get_concept("C0011849") is None
    assert client.get_cross_walks("C0011849") == {}


# ── 2. 정상 응답 → 정규화 ───────────────────────────────────


def test_search_normalizes_results(monkeypatch):
    fake_response = _ok(
        {
            "result": {
                "results": [
                    {"ui": "C0011849", "name": "Diabetes Mellitus, Type 2"},
                    {"ui": "C0011860", "name": "Type 2 diabetes"},
                    {"ui": "NONE", "name": "no results"},  # 필터링 대상
                ]
            }
        }
    )
    captured = []

    def fake_get(url, params=None, timeout=None):
        captured.append((url, params))
        return fake_response

    monkeypatch.setattr(requests, "get", fake_get)
    client = UMLSClient(api_key="fake-key")
    out = client.search("diabetes", top_k=3)
    assert len(out) == 2
    assert out[0]["cui"] == "C0011849"
    assert out[0]["source"] == "umls"
    # 인증 키 + 쿼리 파라미터 전달 확인
    assert captured[0][1]["apiKey"] == "fake-key"
    assert captured[0][1]["string"] == "diabetes"
    assert captured[0][1]["pageSize"] == 3


# ── 3. 401 → enabled=False 영구 ─────────────────────────────


def test_401_disables_client_permanently(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _http(401))
    client = UMLSClient(api_key="bad-key")
    assert client.enabled is True  # 처음엔 True
    assert client.search("diabetes") == []
    assert client.enabled is False  # 401 후 영구 비활성
    # 후속 호출도 즉시 빈 결과
    assert client.get_concept("C0011849") is None


# ── 4. 429 → 빈 결과, enabled 유지 ──────────────────────────


def test_429_returns_empty_keeps_enabled(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: _http(429))
    client = UMLSClient(api_key="fake-key")
    assert client.search("diabetes") == []
    assert client.enabled is True  # rate limit은 일시적이므로 유지


# ── 5. timeout → 빈 결과 ────────────────────────────────────


def test_timeout_returns_empty(monkeypatch):
    def raise_timeout(*a, **kw):
        raise requests.Timeout()

    monkeypatch.setattr(requests, "get", raise_timeout)
    client = UMLSClient(api_key="fake-key", timeout=0.1)
    assert client.search("diabetes") == []
    assert client.enabled is True


# ── 6. cache hit — 재호출 시 외부 호출 0 ─────────────────────


def test_cache_hit_skips_request(monkeypatch):
    call_count = [0]
    fake = _ok({"result": {"results": [{"ui": "C0011849", "name": "DM"}]}})

    def fake_get(*a, **kw):
        call_count[0] += 1
        return fake

    monkeypatch.setattr(requests, "get", fake_get)
    cache = TTLCache(max_size=10, ttl_seconds=60)
    client = UMLSClient(api_key="fake-key", cache=cache)
    out1 = client.search("diabetes", top_k=1)
    out2 = client.search("diabetes", top_k=1)  # cache hit
    assert call_count[0] == 1
    assert out1 == out2


# ── 7. cross-walk 정규화 ────────────────────────────────────


def test_cross_walks_normalize(monkeypatch):
    fake = _ok(
        {
            "result": [
                {"rootSource": "ICD10CM", "code": "https://uts/.../E11.9"},
                {"rootSource": "ICD10CM", "code": "E11.9"},  # 중복 → dedupe
                {"rootSource": "MSH", "code": "D003924"},
                {"rootSource": "", "code": "X"},  # 무효
                {"rootSource": "SNOMEDCT_US", "code": ""},  # 무효
            ]
        }
    )
    monkeypatch.setattr(requests, "get", lambda *a, **kw: fake)
    client = UMLSClient(api_key="fake-key")
    xw = client.get_cross_walks("C0011849", sources=["ICD10CM", "MSH"])
    assert xw == {"ICD10CM": ["E11.9"], "MSH": ["D003924"]}


# ── 8. search_with_cross_walks 합산본 ───────────────────────


def test_search_with_cross_walks_combines(monkeypatch):
    """검색 + concept + cross-walk이 한 호출에서 합쳐짐."""
    responses = {
        "/search/current": _ok(
            {"result": {"results": [{"ui": "C0011849", "name": "DM Type 2"}]}}
        ),
        "/content/current/CUI/C0011849": _ok(
            {
                "result": {
                    "ui": "C0011849",
                    "name": "DM Type 2",
                    "semanticTypes": [{"name": "Disease or Syndrome"}],
                }
            }
        ),
        "/content/current/CUI/C0011849/atoms": _ok(
            {"result": [{"rootSource": "ICD10CM", "code": "E11.9"}]}
        ),
    }

    def fake_get(url, params=None, timeout=None):
        # 더 긴 path가 더 구체적이므로 우선 매칭 (예: /atoms가 /CUI/{cui}보다 우선)
        for path in sorted(responses.keys(), key=len, reverse=True):
            if path in url:
                return responses[path]
        return _http(404)

    monkeypatch.setattr(requests, "get", fake_get)
    client = UMLSClient(api_key="fake-key")
    out = client.search_with_cross_walks("diabetes", top_k=1, sources=["ICD10CM"])
    assert len(out) == 1
    assert out[0]["cui"] == "C0011849"
    assert "Disease or Syndrome" in out[0]["semantic_types"]
    assert out[0]["cross_walks"] == {"ICD10CM": ["E11.9"]}
