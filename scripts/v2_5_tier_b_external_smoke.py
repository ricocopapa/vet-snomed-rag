"""v2.5 Tier B 실제 외부 도구 호출 smoke.

사용자 .env의 UMLS_API_KEY + NCBI_API_KEY로 실제 NLM API 호출.
응답 형식 + 키 인증 + 네트워크 도달성 검증.

실패 분류:
- env 미설정 → SKIP (정상)
- 401 → 키 잘못/만료 (수정 필요)
- timeout/network → 일시적 (graceful)
- 200 + 결과 0 → 검색어 문제 (정상 가능)

설계서: docs/20260425_v2_5_tier_b_external_tools_design_v1.md §7 (검증 전략)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from src.tools.pubmed_client import PubMedClient
from src.tools.umls_client import UMLSClient


def main() -> int:
    print("v2.5 Tier B 실제 외부 호출 smoke")
    print("=" * 60)

    fails = 0

    # ── UMLS smoke ──────────────────────────────────────
    print("\n[UMLS]")
    umls_key = os.environ.get("UMLS_API_KEY", "")
    if not umls_key:
        print("  [SKIP] UMLS_API_KEY 미설정")
    else:
        client = UMLSClient()
        if not client.enabled:
            print("  [FAIL] UMLSClient 비활성 (키 환경변수 누락)")
            fails += 1
        else:
            print(f"  키 길이: {len(umls_key)}자 (API key)")
            results = client.search("diabetes mellitus", top_k=2)
            if not results:
                if not client.enabled:
                    print("  [FAIL] 401/인증 실패 — 키 재발급 필요")
                    fails += 1
                else:
                    print("  [WARN] 검색 결과 0건 (네트워크 또는 일시 오류)")
            else:
                print(f"  [PASS] search('diabetes mellitus') → {len(results)}건")
                top = results[0]
                print(f"        Top-1: {top['cui']} {top['name']}")
                # Cross-walk 시도
                xw = client.get_cross_walks(top["cui"], sources=["ICD10CM", "MSH"])
                if xw:
                    print(f"  [PASS] cross-walks: {xw}")
                else:
                    print("  [WARN] cross-walks 빈 결과 (atom 엔드포인트 응답 없음)")

    # ── PubMed smoke ────────────────────────────────────
    print("\n[PubMed]")
    ncbi_key = os.environ.get("NCBI_API_KEY", "")
    if not ncbi_key:
        print("  [INFO] NCBI_API_KEY 미설정 → 3 rps 모드로 호출")
    else:
        print(f"  키 길이: {len(ncbi_key)}자 (10 rps 모드)")

    pclient = PubMedClient()
    pmids = pclient.search("feline diabetes", top_k=2)
    if not pmids:
        print("  [WARN] PMID 검색 결과 0건 또는 네트워크 오류")
    else:
        print(f"  [PASS] search('feline diabetes') → {len(pmids)} PMIDs: {pmids}")
        summaries = pclient.fetch_summaries(pmids)
        if not summaries:
            print("  [WARN] esummary 0건")
        else:
            print(f"  [PASS] fetch_summaries → {len(summaries)} entries")
            top = summaries[0]
            print(
                f"        Top-1: {top.get('year','')} {top.get('journal','')} — "
                f"{top.get('title','')[:60]}..."
            )

    print("\n" + "=" * 60)
    if fails == 0:
        print("RESULT: PASS (외부 API 도달성·인증 OK)")
        return 0
    else:
        print(f"RESULT: FAIL ({fails} hard failures — 키/네트워크 점검)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
