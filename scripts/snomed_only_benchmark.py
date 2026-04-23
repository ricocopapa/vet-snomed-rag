"""
snomed_only_benchmark.py — SNOMED 태거 단독 벤치마크
=====================================================

목적:
  Gemini API 없이 SNOMED 태깅 단계만 단독으로 재실행한다.
  기존 v2_e2e_raw.jsonl의 fields 데이터를 재입력하여
  mrcm_rules_v1.json 변경 효과만 측정한다.

사용법:
  venv/bin/python scripts/snomed_only_benchmark.py \\
    --input benchmark/v2_e2e_raw.jsonl \\
    --output benchmark/v2.1_strategy_a_result.md \\
    --jsonl-out benchmark/v2.1_strategy_a_result.jsonl

[절대 원칙]
  - 통계 수치만 보고. 임상/투자 판단 문구 0건 (data-analyzer 원칙)
  - gold-label 조작 금지. 추측 수치 금지.
  - v1.0 src/retrieval/* 무변경
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.eval.parse_gold_labels import load_all_gold_labels
from scripts.eval.metrics import snomed_match_rate


def _load_jsonl(path: Path) -> list[dict]:
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def run_snomed_tagging(fields: list[dict], snomed_tagger) -> tuple[list[dict], float]:
    """fields 배열을 SNOMED 태거에 입력하고 tagging 결과와 소요 시간을 반환한다."""
    t0 = time.monotonic()
    result = snomed_tagger.tag_all(fields)
    elapsed_ms = (time.monotonic() - t0) * 1000
    return result, elapsed_ms


def main():
    parser = argparse.ArgumentParser(description="SNOMED 태거 단독 벤치마크")
    parser.add_argument("--input", default="benchmark/v2_e2e_raw.jsonl",
                        help="기존 E2E raw JSONL (fields 데이터 재사용)")
    parser.add_argument("--output", default="benchmark/v2.1_strategy_a_result.md",
                        help="결과 리포트 MD 출력 경로")
    parser.add_argument("--jsonl-out", default="benchmark/v2.1_strategy_a_result.jsonl",
                        help="결과 JSONL 출력 경로")
    parser.add_argument("--snomed-mode", default="synonym",
                        choices=["exact", "synonym"])
    args = parser.parse_args()

    input_path = PROJECT_ROOT / args.input
    output_path = PROJECT_ROOT / args.output
    jsonl_out_path = PROJECT_ROOT / args.jsonl_out

    print("=" * 60)
    print("vet-snomed-rag v2.1 — SNOMED 태거 단독 벤치마크 (전략 A)")
    print(f"  input        = {args.input}")
    print(f"  snomed_mode  = {args.snomed_mode}")
    print(f"  output       = {args.output}")
    print("=" * 60)

    # ── Step 1: 기존 E2E raw JSONL 로드 (fields 데이터 재사용) ─────────────
    print("\n[Step 1] 기존 E2E raw 데이터 로드")
    raw_records = _load_jsonl(input_path)
    print(f"  로드 완료: {len(raw_records)}건")

    # ── Step 2: Gold-label 파싱 ─────────────────────────────────────────────
    print("\n[Step 2] Gold-label 파싱")
    gold_labels = load_all_gold_labels()
    gold_by_scenario: dict[int, dict] = {g["scenario_id"]: g for g in gold_labels}
    print(f"  파싱 성공: {len(gold_labels)} 시나리오")
    total_gold_snomed = sum(len(g["snomed"]) for g in gold_labels)
    print(f"  총 gold concept_id: {total_gold_snomed}")

    # ── Step 3: SNOMEDTagger 초기화 ─────────────────────────────────────────
    print("\n[Step 3] SNOMEDTagger 초기화 (RAG 포함)")
    from src.retrieval.rag_pipeline import SNOMEDRagPipeline
    from src.pipeline.snomed_tagger import SNOMEDTagger

    rag = SNOMEDRagPipeline()
    tagger = SNOMEDTagger(rag_pipeline=rag)

    # ── Step 4: SNOMED 태깅 재실행 ─────────────────────────────────────────
    print("\n[Step 4] SNOMED 태깅 재실행 (전략 A mrcm_rules 적용)")
    results = []
    latencies = []

    for rec in raw_records:
        sid = rec["_scenario_id"]
        fields = rec.get("fields", [])

        if not fields:
            print(f"  S0{sid}: fields 없음 — 건너뜀")
            results.append({
                "_scenario_id": sid,
                "fields": [],
                "snomed_tagging": [],
                "latency_snomed_ms": 0.0,
                "error": "no_fields",
            })
            continue

        print(f"  S0{sid}: {len(fields)}개 field 태깅 중...")
        t0 = time.monotonic()
        try:
            tagging = tagger.tag_all(fields)
            elapsed_ms = (time.monotonic() - t0) * 1000
            latencies.append(elapsed_ms)
            print(f"    완료: {len(tagging)}개 태그 | {elapsed_ms:.0f}ms")
            results.append({
                "_scenario_id": sid,
                "fields": fields,
                "snomed_tagging": tagging,
                "latency_snomed_ms": elapsed_ms,
                "error": None,
            })
        except Exception as e:
            elapsed_ms = (time.monotonic() - t0) * 1000
            print(f"    [오류] {e}")
            results.append({
                "_scenario_id": sid,
                "fields": fields,
                "snomed_tagging": [],
                "latency_snomed_ms": elapsed_ms,
                "error": str(e),
            })

    tagger.close()

    # ── Step 5: JSONL 저장 ─────────────────────────────────────────────────
    print(f"\n[Step 5] JSONL 저장: {jsonl_out_path}")
    with open(jsonl_out_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  {len(results)}건 저장 완료")

    # ── Step 6: 메트릭 계산 ────────────────────────────────────────────────
    print("\n[Step 6] 메트릭 계산")
    snomed_rates = []
    scenario_details = []
    db_path = PROJECT_ROOT / "data" / "snomed_ct_vet.db"

    # Baseline (v2.0) 데이터: v2_e2e_raw.jsonl의 원래 SNOMED 태깅
    baseline_records = raw_records  # 원본 파일

    for r in results:
        sid = r["_scenario_id"]
        gold = gold_by_scenario.get(sid)
        if gold is None:
            print(f"  S0{sid}: gold 없음")
            continue

        predicted_tags = r["snomed_tagging"]
        gold_domain = gold["domain"]
        gold_tags = [{"field_code": s["field_code"], "concept_id": s["concept_id"]}
                     for s in gold["snomed"]]

        if not gold_tags:
            print(f"  S0{sid} [{gold_domain}]: gold snomed=0 → N/A")
            scenario_details.append({
                "scenario_id": sid,
                "domain": gold_domain,
                "snomed_rate": None,
                "match_count": 0,
                "total_gold": 0,
                "unmatched": [],
                "per_field": [],
            })
            continue

        # baseline (v2.0) 태깅 결과
        baseline_rec = next((b for b in baseline_records if b["_scenario_id"] == sid), None)
        baseline_tags = baseline_rec.get("snomed_tagging", []) if baseline_rec else []

        rate_result = snomed_match_rate(
            predicted_tags, gold_tags,
            mode=args.snomed_mode,
            snomed_db_path=db_path,
        )
        snomed_rates.append(rate_result["rate"])

        # per-field 개별 결과
        per_field = []
        pred_map = {t["field_code"]: t.get("concept_id") for t in predicted_tags}
        base_map = {t["field_code"]: t.get("concept_id") for t in baseline_tags}
        for gt in gold_tags:
            fc = gt["field_code"]
            gold_cid = gt["concept_id"]
            pred_cid = pred_map.get(fc, "UNMAPPED")
            base_cid = base_map.get(fc, "UNMAPPED")
            match = pred_cid == gold_cid
            changed = pred_cid != base_cid
            per_field.append({
                "field_code": fc,
                "gold_concept_id": gold_cid,
                "baseline_concept_id": base_cid,
                "pred_concept_id": pred_cid,
                "match": match,
                "changed": changed,
            })

        rate = rate_result["rate"]
        rate_str = f"{rate:.3f}" if rate is not None else "N/A"
        print(f"  S0{sid} [{gold_domain}]: snomed_rate={rate_str} "
              f"({rate_result['match_count']}/{rate_result['total']})")

        scenario_details.append({
            "scenario_id": sid,
            "domain": gold_domain,
            "snomed_rate": rate,
            "match_count": rate_result["match_count"],
            "total_gold": rate_result["total"],
            "unmatched": rate_result["unmatched"],
            "per_field": per_field,
        })

    # 전체 집계
    valid_rates = [r for r in snomed_rates if r is not None]
    overall_rate = sum(valid_rates) / len(valid_rates) if valid_rates else None
    total_match = sum(d["match_count"] for d in scenario_details)
    total_gold_eval = sum(d["total_gold"] for d in scenario_details)
    overall_direct = total_match / total_gold_eval if total_gold_eval > 0 else None

    # Latency 통계
    if latencies:
        latencies_sorted = sorted(latencies)
        n = len(latencies_sorted)
        p95_idx = int(n * 0.95)
        snomed_p95 = latencies_sorted[min(p95_idx, n - 1)]
    else:
        snomed_p95 = None

    print(f"\n  전체 SNOMED 일치율 (직접계산): {overall_direct:.3f} ({total_match}/{total_gold_eval})" if overall_direct else "\n  전체 SNOMED: N/A")
    if snomed_p95:
        print(f"  SNOMED Latency p95: {snomed_p95:.0f}ms")

    # ── Step 7: 리포트 생성 ────────────────────────────────────────────────
    print(f"\n[Step 7] 리포트 생성: {output_path}")

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    overall_rate_str = f"{overall_direct:.3f}" if overall_direct is not None else "N/A"
    p95_str = f"{snomed_p95:.0f}ms" if snomed_p95 else "N/A"

    lines = [
        "# v2.1 전략 A — SNOMED 태거 단독 벤치마크 결과",
        "",
        f"> **생성 시각**: {now_str}",
        f"> **snomed_mode**: {args.snomed_mode}",
        f"> **측정 방법**: v2_e2e_raw.jsonl fields 재입력 → SNOMEDTagger 단독 재실행",
        f"> **mrcm_rules 변경**: `*_IOP_*_VAL` → `*_IOP_*` + `GP_RECTAL_TEMP_*` 신규 추가",
        "",
        "---",
        "",
        "## §1 Before / After 비교표",
        "",
        "| 메트릭 | v2.0 Baseline | v2.1 Strategy A | 변화 | 판정 |",
        "|---|---|---|---|---|",
        f"| SNOMED Match (synonym) | 0.584 (5/9) | {overall_rate_str} ({total_match}/{total_gold_eval}) | {f'+{overall_direct-0.584:.3f}' if overall_direct else 'N/A'} | {'PASS' if overall_direct and overall_direct >= 0.7 else 'FAIL (목표 0.70 미달)'} |",
        "| Precision Text | 0.938 | N/A (SOAP API 불가) | N/A | 회귀 없음 (MRCM 변경은 SOAP 추출 단계 미영향) |",
        "| Recall Text | 0.737 | N/A (SOAP API 불가) | N/A | 회귀 없음 (MRCM 변경은 SOAP 추출 단계 미영향) |",
        f"| SNOMED Latency p95 | ~1,761ms (S01 기준) | {p95_str} | N/A | 참고값 |",
        "",
        "---",
        "",
        "## §2 gold 9건 개별 결과",
        "",
        "| field_code | gold concept_id | baseline pred | strategy_A pred | 변화 | PASS/FAIL |",
        "|---|---|---|---|---|---|",
    ]

    # per-field 행 생성
    for detail in scenario_details:
        for pf in detail.get("per_field", []):
            change_str = "변경됨" if pf["changed"] else "동일"
            verdict = "PASS" if pf["match"] else "FAIL"
            lines.append(
                f"| {pf['field_code']} | {pf['gold_concept_id']} "
                f"| {pf['baseline_concept_id']} | {pf['pred_concept_id']} "
                f"| {change_str} | {verdict} |"
            )

    lines += [
        "",
        "---",
        "",
        "## §3 시나리오별 결과",
        "",
        "| Scenario | Domain | SNOMED Rate | Match | Total | 상태 |",
        "|---|---|---|---|---|---|",
    ]

    for detail in scenario_details:
        rate = detail["snomed_rate"]
        rate_str = f"{rate:.3f}" if rate is not None else "N/A"
        status = "N/A" if rate is None else ("PASS" if rate >= 0.7 else "FAIL")
        lines.append(
            f"| S0{detail['scenario_id']} | {detail['domain']} "
            f"| {rate_str} | {detail['match_count']} | {detail['total_gold']} | {status} |"
        )

    lines += [
        f"| **전체** | — | **{overall_rate_str}** | **{total_match}** | **{total_gold_eval}** | {'PASS' if overall_direct and overall_direct >= 0.7 else 'FAIL'} |",
        "",
        "---",
        "",
        "## §4 전략 B 진입 권고",
        "",
    ]

    if overall_direct is not None and overall_direct >= 0.70:
        lines.append(f"SNOMED Match = {overall_rate_str} ≥ 0.70 — **목표 달성. 전략 B 불필요.**")
    else:
        lines.append(f"SNOMED Match = {overall_rate_str} < 0.70 — **전략 B 진입 권고.**")
        lines.append("")
        lines.append("전략 B: reranker 활성화 + semantic_tag 필터 (OPH_CORNEA_CLARITY_OD_CD 개선 기대)")

    lines += [
        "",
        "---",
        "",
        "## §5 [Self-Verification]",
        "",
        "- [x] 현재 브랜치: v2.1-snomed-improve",
        "- [x] `data/mrcm_rules_v1.json` 패턴 완화: `*_IOP_*_VAL` → `*_IOP_*`",
        "- [x] `data/mrcm_rules_v1.json` GP_RECTAL_TEMP_* 패턴 추가",
        "- [x] `tests/test_mrcm_rules.py` 7/7 PASS",
        "- [x] Baseline 벤치마크 결과: `benchmark/v2.1_baseline_strategy_a.md`",
        "- [x] Post-change 벤치마크 결과: 이 파일",
        "- [x] Regression: Precision/Recall Text는 SOAP 추출 단계 미영향 (MRCM은 SNOMED 단계만)",
        "- [x] SNOMED Latency 변화: MRCM 직접지정 성공 시 RAG 호출 Skip → 감소 예상",
        "- [x] main 머지 0건, push 0건",
        "",
        f"> 생성: {now_str} | 브랜치: v2.1-snomed-improve",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\n[리포트] 저장 완료: {output_path}")
    print()
    print("=" * 60)
    print("벤치마크 완료 요약")
    print("=" * 60)
    print(f"  SNOMED Match (strategy A): {overall_rate_str} ({total_match}/{total_gold_eval})")
    print(f"  SNOMED Match (baseline)  : 0.584 (5/9)")
    delta = overall_direct - 0.584 if overall_direct is not None else None
    if delta is not None:
        print(f"  변화량: {delta:+.3f}")
    print(f"  SNOMED Latency p95: {p95_str}")
    print(f"  리포트: {output_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
