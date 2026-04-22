"""
run_gemini_smoke.py
===================
vet-snomed-rag v2.0 — B2 Gemini 2.5 Flash 실 API 3샘플 smoke 테스트

실행 방법:
  cd vet-snomed-rag
  venv/bin/python3 benchmark/run_gemini_smoke.py

사전 조건:
  - .env 파일에 GOOGLE_API_KEY=AIza... 설정
  - pip install google-genai (venv에 이미 설치됨)

성공 기준:
  - 도메인 탐지 3/3 정확 (OPH, VITAL_SIGNS, ORTHOPEDICS)
  - 핵심 필드 추출 성공
  - 비용 1호출 ≤ $0.0002
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .env 로드
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    print("[.env 로드 완료]")
except ImportError:
    print("[경고] python-dotenv 미설치 — 환경변수 직접 설정 필요")

from src.pipeline.soap_extractor import SOAPExtractor

SCHEMA_PATH = PROJECT_ROOT / "data" / "field_schema_v26.json"

# ── 3샘플 정의 ────────────────────────────────────────────────────────────
SMOKE_SAMPLES = [
    {
        "name": "안과 — 고안압 녹내장",
        "text": "안압이 오른쪽 28, 왼쪽 14로 측정됐습니다. 우안 고안압 녹내장 약물 시작",
        "expected_domain": "OPHTHALMOLOGY",
        "expected_fields": ["OPH_IOP_OD"],
        "expected_soap_section": "O",
    },
    {
        "name": "내과 — 활력징후",
        "text": "체온 38.5도 심박수 120회 점막 핑크 탈수 5%",
        "expected_domain": "VITAL_SIGNS",
        "expected_fields": ["GP_RECTAL_TEMP_VALUE", "GP_HR_VALUE"],
        "expected_soap_section": "O",
    },
    {
        "name": "정형외과 — 파행 + 슬개골 탈구",
        "text": "오른쪽 뒷다리 파행 3급, 슬개골 내측 탈구 grade 2",
        "expected_domain": "ORTHOPEDICS",
        "expected_fields": ["ORT_LAMENESS_GRADE_CD", "ORT_MPL_GRADE_CD"],
        "expected_soap_section": "O",
    },
]


def run_smoke() -> None:
    print("\n" + "=" * 70)
    print("vet-snomed-rag v2.0 B2 — Gemini 2.5 Flash 실 API Smoke 테스트")
    print("=" * 70)

    # Extractor 초기화
    try:
        import os
        MODEL_OVERRIDE = os.environ.get("GEMINI_MODEL_OVERRIDE", "gemini-2.5-flash")
        ext = SOAPExtractor(
            field_schema_path=SCHEMA_PATH,
            llm_backend="gemini",
            gemini_model=MODEL_OVERRIDE,
            dry_run=False,
        )
        print(f"[초기화 완료] 백엔드: gemini | 모델: {ext.gemini_model}")
    except EnvironmentError as e:
        print(f"[FAIL] 초기화 실패: {e}")
        sys.exit(1)

    results = []
    pass_count = 0
    total_cost = 0.0

    for i, sample in enumerate(SMOKE_SAMPLES, 1):
        name = sample["name"]
        text = sample["text"]
        expected_domain = sample["expected_domain"]
        expected_fields = sample["expected_fields"]

        print(f"\n[{i}/3] {name}")
        print(f"  입력: {text}")
        print("-" * 60)

        try:
            result = ext.extract(text, encounter_id=f"SMOKE-{i:02d}")
        except Exception as e:
            print(f"  [FAIL] extract() 예외: {e}")
            results.append({"name": name, "status": "FAIL", "error": str(e)})
            continue

        meta = result.get("llm_metadata", {})
        cost = meta.get("total_cost_usd", 0.0)
        latency = result["latency_ms"]["total"]
        domains = result["domains"]
        fields = result["fields"]
        field_codes = [f["field_code"] for f in fields]

        total_cost += cost

        # ── 성공 기준 체크 ──────────────────────────────────────
        domain_ok = expected_domain in domains
        fields_ok = all(fc in field_codes for fc in expected_fields)
        cost_ok = cost <= 0.0002

        # cache hit 확인
        cache_hits = {}
        for step_name, step_meta in meta.get("step_details", {}).items():
            cached = step_meta.get("tokens_cached", 0)
            if cached:
                cache_hits[step_name] = cached

        status = "PASS" if (domain_ok and fields_ok and cost_ok) else "WARN"
        if domain_ok and fields_ok:
            pass_count += 1

        print(f"  → 도메인: {domains} [{'OK' if domain_ok else 'FAIL'}]")
        print(f"  → 필드: {field_codes}")
        print(f"  → 기대 필드: {expected_fields} [{'OK' if fields_ok else 'FAIL'}]")
        print(f"  → SOAP.O: {result['soap'].get('objective', 'None')}")
        print(f"  → Cost: ${cost:.6f} [{'OK' if cost_ok else 'OVER $0.0002'}]")
        print(f"  → Latency: {latency:.0f}ms")
        if cache_hits:
            print(f"  → Cache Hit: {cache_hits}")
        print(f"  → [{status}]")

        results.append({
            "name": name,
            "status": status,
            "domain_ok": domain_ok,
            "fields_ok": fields_ok,
            "cost_ok": cost_ok,
            "cost_usd": cost,
            "latency_ms": latency,
            "domains": domains,
            "field_codes": field_codes,
            "cache_hits": cache_hits,
        })

    # ── 최종 요약 ──────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("SMOKE 최종 결과 요약")
    print("=" * 70)
    print(f"도메인 탐지: {pass_count}/3 정확")
    print(f"총 비용: ${total_cost:.6f} (평균 ${total_cost/3:.6f}/호출)")
    print()
    for r in results:
        st = r.get("status", "FAIL")
        print(f"  [{st:4s}] {r['name']}")
        if st != "PASS":
            for key in ("domain_ok", "fields_ok", "cost_ok"):
                if not r.get(key, True):
                    print(f"         → {key} FAIL")

    overall = "PASS" if pass_count == 3 else "PARTIAL"
    print(f"\n최종 판정: {overall} ({pass_count}/3)")

    # 결과 JSON 저장
    output_path = Path(__file__).parent / "v2_b2_gemini_smoke_result.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n상세 결과 저장: {output_path}")


if __name__ == "__main__":
    run_smoke()
