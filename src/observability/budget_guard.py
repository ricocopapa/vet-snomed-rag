"""Budget guard — Gemini API + Tavily Web Search 사용량 임계 모니터링 (v2.9 R-10 PoC).

per-call token/credit 사용량을 추적하고, Free 한도 또는 PAYG 월간 USD 예산을
초과하기 전 임계 경고(80% / 95%)를 emit한다.

[설계서]   docs/20260427_r10_payg_simulation.md §4
[핸드오프] docs/20260427_v2_9_roadmap_handoff.md §1-2 #3 (R-10)

환경변수 (모두 optional):
    GSD_BUDGET_USD_MONTH       — 월간 USD 캡 (default: None = 비활성)
    GSD_TAVILY_CREDIT_LIMIT    — Tavily 월간 credit 캡 (default: 1000 = Free)
    GSD_GEMINI_RPD_LIMIT       — Gemini 일간 RPD 캡 (default: 500)
    GSD_BUDGET_WARN_AT         — first 경고 임계% (default: 80)
    GSD_BUDGET_CRIT_AT         — critical 경고 임계% (default: 95)

공식 단가 (2026-04-27 검증):
    Gemini 3.1 Flash-Lite Preview — input $0.25/1M, output $1.50/1M
        (출처: https://ai.google.dev/gemini-api/docs/pricing)
    Tavily PAYG — $0.008 / credit, Free tier 1,000 credits/월
        (출처: https://docs.tavily.com/documentation/api-credits)

PoC 단계 — in-memory state only. 영속화 + runtime 통합은 v3.0+ phase.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

GEMINI_3_1_FLASH_LITE_INPUT_PER_M: float = 0.25
GEMINI_3_1_FLASH_LITE_OUTPUT_PER_M: float = 1.50
TAVILY_PAYG_PER_CREDIT: float = 0.008
TAVILY_FREE_CREDITS_PER_MONTH: int = 1000
GEMINI_FREE_RPD: int = 500

DEFAULT_WARN_PCT: int = 80
DEFAULT_CRIT_PCT: int = 95


@dataclass
class GeminiCallStats:
    input_tokens: int = 0
    output_tokens: int = 0
    request_count_today: int = 0
    last_reset_day: str = ""

    def cost_usd(self) -> float:
        return (
            self.input_tokens / 1_000_000 * GEMINI_3_1_FLASH_LITE_INPUT_PER_M
            + self.output_tokens / 1_000_000 * GEMINI_3_1_FLASH_LITE_OUTPUT_PER_M
        )


@dataclass
class TavilyCallStats:
    credits_used: int = 0
    last_reset_month: str = ""

    def cost_usd_payg(self) -> float:
        return self.credits_used * TAVILY_PAYG_PER_CREDIT


@dataclass
class BudgetWarning:
    severity: str  # "warn" | "crit"
    metric: str    # "usd_month" | "tavily_credits" | "gemini_rpd"
    pct_used: float
    current: float
    limit: float
    message: str


class BudgetGuard:
    """월간 USD + Tavily credit + Gemini RPD 임계 모니터링 PoC."""

    def __init__(
        self,
        budget_usd_month: Optional[float] = None,
        tavily_credit_limit: int = TAVILY_FREE_CREDITS_PER_MONTH,
        gemini_rpd_limit: int = GEMINI_FREE_RPD,
        warn_at_pct: int = DEFAULT_WARN_PCT,
        crit_at_pct: int = DEFAULT_CRIT_PCT,
    ) -> None:
        self.budget_usd_month = budget_usd_month
        self.tavily_credit_limit = tavily_credit_limit
        self.gemini_rpd_limit = gemini_rpd_limit
        self.warn_at_pct = warn_at_pct
        self.crit_at_pct = crit_at_pct
        self.gemini = GeminiCallStats()
        self.tavily = TavilyCallStats()

    @classmethod
    def from_env(cls) -> "BudgetGuard":
        return cls(
            budget_usd_month=_parse_float_env("GSD_BUDGET_USD_MONTH"),
            tavily_credit_limit=_parse_int_env(
                "GSD_TAVILY_CREDIT_LIMIT", TAVILY_FREE_CREDITS_PER_MONTH
            ),
            gemini_rpd_limit=_parse_int_env("GSD_GEMINI_RPD_LIMIT", GEMINI_FREE_RPD),
            warn_at_pct=_parse_int_env("GSD_BUDGET_WARN_AT", DEFAULT_WARN_PCT),
            crit_at_pct=_parse_int_env("GSD_BUDGET_CRIT_AT", DEFAULT_CRIT_PCT),
        )

    def record_gemini(
        self,
        input_tokens: int,
        output_tokens: int,
        *,
        now: Optional[datetime] = None,
    ) -> None:
        if input_tokens < 0 or output_tokens < 0:
            raise ValueError("token counts must be non-negative")
        now = now or datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        if self.gemini.last_reset_day != today:
            self.gemini.request_count_today = 0
            self.gemini.last_reset_day = today
        self.gemini.input_tokens += input_tokens
        self.gemini.output_tokens += output_tokens
        self.gemini.request_count_today += 1

    def record_tavily(
        self,
        credits: int,
        *,
        now: Optional[datetime] = None,
    ) -> None:
        if credits < 0:
            raise ValueError("credits must be non-negative")
        now = now or datetime.now(timezone.utc)
        month = now.strftime("%Y-%m")
        if self.tavily.last_reset_month != month:
            self.tavily.credits_used = 0
            self.tavily.last_reset_month = month
        self.tavily.credits_used += credits

    def record_tavily_search(
        self,
        depth: str = "basic",
        *,
        now: Optional[datetime] = None,
    ) -> None:
        """Tavily Search 호출 1건 기록 (basic=1 credit, advanced=2 credits)."""
        credits = 2 if depth == "advanced" else 1
        self.record_tavily(credits, now=now)

    def total_usd(self) -> float:
        return self.gemini.cost_usd() + self.tavily.cost_usd_payg()

    def check(self) -> list[BudgetWarning]:
        warnings: list[BudgetWarning] = []

        if self.budget_usd_month is not None and self.budget_usd_month > 0:
            usd = self.total_usd()
            pct = usd / self.budget_usd_month * 100
            w = self._classify(
                pct, "usd_month", usd, self.budget_usd_month,
                f"USD 월간 예산 {pct:.1f}% 사용 (${usd:.4f}/${self.budget_usd_month:.2f})",
            )
            if w is not None:
                warnings.append(w)

        if self.tavily_credit_limit > 0:
            credits = self.tavily.credits_used
            pct = credits / self.tavily_credit_limit * 100
            w = self._classify(
                pct, "tavily_credits", credits, self.tavily_credit_limit,
                f"Tavily credits {pct:.1f}% 사용 ({credits}/{self.tavily_credit_limit})",
            )
            if w is not None:
                warnings.append(w)

        if self.gemini_rpd_limit > 0:
            rpd = self.gemini.request_count_today
            pct = rpd / self.gemini_rpd_limit * 100
            w = self._classify(
                pct, "gemini_rpd", rpd, self.gemini_rpd_limit,
                f"Gemini RPD {pct:.1f}% 사용 ({rpd}/{self.gemini_rpd_limit})",
            )
            if w is not None:
                warnings.append(w)

        return warnings

    def _classify(
        self,
        pct: float,
        metric: str,
        current: float,
        limit: float,
        message: str,
    ) -> Optional[BudgetWarning]:
        if pct >= self.crit_at_pct:
            return BudgetWarning("crit", metric, pct, current, limit, message)
        if pct >= self.warn_at_pct:
            return BudgetWarning("warn", metric, pct, current, limit, message)
        return None

    def emit_warnings(self) -> list[BudgetWarning]:
        warnings = self.check()
        for w in warnings:
            level = logging.WARNING if w.severity == "warn" else logging.ERROR
            logger.log(level, "[BudgetGuard][%s] %s", w.severity.upper(), w.message)
        return warnings


def _parse_float_env(name: str) -> Optional[float]:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def _parse_int_env(name: str, default: int) -> int:
    v = os.getenv(name)
    if v is None or v.strip() == "":
        return default
    try:
        return int(v)
    except ValueError:
        return default


__all__ = [
    "BudgetGuard",
    "BudgetWarning",
    "GeminiCallStats",
    "TavilyCallStats",
    "GEMINI_3_1_FLASH_LITE_INPUT_PER_M",
    "GEMINI_3_1_FLASH_LITE_OUTPUT_PER_M",
    "TAVILY_PAYG_PER_CREDIT",
    "TAVILY_FREE_CREDITS_PER_MONTH",
    "GEMINI_FREE_RPD",
]
