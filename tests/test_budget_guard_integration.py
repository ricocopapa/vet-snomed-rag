"""tests/test_budget_guard_integration.py — v2.9+ phase 1 runtime 통합 검증.

[설계서] docs/20260427_r10_payg_simulation.md §4-4
[모듈]   src/observability/__init__.py (싱글톤) + src/retrieval/agentic/synthesizer.py + src/tools/web_search_client.py

검증 항목:
1. synthesizer가 Gemini usage_metadata 있을 때 BudgetGuard에 기록
2. synthesizer가 usage_metadata 없을 때 silent skip (예외 X)
3. web_search_client가 성공 호출 시 Tavily credit 기록 (depth 반영)
4. web_search_client cache hit은 credit 미기록 (이중 카운트 방지)
5. web_search_client 실패(non-200) 시 credit 미기록
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.observability import get_budget_guard, reset_budget_guard  # noqa: E402
from src.retrieval.agentic.synthesizer import ExternalSynthesizerAgent  # noqa: E402
from src.tools.web_search_client import TavilyWebSearchClient  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_guard():
    reset_budget_guard()
    yield
    reset_budget_guard()


def _http(status: int, body=None):
    r = MagicMock(spec=requests.Response)
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    r.headers = {}
    return r


class TestSynthesizerHook:
    def test_records_gemini_usage_when_metadata_present(self):
        fake_usage = MagicMock()
        fake_usage.prompt_token_count = 600
        fake_usage.candidates_token_count = 80

        fake_response = MagicMock()
        fake_response.text = "synthesized output"
        fake_response.usage_metadata = fake_usage

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = fake_response

        agent = ExternalSynthesizerAgent()

        with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=False), \
             patch("google.genai.Client", return_value=fake_client):
            agent._synthesize_gemini(
                query="q",
                base_answer="base",
                external_results={"umls": [{"cui": "C0", "name": "x"}]},
            )

        guard = get_budget_guard()
        assert guard.gemini.input_tokens == 600
        assert guard.gemini.output_tokens == 80
        assert guard.gemini.request_count_today == 1

    def test_silent_when_no_usage_metadata(self):
        fake_response = MagicMock(spec=["text"])  # usage_metadata 속성 없음
        fake_response.text = "ok"

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = fake_response

        agent = ExternalSynthesizerAgent()

        with patch("src.retrieval.agentic.synthesizer._ensure_env_loaded"), \
             patch.dict(os.environ, {"GOOGLE_API_KEY": "fake-key"}, clear=False), \
             patch("google.genai.Client", return_value=fake_client):
            result = agent._synthesize_gemini(
                query="q",
                base_answer="base",
                external_results={"umls": [{"cui": "C0", "name": "x"}]},
            )

        assert result.used is True
        guard = get_budget_guard()
        assert guard.gemini.input_tokens == 0
        assert guard.gemini.output_tokens == 0


class TestWebSearchHook:
    def _client_with_key(self, monkeypatch, depth="basic"):
        monkeypatch.setenv("TAVILY_API_KEY", "fake-key")
        return TavilyWebSearchClient(search_depth=depth)

    def test_records_basic_credit_on_success(self, monkeypatch):
        client = self._client_with_key(monkeypatch, depth="basic")
        ok = _http(200, {"results": [{"title": "t", "url": "u", "content": "c", "score": 0.9}]})
        monkeypatch.setattr(requests, "post", lambda *a, **kw: ok)
        out = client.search("q", top_k=3)
        assert len(out) == 1
        guard = get_budget_guard()
        assert guard.tavily.credits_used == 1

    def test_records_advanced_credit_on_success(self, monkeypatch):
        client = self._client_with_key(monkeypatch, depth="advanced")
        ok = _http(200, {"results": [{"title": "t", "url": "u", "content": "c", "score": 0.9}]})
        monkeypatch.setattr(requests, "post", lambda *a, **kw: ok)
        client.search("q", top_k=3)
        guard = get_budget_guard()
        assert guard.tavily.credits_used == 2

    def test_no_record_on_cache_hit(self, monkeypatch):
        client = self._client_with_key(monkeypatch, depth="basic")
        ok = _http(200, {"results": [{"title": "t", "url": "u", "content": "c", "score": 0.9}]})

        call_count = {"n": 0}

        def fake_post(*a, **kw):
            call_count["n"] += 1
            return ok

        monkeypatch.setattr(requests, "post", fake_post)
        client.search("dup-query", top_k=3)
        client.search("dup-query", top_k=3)  # cache hit
        guard = get_budget_guard()
        assert call_count["n"] == 1, "second call must hit cache"
        assert guard.tavily.credits_used == 1, "cache hit must not consume credits"

    def test_no_record_on_failure(self, monkeypatch):
        client = self._client_with_key(monkeypatch, depth="basic")
        monkeypatch.setattr(requests, "post", lambda *a, **kw: _http(500))
        out = client.search("q", top_k=3)
        assert out == []
        guard = get_budget_guard()
        assert guard.tavily.credits_used == 0


class TestSingletonAccessor:
    def test_get_budget_guard_returns_same_instance(self):
        a = get_budget_guard()
        b = get_budget_guard()
        assert a is b

    def test_reset_budget_guard_clears_singleton(self):
        a = get_budget_guard()
        reset_budget_guard()
        b = get_budget_guard()
        assert a is not b


# ──────────────────────────────────────────────────────────────────────────────
# v3.1 R-5+ — Reformulator Hook + 영속화 시나리오 통합 검증
# ──────────────────────────────────────────────────────────────────────────────

class TestReformulatorHook:
    """Gemini reformulator → BudgetGuard 통합 (v3.1 production 통합 잔여 결손 해소)."""

    def test_records_gemini_usage_when_metadata_present(self, monkeypatch):
        from src.retrieval.query_reformulator import GeminiReformulator

        fake_usage = MagicMock()
        fake_usage.prompt_token_count = 350
        fake_usage.candidates_token_count = 60

        fake_response = MagicMock()
        fake_response.text = '{"reformulated": "diabetes mellitus", "confidence": 0.9}'
        fake_response.usage_metadata = fake_usage

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = fake_response

        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        with patch("google.genai.Client", return_value=fake_client):
            r = GeminiReformulator()
            r._call_api("feline diabetes")

        guard = get_budget_guard()
        assert guard.gemini.input_tokens == 350
        assert guard.gemini.output_tokens == 60
        assert guard.gemini.request_count_today == 1

    def test_silent_when_no_usage_metadata(self, monkeypatch):
        """usage_metadata 누락 시 0 token으로 record (production 흐름 보호)."""
        from src.retrieval.query_reformulator import GeminiReformulator

        fake_response = MagicMock(spec=["text"])
        fake_response.text = '{"reformulated": "x", "confidence": 0.5}'

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = fake_response

        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        with patch("google.genai.Client", return_value=fake_client):
            r = GeminiReformulator()
            r._call_api("q")

        guard = get_budget_guard()
        # usage_metadata 누락 → 0 token이지만 호출 1건은 카운트 (RPD 정확성)
        assert guard.gemini.input_tokens == 0
        assert guard.gemini.output_tokens == 0
        assert guard.gemini.request_count_today == 1


class TestPersistenceIntegration:
    """v3.1 R-5: state_path 적용 시 production 호출이 file에 영속화되는지 검증."""

    def test_persistence_accumulates_across_singleton_resets(self, tmp_path, monkeypatch):
        """singleton reset 후 from_env() 재초기화 시 file에서 누적 state 복원."""
        from src.observability.budget_guard import BudgetGuard
        state_path = tmp_path / "budget_state.json"

        # 1차: state_path 환경변수 적용 + singleton 생성 + record
        monkeypatch.setenv("GSD_BUDGET_STATE_PATH", str(state_path))
        reset_budget_guard()
        g1 = get_budget_guard()
        g1.record_gemini(input_tokens=1000, output_tokens=200)
        g1.record_tavily(credits=5)

        assert state_path.exists()

        # 2차: singleton 강제 reset → 새 instance가 file에서 누적 state 복원
        reset_budget_guard()
        g2 = get_budget_guard()
        assert g2 is not g1
        assert g2.gemini.input_tokens == 1000
        assert g2.gemini.output_tokens == 200
        assert g2.tavily.credits_used == 5

        # 3차: 추가 record가 누적되어 file에 반영
        g2.record_gemini(input_tokens=500, output_tokens=100)
        reset_budget_guard()
        g3 = get_budget_guard()
        assert g3.gemini.input_tokens == 1500
        assert g3.gemini.output_tokens == 300
