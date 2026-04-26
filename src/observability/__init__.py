"""src/observability — v2.9+ 운영 견고성 모듈.

[모듈]
- budget_guard: Gemini API + Tavily Web 사용량 모니터링 + 임계 알림 (v2.9 R-10)

[싱글톤]
get_budget_guard() — runtime 통합 사용처(synthesizer / web_search_client /
agentic_pipeline)에서 공통 인스턴스로 사용. 테스트는 reset_budget_guard()로 격리.
"""
from __future__ import annotations

from typing import Optional

from .budget_guard import BudgetGuard, BudgetWarning

_GUARD: Optional[BudgetGuard] = None


def get_budget_guard() -> BudgetGuard:
    """Lazy 싱글톤 — 환경변수 기반 초기화."""
    global _GUARD
    if _GUARD is None:
        _GUARD = BudgetGuard.from_env()
    return _GUARD


def reset_budget_guard() -> None:
    """테스트 격리용 — 다음 get_budget_guard() 호출 시 재초기화."""
    global _GUARD
    _GUARD = None


__all__ = ["BudgetGuard", "BudgetWarning", "get_budget_guard", "reset_budget_guard"]
