"""
eval_v22_stage1_real_api.py
===========================
v2.2 Stage 1 — 실 Gemini API E2E smoke test.

목적:
  1. dry-run mock 한계(01/02 `VITAL_SIGNS` 폴백)가 실 API 경로에서 해소되는지 확인.
  2. PDF → pdf_reader → ClinicalEncoder(Gemini) → SOAP + SNOMED 파이프라인 통과.
  3. 3 PDF × 실측 latency 기록.

주의:
  - GOOGLE_API_KEY 필요 (외부 API 호출, 비용/quota 소모).
  - 결과는 benchmark/v2.2_pdf_stage1_real_api.json 및 …real_api.md 에 저장.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.pdf_reader import read_pdf
from src.pipeline.e2e import ClinicalEncoder, ClinicalEncoderConfig

SAMPLES = sorted((PROJECT_ROOT / "data" / "synthetic_scenarios_pdf").glob("*.pdf"))
OUT_JSON = PROJECT_ROOT / "benchmark" / "v2.2_pdf_stage1_real_api.json"
OUT_MD   = PROJECT_ROOT / "benchmark" / "v2.2_pdf_stage1_real_api.md"

EXPECTED_DOMAIN = {
    "hyangnam_anon_01_ophthalmology.pdf":      "OPHTHALMOLOGY",
    "hyangnam_anon_02_dermatology.pdf":         "DERMATOLOGY",
    "hyangnam_anon_03_gastrointestinal.pdf":    "GASTROINTESTINAL",
}


def main() -> int:
    if not os.environ.get("GOOGLE_API_KEY"):
        # .env 로드 재시도
        try:
            from dotenv import load_dotenv
            load_dotenv(PROJECT_ROOT / ".env")
        except ImportError:
            pass
    if not os.environ.get("GOOGLE_API_KEY"):
        print("ERROR: GOOGLE_API_KEY not set")
        return 1

    encoder = ClinicalEncoder(config=ClinicalEncoderConfig(
        dry_run=False,
        reformulator_backend="gemini",
        enable_rerank=False,
    ))

    results = []
    for pdf_path in SAMPLES:
        print(f"\n== {pdf_path.name} ==")
        t0 = time.perf_counter()
        info = read_pdf(pdf_path)
        t_pdf = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        try:
            record = encoder.encode(info["text"], input_type="text")
            err = None
        except Exception as e:
            record = None
            err = str(e)[:500]
        t_enc = (time.perf_counter() - t1) * 1000

        domains = record.get("domains", []) if record else []
        fields = record.get("fields", []) if record else []
        snomed_tagged = [
            t for t in (record.get("snomed_tagging", []) if record else [])
            if t.get("concept_id") != "UNMAPPED"
        ]
        soap = record.get("soap", {}) if record else {}
        soap_nonempty = sum(
            1 for k in ("subjective", "objective", "assessment", "plan") if soap.get(k)
        )
        expected = EXPECTED_DOMAIN[pdf_path.name]
        domain_hit = expected in domains

        result = {
            "pdf": pdf_path.name,
            "pages": info["pages"],
            "chars": len(info["text"]),
            "pdf_latency_ms": round(t_pdf, 1),
            "encode_latency_ms": round(t_enc, 1),
            "expected_domain": expected,
            "detected_domains": domains,
            "domain_hit": domain_hit,
            "fields_count": len(fields),
            "snomed_mapped": len(snomed_tagged),
            "soap_nonempty": soap_nonempty,
            "errors": record.get("errors", []) if record else [err],
        }
        results.append(result)
        print(
            f"  domain={domains} (hit={domain_hit}) fields={len(fields)} "
            f"snomed={len(snomed_tagged)} soap={soap_nonempty}/4 lat={t_enc:.0f}ms"
        )

    # dump
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "backend": "gemini",
        "model": "gemini-3.1-flash-lite-preview",
        "results": results,
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nJSON: {OUT_JSON}")

    # markdown
    lines = [
        "# v2.2 Stage 1 — 실 Gemini API E2E Smoke Test",
        "",
        f"- timestamp (UTC): `{summary['timestamp']}`",
        f"- backend: `{summary['backend']}` / model: `{summary['model']}`",
        "",
        "## Results",
        "",
        "| PDF | Expected | Detected | hit | fields | SNOMED | SOAP | encode ms |",
        "|---|---|---|---|---:|---:|---:|---:|",
    ]
    for r in results:
        lines.append(
            f"| {r['pdf']} | {r['expected_domain']} | {','.join(r['detected_domains']) or '∅'} | "
            f"{'✅' if r['domain_hit'] else '❌'} | {r['fields_count']} | {r['snomed_mapped']} | "
            f"{r['soap_nonempty']}/4 | {r['encode_latency_ms']:.0f} |"
        )

    total_hits = sum(1 for r in results if r["domain_hit"])
    lines += [
        "",
        f"- 도메인 hit: **{total_hits}/{len(results)}**",
        f"- SNOMED 매핑 합계: **{sum(r['snomed_mapped'] for r in results)}**",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"MD:   {OUT_MD}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
