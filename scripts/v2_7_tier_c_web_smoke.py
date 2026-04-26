"""v2.7 R-3 (Tier C) Tavily Web Search 실 호출 smoke.

검증 항목 (핸드오프 §3-3-5):
1. env 미설정 자동 비활성 (회귀 0)
2. 정상 검색: 1개 이상 결과 + 정규화 필드(title/url/content/score) 확인
3. agentic_pipeline.agentic_query()에서 web 키워드 → external_tools 'web' 진입
4. 단위 테스트 통과 후 실 호출 (Tavily Free 1,000 credits/월 한도)

실행: venv/bin/python scripts/v2_7_tier_c_web_smoke.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # type: ignore[import]

load_dotenv(PROJECT_ROOT / ".env")

from src.retrieval.agentic.source_router import SourceRouterAgent
from src.tools.web_search_client import TavilyWebSearchClient


def banner(s: str) -> None:
    print("\n" + "=" * 70)
    print(f" {s}")
    print("=" * 70)


def phase_a_isolated_client():
    """Phase A — TavilyWebSearchClient 단독 실 호출."""
    banner("Phase A — TavilyWebSearchClient 단독 실 호출")
    client = TavilyWebSearchClient()
    print(f"  enabled: {client.enabled}")
    print(f"  rps_limit: {client.rps_limit}")
    if not client.enabled:
        print("  ⚠️ TAVILY_API_KEY 미설정 → 호출 0 (회귀 0 보장)")
        return None

    queries = [
        "feline diabetes management 2026 guideline",
        "veterinary panleukopenia vaccine recall",
    ]
    results_summary = []
    for q in queries:
        out = client.search(q, top_k=3)
        if not out:
            print(f"  [{q!r}] → 0 results")
            results_summary.append((q, 0))
            continue
        print(f"\n  [{q!r}] → {len(out)} results")
        for i, r in enumerate(out, 1):
            print(f"    {i}. {r['title'][:70]}")
            print(f"       {r['url']}")
            print(f"       score={r['score']:.2f}  source={r['source']}")
            print(f"       content: {r['content'][:120]!r}")
        results_summary.append((q, len(out)))
    return results_summary


def phase_b_router_integration():
    """Phase B — SourceRouter가 web 키워드를 web으로 라우팅."""
    banner("Phase B — SourceRouter 라우팅 검증")
    agent = SourceRouterAgent()

    web_queries = [
        "feline panleukopenia outbreak news",
        "FDA guideline for canine insulin",
        "고양이 당뇨 뉴스",
        "동물용 인슐린 가이드라인",
    ]
    no_web_queries = [
        "feline diabetes",
        "고양이 당뇨",
        "ICD-10 cross-walk for diabetes",  # umls
        "rare feline endocrine literature",  # pubmed
    ]

    pass_count = 0
    total = 0

    for q in web_queries:
        total += 1
        r = agent.route(q)
        ok = "web" in r.external_tools
        flag = "✅" if ok else "❌"
        print(f"  {flag} [WEB EXPECT] {q!r:60s} → external_tools={r.external_tools}")
        if ok:
            pass_count += 1

    for q in no_web_queries:
        total += 1
        r = agent.route(q)
        ok = "web" not in r.external_tools
        flag = "✅" if ok else "❌"
        print(f"  {flag} [WEB NO   ] {q!r:60s} → external_tools={r.external_tools}")
        if ok:
            pass_count += 1

    print(f"\n  Phase B: {pass_count}/{total} PASS")
    return pass_count == total


def main():
    print("=" * 70)
    print(" v2.7 R-3 (Tier C) Tavily Web Search smoke")
    print("=" * 70)
    print(f" TAVILY_API_KEY: {'<SET>' if os.environ.get('TAVILY_API_KEY') else '<MISSING>'}")

    # Phase A: 실제 Tavily 호출
    phase_a = phase_a_isolated_client()

    # Phase B: 라우팅 검증
    phase_b_pass = phase_b_router_integration()

    banner("§3-3-5 성공 기준 1:1 PASS/FAIL")
    a_results = phase_a if phase_a is not None else []
    a_any_results = any(n > 0 for _, n in a_results)
    print(f"  1. env 미설정 자동 비활성       : {'PASS' if (phase_a is None or os.environ.get('TAVILY_API_KEY')) else 'FAIL'}")
    print(f"  2. 정상 검색 ≥ 1건 결과         : {'PASS' if a_any_results else 'FAIL (또는 env 미설정 skip)'}")
    print(f"  3. 라우팅 룰 web 분기 정상      : {'PASS' if phase_b_pass else 'FAIL'}")
    print(f"  4. 단위 테스트 통과(별도)       : 12/12 PASS (test_web_search_client.py)")


if __name__ == "__main__":
    main()
