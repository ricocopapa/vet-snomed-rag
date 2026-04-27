"""tests/test_budget_guard.py — v2.9 R-10 BudgetGuard 단위 테스트.

[설계서] docs/20260427_r10_payg_simulation.md §4
[모듈]   src/observability/budget_guard.py

검증 항목:
1. Gemini cost 계산 정확성 (공식 단가 검증)
2. Tavily search basic/advanced credit 카운트
3. WARN 임계 (80%) — list 반환
4. CRIT 임계 (95%) — severity=crit 반환
5. 임계 미달 — 빈 list 반환
6. budget_usd_month=None — USD 경고 비활성
7. 일별 RPD 리셋 (next day → counter=1)
8. 월별 credit 리셋 (next month → counter reset)
9. from_env() — 기본값 적용 (env 미설정)
10. from_env() — 환경변수 파싱
11. emit_warnings() — logger 호출 검증
12. 음수 입력 ValueError
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.observability.budget_guard import (  # noqa: E402
    BudgetGuard,
    BudgetWarning,
    GEMINI_3_1_FLASH_LITE_INPUT_PER_M,
    GEMINI_3_1_FLASH_LITE_OUTPUT_PER_M,
    TAVILY_PAYG_PER_CREDIT,
    TAVILY_FREE_CREDITS_PER_MONTH,
    GEMINI_FREE_RPD,
)


class TestGeminiCost:
    def test_zero_state(self):
        g = BudgetGuard()
        assert g.gemini.cost_usd() == 0.0

    def test_input_only_1m_tokens(self):
        g = BudgetGuard()
        g.record_gemini(input_tokens=1_000_000, output_tokens=0)
        assert g.gemini.cost_usd() == pytest.approx(GEMINI_3_1_FLASH_LITE_INPUT_PER_M)

    def test_output_only_1m_tokens(self):
        g = BudgetGuard()
        g.record_gemini(input_tokens=0, output_tokens=1_000_000)
        assert g.gemini.cost_usd() == pytest.approx(GEMINI_3_1_FLASH_LITE_OUTPUT_PER_M)

    def test_realistic_call(self):
        # 실측 cached 평균: $0.000270/call
        g = BudgetGuard()
        g.record_gemini(input_tokens=600, output_tokens=80)
        # 600/1M*0.25 + 80/1M*1.50 = 0.00015 + 0.00012 = 0.00027
        assert g.gemini.cost_usd() == pytest.approx(0.00027, abs=1e-7)


class TestTavilyCredits:
    def test_zero_state(self):
        g = BudgetGuard()
        assert g.tavily.cost_usd_payg() == 0.0

    def test_search_basic_costs_1_credit(self):
        g = BudgetGuard()
        g.record_tavily_search(depth="basic")
        assert g.tavily.credits_used == 1

    def test_search_advanced_costs_2_credits(self):
        g = BudgetGuard()
        g.record_tavily_search(depth="advanced")
        assert g.tavily.credits_used == 2

    def test_payg_cost_per_credit(self):
        g = BudgetGuard()
        g.record_tavily(credits=10)
        assert g.tavily.cost_usd_payg() == pytest.approx(10 * TAVILY_PAYG_PER_CREDIT)


class TestThresholds:
    def test_warn_at_80_pct_usd(self):
        g = BudgetGuard(budget_usd_month=1.0, warn_at_pct=80, crit_at_pct=95)
        # input 3.2M tokens × $0.25/1M = $0.80 = 80%
        g.record_gemini(input_tokens=3_200_000, output_tokens=0)
        ws = g.check()
        usd_w = [w for w in ws if w.metric == "usd_month"]
        assert len(usd_w) == 1
        assert usd_w[0].severity == "warn"

    def test_crit_at_95_pct_usd(self):
        g = BudgetGuard(budget_usd_month=1.0, warn_at_pct=80, crit_at_pct=95)
        g.record_gemini(input_tokens=3_800_000, output_tokens=0)  # $0.95 = 95%
        ws = g.check()
        usd_w = [w for w in ws if w.metric == "usd_month"]
        assert len(usd_w) == 1
        assert usd_w[0].severity == "crit"

    def test_below_warn_no_alert(self):
        g = BudgetGuard(budget_usd_month=1.0)
        g.record_gemini(input_tokens=1_000_000, output_tokens=0)  # $0.25 = 25%
        ws = g.check()
        assert [w for w in ws if w.metric == "usd_month"] == []

    def test_no_budget_no_usd_alert(self):
        g = BudgetGuard(budget_usd_month=None)
        g.record_gemini(input_tokens=10_000_000, output_tokens=10_000_000)
        ws = g.check()
        assert [w for w in ws if w.metric == "usd_month"] == []

    def test_tavily_credit_warn(self):
        g = BudgetGuard(tavily_credit_limit=100, warn_at_pct=80)
        g.record_tavily(credits=80)
        ws = g.check()
        cred_w = [w for w in ws if w.metric == "tavily_credits"]
        assert len(cred_w) == 1
        assert cred_w[0].severity == "warn"

    def test_gemini_rpd_crit(self):
        g = BudgetGuard(gemini_rpd_limit=10, crit_at_pct=95)
        for _ in range(10):
            g.record_gemini(input_tokens=1, output_tokens=1)
        ws = g.check()
        rpd_w = [w for w in ws if w.metric == "gemini_rpd"]
        assert len(rpd_w) == 1
        assert rpd_w[0].severity == "crit"


class TestPeriodReset:
    def test_rpd_resets_next_day(self):
        g = BudgetGuard()
        d1 = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        d2 = datetime(2026, 4, 28, 0, 1, tzinfo=timezone.utc)
        g.record_gemini(input_tokens=10, output_tokens=10, now=d1)
        g.record_gemini(input_tokens=10, output_tokens=10, now=d1)
        assert g.gemini.request_count_today == 2
        g.record_gemini(input_tokens=10, output_tokens=10, now=d2)
        assert g.gemini.request_count_today == 1

    def test_credits_reset_next_month(self):
        g = BudgetGuard()
        m1 = datetime(2026, 4, 30, 23, 59, tzinfo=timezone.utc)
        m2 = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
        g.record_tavily(credits=500, now=m1)
        assert g.tavily.credits_used == 500
        g.record_tavily(credits=2, now=m2)
        assert g.tavily.credits_used == 2


class TestFromEnv:
    def test_defaults_when_unset(self):
        with patch.dict(os.environ, {}, clear=False):
            for k in [
                "GSD_BUDGET_USD_MONTH",
                "GSD_TAVILY_CREDIT_LIMIT",
                "GSD_GEMINI_RPD_LIMIT",
                "GSD_BUDGET_WARN_AT",
                "GSD_BUDGET_CRIT_AT",
            ]:
                os.environ.pop(k, None)
            g = BudgetGuard.from_env()
            assert g.budget_usd_month is None
            assert g.tavily_credit_limit == TAVILY_FREE_CREDITS_PER_MONTH
            assert g.gemini_rpd_limit == GEMINI_FREE_RPD
            assert g.warn_at_pct == 80
            assert g.crit_at_pct == 95

    def test_parses_env(self):
        env = {
            "GSD_BUDGET_USD_MONTH": "5.50",
            "GSD_TAVILY_CREDIT_LIMIT": "4000",
            "GSD_GEMINI_RPD_LIMIT": "1000",
            "GSD_BUDGET_WARN_AT": "70",
            "GSD_BUDGET_CRIT_AT": "90",
        }
        with patch.dict(os.environ, env, clear=False):
            g = BudgetGuard.from_env()
            assert g.budget_usd_month == 5.5
            assert g.tavily_credit_limit == 4000
            assert g.gemini_rpd_limit == 1000
            assert g.warn_at_pct == 70
            assert g.crit_at_pct == 90

    def test_invalid_env_falls_back_to_default(self):
        env = {
            "GSD_BUDGET_USD_MONTH": "not-a-number",
            "GSD_TAVILY_CREDIT_LIMIT": "abc",
        }
        with patch.dict(os.environ, env, clear=False):
            g = BudgetGuard.from_env()
            assert g.budget_usd_month is None
            assert g.tavily_credit_limit == TAVILY_FREE_CREDITS_PER_MONTH


class TestEmitWarnings:
    def test_emits_via_logger(self, caplog):
        g = BudgetGuard(budget_usd_month=1.0, tavily_credit_limit=10)
        g.record_gemini(input_tokens=3_900_000, output_tokens=0)  # $0.975 = 97.5% crit
        g.record_tavily(credits=8)  # 80% warn
        with caplog.at_level(logging.WARNING, logger="src.observability.budget_guard"):
            ws = g.emit_warnings()
        assert len(ws) == 2
        assert any("USD" in r.message for r in caplog.records)
        assert any("Tavily" in r.message for r in caplog.records)

    def test_no_warnings_emits_nothing(self, caplog):
        g = BudgetGuard(budget_usd_month=1000.0)
        g.record_gemini(input_tokens=10, output_tokens=10)
        with caplog.at_level(logging.WARNING):
            ws = g.emit_warnings()
        assert ws == []


class TestValidation:
    def test_negative_tokens_raises(self):
        g = BudgetGuard()
        with pytest.raises(ValueError):
            g.record_gemini(input_tokens=-1, output_tokens=0)
        with pytest.raises(ValueError):
            g.record_gemini(input_tokens=0, output_tokens=-1)

    def test_negative_credits_raises(self):
        g = BudgetGuard()
        with pytest.raises(ValueError):
            g.record_tavily(credits=-5)


class TestTotalUsd:
    def test_combines_gemini_and_tavily(self):
        g = BudgetGuard()
        g.record_gemini(input_tokens=1_000_000, output_tokens=0)  # $0.25
        g.record_tavily(credits=10)  # $0.08
        assert g.total_usd() == pytest.approx(0.25 + 10 * TAVILY_PAYG_PER_CREDIT)


# ──────────────────────────────────────────────────────────────────────────────
# v3.1 R-5 — JSON 영속화 (in-memory→file) 신규 테스트 T1~T10
# ──────────────────────────────────────────────────────────────────────────────

import json


class TestPersistence:
    def test_T1_save_creates_file_with_state(self, tmp_path):
        """T1: record 후 file 존재 + JSON parse OK + 기록 값 반영."""
        state_path = tmp_path / "budget_state.json"
        g = BudgetGuard(state_path=state_path)
        g.record_gemini(input_tokens=1000, output_tokens=200)
        g.record_tavily(credits=5)
        assert state_path.exists()
        with state_path.open() as f:
            data = json.load(f)
        assert data["gemini"]["input_tokens"] == 1000
        assert data["gemini"]["output_tokens"] == 200
        assert data["tavily"]["credits_used"] == 5

    def test_T2_load_restores_state_after_init(self, tmp_path):
        """T2: save → 새 instance load → 동일 state."""
        state_path = tmp_path / "budget_state.json"
        g1 = BudgetGuard(state_path=state_path)
        g1.record_gemini(input_tokens=600, output_tokens=80)
        g1.record_tavily_search(depth="advanced")
        g2 = BudgetGuard(state_path=state_path)
        assert g2.gemini.input_tokens == 600
        assert g2.gemini.output_tokens == 80
        assert g2.tavily.credits_used == 2
        assert g2.gemini.cost_usd() == pytest.approx(g1.gemini.cost_usd())

    def test_T3_record_gemini_auto_saves(self, tmp_path):
        """T3: record_gemini 호출 후 file 즉시 갱신."""
        state_path = tmp_path / "budget_state.json"
        g = BudgetGuard(state_path=state_path)
        g.record_gemini(input_tokens=100, output_tokens=10)
        with state_path.open() as f:
            data = json.load(f)
        assert data["gemini"]["input_tokens"] == 100
        # 누적 갱신 확인
        g.record_gemini(input_tokens=50, output_tokens=5)
        with state_path.open() as f:
            data = json.load(f)
        assert data["gemini"]["input_tokens"] == 150

    def test_T4_record_tavily_auto_saves(self, tmp_path):
        """T4: record_tavily 호출 후 file 즉시 갱신 + record_tavily_search 동일."""
        state_path = tmp_path / "budget_state.json"
        g = BudgetGuard(state_path=state_path)
        g.record_tavily(credits=3)
        with state_path.open() as f:
            data = json.load(f)
        assert data["tavily"]["credits_used"] == 3
        g.record_tavily_search(depth="basic")
        with state_path.open() as f:
            data = json.load(f)
        assert data["tavily"]["credits_used"] == 4

    def test_T5_no_state_path_no_file_io(self, tmp_path):
        """T5: state_path=None → 기존 동작 보존 (file 생성 0, 회귀 입증)."""
        g = BudgetGuard()  # state_path 미지정
        g.record_gemini(input_tokens=1000, output_tokens=100)
        g.record_tavily(credits=10)
        assert g.gemini.input_tokens == 1000
        assert g.tavily.credits_used == 10
        # tmp_path 안에 어떤 file도 생성되지 않아야 함
        assert list(tmp_path.iterdir()) == []

    def test_T6_atomic_write_preserves_existing_on_error(self, tmp_path, monkeypatch):
        """T6: write 중 실패 시 기존 file 보존 (atomic write rename)."""
        state_path = tmp_path / "budget_state.json"
        g = BudgetGuard(state_path=state_path)
        g.record_gemini(input_tokens=500, output_tokens=50)
        original_content = state_path.read_text()

        # os.replace를 강제 실패시켜 atomic rename 단계에서 fail 유도
        import os as _os
        original_replace = _os.replace

        def failing_replace(src, dst):
            _os.unlink(src)  # tmp 정리
            raise OSError("simulated rename failure")

        monkeypatch.setattr(_os, "replace", failing_replace)
        with pytest.raises(OSError):
            g.record_gemini(input_tokens=999, output_tokens=999)
        # 기존 file 내용 보존
        assert state_path.read_text() == original_content

    def test_T7_load_missing_file_initializes_empty(self, tmp_path):
        """T7: file 없음 → empty state로 정상 시작."""
        state_path = tmp_path / "nonexistent.json"
        assert not state_path.exists()
        g = BudgetGuard(state_path=state_path)
        assert g.gemini.input_tokens == 0
        assert g.gemini.output_tokens == 0
        assert g.gemini.request_count_today == 0
        assert g.gemini.last_reset_day == ""
        assert g.tavily.credits_used == 0
        assert g.tavily.last_reset_month == ""

    def test_T8_load_corrupt_json_falls_back_to_empty(self, tmp_path, caplog):
        """T8: corrupt JSON → empty state + logger warning."""
        state_path = tmp_path / "budget_state.json"
        state_path.write_text("{not valid json")
        with caplog.at_level(logging.WARNING, logger="src.observability.budget_guard"):
            g = BudgetGuard(state_path=state_path)
        assert g.gemini.input_tokens == 0
        assert g.tavily.credits_used == 0
        assert any("budget_state" in r.message or "corrupt" in r.message.lower()
                   for r in caplog.records)

    def test_T9_period_reset_persisted(self, tmp_path):
        """T9: 일별/월별 reset이 file에 반영."""
        state_path = tmp_path / "budget_state.json"
        g = BudgetGuard(state_path=state_path)
        d1 = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        d2 = datetime(2026, 4, 28, 0, 1, tzinfo=timezone.utc)
        g.record_gemini(input_tokens=10, output_tokens=10, now=d1)
        g.record_gemini(input_tokens=10, output_tokens=10, now=d1)
        with state_path.open() as f:
            data = json.load(f)
        assert data["gemini"]["request_count_today"] == 2
        assert data["gemini"]["last_reset_day"] == "2026-04-27"
        # 다음 날 reset
        g.record_gemini(input_tokens=10, output_tokens=10, now=d2)
        with state_path.open() as f:
            data = json.load(f)
        assert data["gemini"]["request_count_today"] == 1
        assert data["gemini"]["last_reset_day"] == "2026-04-28"

    def test_T10_load_preserves_period_state(self, tmp_path):
        """T10: last_reset_day / last_reset_month round-trip 보존."""
        state_path = tmp_path / "budget_state.json"
        g1 = BudgetGuard(state_path=state_path)
        d = datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
        m = datetime(2026, 4, 30, 23, 59, tzinfo=timezone.utc)
        g1.record_gemini(input_tokens=10, output_tokens=10, now=d)
        g1.record_tavily(credits=100, now=m)
        # 새 instance — period state 복원
        g2 = BudgetGuard(state_path=state_path)
        assert g2.gemini.last_reset_day == "2026-04-27"
        assert g2.tavily.last_reset_month == "2026-04"
        assert g2.gemini.request_count_today == 1
        assert g2.tavily.credits_used == 100
        # 같은 날 추가 record → 누적 (reset 미발동)
        g2.record_gemini(input_tokens=5, output_tokens=5, now=d)
        assert g2.gemini.request_count_today == 2
