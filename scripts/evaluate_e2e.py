"""
evaluate_e2e.py — vet-snomed-rag v2.0 C2 E2E 평가 메인 러너
=============================================================

사용법:
  # Day 5 dry_run (텍스트 모드, API 키 불필요):
  python scripts/evaluate_e2e.py --input-mode text --dry-run

  # Day 6 오디오 모드 (녹음 완료 후):
  python scripts/evaluate_e2e.py --input-mode audio --input-dir data/synthetic_scenarios/

공통 옵션:
  --input-mode   text | audio  (기본: text)
  --input-dir    입력 디렉토리 (기본: data/synthetic_scenarios/)
  --output       출력 리포트 경로 (기본: benchmark/v2_e2e_report.md)
  --jsonl-out    JSONL 출력 경로 (기본: benchmark/v2_e2e_raw.jsonl)
  --snomed-mode  exact | synonym (기본: exact)
  --dry-run      API 미호출 (ClinicalEncoder dry_run=True)
  --no-chart     차트 생성 건너뜀

[절대 원칙]
  - 통계 수치만 보고. 임상/투자 판단 문구 0건 (data-analyzer 원칙)
  - gold-label 조작 금지. 파싱 실패 시 즉시 FAIL 종료
  - v1.0 src/retrieval/* 무변경
  - B1~B4 src/pipeline/* 무변경
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── 프로젝트 루트 설정 ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.eval.parse_gold_labels import load_all_gold_labels
from scripts.eval.metrics import (
    compute_scenario_metrics,
    aggregate_metrics,
)

DATA_DIR      = PROJECT_ROOT / "data" / "synthetic_scenarios"
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
CHARTS_DIR    = BENCHMARK_DIR / "charts"


# ─── 헬퍼: None-safe 포맷 ────────────────────────────────────────────────────

def _fmt_float(val, decimals=3):
    """None-safe float 포맷."""
    return f"{val:.{decimals}f}" if val is not None else "N/A"


def _fmt_ms(val):
    """None-safe ms 포맷."""
    return f"{val:.0f} ms" if val is not None else "N/A"


# ─── Step 1: 입력 준비 ────────────────────────────────────────────────────────

def _build_text_inputs(gold_labels: list[dict], input_dir: Path) -> list[dict]:
    """텍스트 모드 입력 목록을 구성한다.

    gold-label의 녹음 스크립트 섹션을 마크다운에서 추출하여 사용한다.

    Args:
        gold_labels : load_all_gold_labels() 반환값
        input_dir   : synthetic_scenarios 디렉토리

    Returns:
        [{"scenario_id": int, "data": str, "type": "text"}, ...]
    """
    import re
    inputs = []
    md_files = sorted(
        [f for f in input_dir.glob("scenario_*.md") if f.stem != "README"],
        key=lambda p: int(re.search(r"scenario_(\d+)", p.stem).group(1))
        if re.search(r"scenario_(\d+)", p.stem) else 999,
    )

    for md_path in md_files:
        sid_match = re.search(r"scenario_(\d+)", md_path.stem)
        if not sid_match:
            continue
        sid = int(sid_match.group(1))
        text = md_path.read_text(encoding="utf-8")

        # 녹음 스크립트 섹션 추출
        script_match = re.search(
            r"## 녹음 스크립트.*?\n(.*?)(?=^##|\Z)",
            text,
            re.DOTALL | re.MULTILINE,
        )
        if script_match:
            script_text = script_match.group(1).strip()
        else:
            script_text = text.strip()
            print(f"  [WARN] S{sid:02d}: 녹음 스크립트 섹션 없음 — 전체 텍스트 사용")

        inputs.append({"scenario_id": sid, "data": script_text, "type": "text"})
        print(f"  [OK] S{sid:02d} 텍스트 준비: {len(script_text)}자")

    return inputs


def _build_audio_inputs(gold_labels: list[dict], input_dir: Path) -> list[dict]:
    """오디오 모드 입력 목록을 구성한다.

    Args:
        gold_labels : load_all_gold_labels() 반환값
        input_dir   : m4a 파일이 있는 디렉토리

    Returns:
        [{"scenario_id": int, "data": str(파일경로), "type": "audio"}, ...]

    Raises:
        FileNotFoundError: 필요한 오디오 파일이 없는 경우
    """
    inputs = []
    missing = []

    for lb in gold_labels:
        sid = lb["scenario_id"]
        candidates = list(input_dir.glob(f"scenario_{sid}*.m4a"))
        if not candidates:
            candidates = list(input_dir.glob(f"scenario_{sid}*.wav"))
        if not candidates:
            candidates = list(input_dir.glob(f"scenario_{sid}*.mp3"))

        if not candidates:
            missing.append(f"scenario_{sid}.m4a (또는 .wav/.mp3)")
            continue

        audio_path = candidates[0]
        inputs.append({"scenario_id": sid, "data": str(audio_path), "type": "audio"})
        print(f"  [OK] S{sid:02d} 오디오: {audio_path.name}")

    if missing:
        raise FileNotFoundError(
            f"오디오 파일 없음 {len(missing)}건:\n" + "\n".join(f"  - {m}" for m in missing)
        )

    return inputs


# ─── Step 2: E2E 실행 ─────────────────────────────────────────────────────────

def _run_encoder(
    inputs: list[dict],
    dry_run: bool,
    jsonl_out: Path,
) -> list[dict]:
    """ClinicalEncoder를 실행하여 JSONL 레코드를 생성한다."""
    from src.pipeline.e2e import ClinicalEncoder, ClinicalEncoderConfig

    config = ClinicalEncoderConfig(
        dry_run=dry_run,
        reformulator_backend="gemini",
        enable_rerank=False,
    )
    encoder = ClinicalEncoder(config=config)

    jsonl_out.parent.mkdir(parents=True, exist_ok=True)
    records = []

    with open(jsonl_out, "w", encoding="utf-8") as f:
        for i, item in enumerate(inputs, 1):
            sid   = item["scenario_id"]
            data  = item["data"]
            itype = item["type"]
            print(f"\n[E2E] {i}/{len(inputs)} — S{sid:02d} (type={itype})")

            t0 = time.perf_counter()
            record = encoder.encode(data, input_type=itype)
            elapsed = time.perf_counter() - t0

            record["_scenario_id"] = sid
            records.append(record)
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            print(f"  완료: {elapsed:.2f}s | errors={record.get('errors', [])}")

    encoder.close()
    print(f"\n[E2E] 총 {len(records)}건 → {jsonl_out}")
    return records


# ─── Step 3: 메트릭 계산 ──────────────────────────────────────────────────────

def _compute_all_metrics(
    gold_labels: list[dict],
    records: list[dict],
    snomed_mode: str,
) -> tuple[list[dict], dict]:
    """모든 시나리오의 메트릭을 계산하고 집계한다."""
    gold_by_id   = {lb["scenario_id"]: lb for lb in gold_labels}
    record_by_id = {rec["_scenario_id"]: rec for rec in records}

    per_scenario = []
    for sid, gold in sorted(gold_by_id.items()):
        rec = record_by_id.get(sid)
        if rec is None:
            print(f"  [WARN] S{sid:02d}: 레코드 없음 — 메트릭 건너뜀")
            continue
        m = compute_scenario_metrics(sid, gold, rec, snomed_mode=snomed_mode)
        per_scenario.append(m)
        prec     = m["field_metrics"]["precision"]
        rec_val  = m["field_metrics"]["recall"]
        snomed_r = m["snomed_metrics"]["rate"]
        print(f"  S{sid:02d} [{gold['domain']}] "
              f"precision={_fmt_float(prec)} "
              f"recall={_fmt_float(rec_val)} "
              f"snomed_rate={_fmt_float(snomed_r)}")

    aggregated = aggregate_metrics(per_scenario)
    return per_scenario, aggregated


# ─── Step 4: 차트 3장 생성 ────────────────────────────────────────────────────

def _generate_charts(
    per_scenario: list[dict],
    aggregated: dict,
    charts_dir: Path,
) -> dict[str, Path]:
    """차트 3장을 생성한다."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib as mpl
    except ImportError:
        print("  [WARN] matplotlib 없음 — 차트 생성 건너뜀")
        return {}

    charts_dir.mkdir(parents=True, exist_ok=True)

    mpl.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "DejaVu Sans"]
    mpl.rcParams["axes.unicode_minus"] = False
    COLOR_PRIMARY   = "#1F77B4"
    COLOR_SECONDARY = "#FF7F0E"

    output_paths: dict[str, Path] = {}

    # ── Chart 1: 도메인별 필드 precision/recall 바 차트 ──────────────────
    domains    = [m["domain"] for m in per_scenario]
    precisions = [m["field_metrics"]["precision"] if m["field_metrics"]["precision"] is not None else 0.0
                  for m in per_scenario]
    recalls    = [m["field_metrics"]["recall"] if m["field_metrics"]["recall"] is not None else 0.0
                  for m in per_scenario]

    try:
        import numpy as np
        x = np.arange(len(domains))
        w = 0.38
        fig, ax = plt.subplots(figsize=(10, 5.5))
        b1 = ax.bar(x - w / 2, precisions, w, label="Precision", color=COLOR_PRIMARY)
        b2 = ax.bar(x + w / 2, recalls,    w, label="Recall",    color=COLOR_SECONDARY)
        ax.set_xticks(x)
        ax.set_xticklabels(domains, rotation=15, ha="right", fontsize=9)
        ax.set_ylabel("Score (0~1)", fontsize=11)
        ax.set_title("Field Extraction: Precision & Recall by Domain", fontsize=13, pad=14)
        ax.set_ylim(0, 1.25)
        ax.axhline(0.80, color="#d62728", linestyle="--", linewidth=1.0,
                   alpha=0.7, label="Target precision >=0.80")
        ax.axhline(0.70, color="#9467bd", linestyle="--", linewidth=1.0,
                   alpha=0.7, label="Target recall >=0.70")
        for bar, v in zip(list(b1) + list(b2), precisions + recalls):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{v:.2f}", ha="center", va="bottom", fontsize=8)
        ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        ax.set_axisbelow(True)
        fig.tight_layout()
        out1 = charts_dir / "v2_field_accuracy.png"
        fig.savefig(out1, dpi=150)
        plt.close(fig)
        output_paths["v2_field_accuracy"] = out1
        print(f"  [OK] 차트 1: {out1.name}")
    except Exception as e:
        print(f"  [WARN] 차트 1 생성 실패: {e}")

    # ── Chart 2: SNOMED 태깅 일치율 ──────────────────────────────────────
    try:
        snomed_rates = [
            m["snomed_metrics"]["rate"] if m["snomed_metrics"]["rate"] is not None else 0.0
            for m in per_scenario
        ]
        scenario_labels = [f"S{m['scenario_id']:02d}\n{m['domain'][:6]}" for m in per_scenario]

        fig, ax = plt.subplots(figsize=(9, 5))
        bars = ax.bar(scenario_labels, snomed_rates, color=COLOR_PRIMARY, width=0.55)
        ax.set_ylabel("Match Rate (exact concept_id)", fontsize=11)
        ax.set_title("SNOMED CT Tagging Match Rate per Scenario", fontsize=13, pad=14)
        ax.set_ylim(0, 1.25)
        ax.axhline(0.70, color="#d62728", linestyle="--", linewidth=1.0,
                   alpha=0.7, label="Target >=0.70")
        for bar, v in zip(bars, snomed_rates):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{v:.2f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
        ax.legend(loc="upper right", fontsize=9)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        ax.set_axisbelow(True)
        fig.tight_layout()
        out2 = charts_dir / "v2_snomed_match.png"
        fig.savefig(out2, dpi=150)
        plt.close(fig)
        output_paths["v2_snomed_match"] = out2
        print(f"  [OK] 차트 2: {out2.name}")
    except Exception as e:
        print(f"  [WARN] 차트 2 생성 실패: {e}")

    # ── Chart 3: 단계별 latency 스택 바 ──────────────────────────────────
    try:
        stages       = ["stt", "soap", "snomed"]
        stage_labels = ["STT", "SOAP", "SNOMED"]
        stage_colors = ["#1F77B4", "#FF7F0E", "#2CA02C"]

        latencies_by_stage: dict[str, list[float]] = {s: [] for s in stages}
        for m in per_scenario:
            for stage in stages:
                stage_data = m["latency"].get(stage, {})
                val = stage_data.get("mean") if isinstance(stage_data, dict) else None
                latencies_by_stage[stage].append(val if val is not None else 0.0)

        x_labels = [f"S{m['scenario_id']:02d}" for m in per_scenario]

        fig, ax = plt.subplots(figsize=(9, 5))
        bottom = [0.0] * len(per_scenario)
        for stage, label, color in zip(stages, stage_labels, stage_colors):
            vals = latencies_by_stage[stage]
            ax.bar(x_labels, vals, bottom=bottom, label=label, color=color, width=0.55)
            bottom = [b + v for b, v in zip(bottom, vals)]

        ax.axhline(60_000, color="#d62728", linestyle="--", linewidth=1.0,
                   alpha=0.7, label="Target total p95 <=60,000 ms")
        ax.set_ylabel("Latency (ms)", fontsize=11)
        ax.set_title("E2E Latency by Stage per Scenario\n(stacked: STT + SOAP + SNOMED)",
                     fontsize=12, pad=14)
        ax.legend(loc="upper right", fontsize=8, framealpha=0.9)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        ax.set_axisbelow(True)
        fig.tight_layout()
        out3 = charts_dir / "v2_e2e_latency.png"
        fig.savefig(out3, dpi=150)
        plt.close(fig)
        output_paths["v2_e2e_latency"] = out3
        print(f"  [OK] 차트 3: {out3.name}")
    except Exception as e:
        print(f"  [WARN] 차트 3 생성 실패: {e}")

    return output_paths


# ─── Step 5: 리포트 생성 ──────────────────────────────────────────────────────

def _generate_report(
    gold_labels: list[dict],
    per_scenario: list[dict],
    aggregated: dict,
    records: list[dict],
    chart_paths: dict[str, Path],
    jsonl_out: Path,
    output_path: Path,
    input_mode: str,
    dry_run: bool,
    snomed_mode: str,
) -> None:
    """benchmark/v2_e2e_report.md 를 생성한다.

    [절대 원칙] 임상/투자 판단 문구 0건.
    """
    now      = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    run_mode = "dry_run (텍스트 입력)" if dry_run else f"{input_mode} 모드"
    dry_note = "dry_run 수치이므로 Day 6 재실행 전까지 공식 수치 아님" if dry_run else "공식 측정 수치"

    # 집계 수치 추출
    field_prec = aggregated["field"].get("precision_mean")
    field_rec  = aggregated["field"].get("recall_mean")
    field_f1   = aggregated["field"].get("f1_mean")
    snomed_r   = aggregated["snomed"].get("exact_rate_mean")
    lat_p95    = aggregated.get("latency_total_p95_ms")
    total_tp   = aggregated["field"].get("total_tp", 0)
    total_fp   = aggregated["field"].get("total_fp", 0)
    total_fn   = aggregated["field"].get("total_fn", 0)

    # 문자열 포맷 (None-safe)
    fp_str   = _fmt_float(field_prec)
    fr_str   = _fmt_float(field_rec)
    ff1_str  = _fmt_float(field_f1)
    snmd_str = _fmt_float(snomed_r)
    lp95_str = _fmt_ms(lat_p95)

    # PASS/FAIL 판정 (§5.2)
    def _status(val, target, higher=True):
        if val is None:
            return "N/A (측정 불가)"
        ok = (val >= target) if higher else (val <= target)
        op = ">=" if higher else "<="
        return f"{'PASS' if ok else 'FAIL'} ({val:.3f} {op} {target})"

    prec_status   = _status(field_prec, 0.80)
    rec_status    = _status(field_rec,  0.70)
    snomed_status = _status(snomed_r,   0.70)
    lat_status    = _status(lat_p95, 60_000, higher=False) if lat_p95 is not None else "N/A"

    # 차트 경로 (상대 경로)
    def _rel(p):
        if p is None:
            return "(생성 실패)"
        try:
            return str(p.relative_to(output_path.parent))
        except ValueError:
            return str(p)

    chart1 = _rel(chart_paths.get("v2_field_accuracy"))
    chart2 = _rel(chart_paths.get("v2_snomed_match"))
    chart3 = _rel(chart_paths.get("v2_e2e_latency"))

    # ── 리포트 본문 ──────────────────────────────────────────────────────
    lines = [
        "# v2.0 E2E 평가 리포트",
        "",
        f"> **생성 시각**: {now}  ",
        f"> **실행 모드**: {run_mode}  ",
        f"> **SNOMED 일치 모드**: {snomed_mode}  ",
        f"> **주의**: {dry_note}",
        "",
        "---",
        "",
        "## §1 Executive Summary",
        "",
        "| 메트릭 | 목표 (§5.2) | 결과 | 상태 |",
        "|---|---|---|---|",
        f"| SOAP 필드 Precision | >=0.800 | {fp_str} | {prec_status} |",
        f"| SOAP 필드 Recall | >=0.700 | {fr_str} | {rec_status} |",
        f"| SNOMED 태깅 일치율 (exact) | >=0.700 | {snmd_str} | {snomed_status} |",
        f"| E2E Latency p95 | <=60,000 ms | {lp95_str} | {lat_status} |",
        "",
        "---",
        "",
        "## §2 시나리오별 상세 결과",
        "",
        "| Scenario | Domain | Precision | Recall | F1 | TP | FP | FN | SNOMED Rate | Total Latency |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    for m in per_scenario:
        sid       = m["scenario_id"]
        domain    = m["domain"]
        prec      = m["field_metrics"]["precision"]
        rec       = m["field_metrics"]["recall"]
        f1v       = m["field_metrics"]["f1"]
        s_rate    = m["snomed_metrics"]["rate"]
        total_lat = m["latency"].get("total", {})
        lat_mean  = total_lat.get("mean") if isinstance(total_lat, dict) else None
        tp        = m["field_metrics"]["tp"]
        fp        = m["field_metrics"]["fp"]
        fn        = m["field_metrics"]["fn"]

        lines.append(
            f"| S{sid:02d} | {domain} "
            f"| {_fmt_float(prec)} | {_fmt_float(rec)} | {_fmt_float(f1v)} "
            f"| {tp} | {fp} | {fn} "
            f"| {_fmt_float(s_rate)} | {_fmt_ms(lat_mean)} |"
        )

    lines += [
        "",
        "---",
        "",
        "## §3 메트릭 요약 (Target vs Actual)",
        "",
        "### 필드 추출",
        "",
        "| 항목 | 수치 |",
        "|---|---|",
        f"| Precision (mean) | {fp_str} |",
        f"| Recall (mean) | {fr_str} |",
        f"| F1 (mean) | {ff1_str} |",
        f"| 총 TP | {total_tp} |",
        f"| 총 FP | {total_fp} |",
        f"| 총 FN | {total_fn} |",
        "",
        f"### SNOMED 태깅 ({snomed_mode} 모드)",
        "",
        "| 항목 | 수치 |",
        "|---|---|",
        f"| 일치율 (mean) | {snmd_str} |",
        "",
        "### Latency",
        "",
        "| 시나리오 | STT p50 | SOAP p50 | SNOMED p50 | Total p50 | Total p95 |",
        "|---|---|---|---|---|---|",
    ]

    for m in per_scenario:
        sid = m["scenario_id"]
        lat = m["latency"]

        def _flt(stage, stat, _lat=lat):
            d = _lat.get(stage, {})
            v = d.get(stat) if isinstance(d, dict) else None
            return _fmt_ms(v)

        lines.append(
            f"| S{sid:02d} | {_flt('stt','p50')} | {_flt('soap','p50')} "
            f"| {_flt('snomed','p50')} | {_flt('total','p50')} | {_flt('total','p95')} |"
        )

    lines += [
        "",
        "---",
        "",
        "## §4 차트",
        "",
        "### Chart 1: 도메인별 필드 Precision/Recall",
        "",
        f"![Field Accuracy]({chart1})",
        "",
        "### Chart 2: SNOMED 태깅 일치율",
        "",
        f"![SNOMED Match]({chart2})",
        "",
        "### Chart 3: E2E Latency (단계별)",
        "",
        f"![E2E Latency]({chart3})",
        "",
        "---",
        "",
        "## §5 Raw JSONL 출력 경로",
        "",
        "```",
        str(jsonl_out),
        "```",
        "",
        "---",
        "",
        "> 본 리포트는 정량 수치만 포함합니다. 임상적 판단은 포함하지 않습니다.",
        "> (data-analyzer 원칙 준수)",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n[리포트] 생성 완료: {output_path}")


# ─── 메인 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="vet-snomed-rag v2.0 C2 E2E 평가 러너")
    parser.add_argument("--input-mode", choices=["text", "audio"], default="text")
    parser.add_argument("--input-dir",  type=Path, default=DATA_DIR)
    parser.add_argument("--output",     type=Path, default=BENCHMARK_DIR / "v2_e2e_report.md")
    parser.add_argument("--jsonl-out",  type=Path, default=BENCHMARK_DIR / "v2_e2e_raw.jsonl")
    parser.add_argument("--snomed-mode", choices=["exact", "synonym"], default="exact")
    parser.add_argument("--dry-run",    action="store_true")
    parser.add_argument("--no-chart",   action="store_true")
    args = parser.parse_args()

    print("=" * 60)
    print("vet-snomed-rag v2.0 E2E 평가 러너")
    print(f"  input_mode  = {args.input_mode}")
    print(f"  dry_run     = {args.dry_run}")
    print(f"  snomed_mode = {args.snomed_mode}")
    print(f"  output      = {args.output}")
    print("=" * 60)

    # Step 1: gold-label 파싱
    print("\n[Step 1] Gold-label 파싱")
    gold_labels = load_all_gold_labels(args.input_dir)
    total_fields_gold  = sum(len(lb["fields"]) for lb in gold_labels)
    total_snomed_gold  = sum(len(lb["snomed"]) for lb in gold_labels)
    print(f"  파싱 성공: {len(gold_labels)}/5 시나리오")
    print(f"  총 gold 필드: {total_fields_gold}, 총 gold concept_id: {total_snomed_gold}")

    # Step 2: 입력 준비
    print(f"\n[Step 2] {args.input_mode} 입력 준비")
    if args.input_mode == "text":
        inputs = _build_text_inputs(gold_labels, args.input_dir)
    else:
        inputs = _build_audio_inputs(gold_labels, args.input_dir)

    # Step 3: E2E 실행
    print("\n[Step 3] E2E 인코더 실행")
    records = _run_encoder(inputs, dry_run=args.dry_run, jsonl_out=args.jsonl_out)
    print(f"  JSONL {len(records)}건 생성")

    # Step 4: 메트릭 계산
    print("\n[Step 4] 메트릭 계산")
    per_scenario, aggregated = _compute_all_metrics(gold_labels, records, args.snomed_mode)

    # Step 5: 차트 생성
    chart_paths: dict = {}
    if not args.no_chart:
        print("\n[Step 5] 차트 생성")
        chart_paths = _generate_charts(per_scenario, aggregated, CHARTS_DIR)

    # Step 6: 리포트 생성
    print("\n[Step 6] 리포트 생성")
    _generate_report(
        gold_labels=gold_labels,
        per_scenario=per_scenario,
        aggregated=aggregated,
        records=records,
        chart_paths=chart_paths,
        jsonl_out=args.jsonl_out,
        output_path=args.output,
        input_mode=args.input_mode,
        dry_run=args.dry_run,
        snomed_mode=args.snomed_mode,
    )

    # ── 최종 요약 출력 ────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("평가 완료 요약")
    print("=" * 60)
    field_prec = aggregated["field"].get("precision_mean")
    field_rec  = aggregated["field"].get("recall_mean")
    snomed_r   = aggregated["snomed"].get("exact_rate_mean")
    lat_p95    = aggregated.get("latency_total_p95_ms")

    prec_pass  = "PASS" if (field_prec is not None and field_prec >= 0.80) else "FAIL/N/A"
    rec_pass   = "PASS" if (field_rec  is not None and field_rec  >= 0.70) else "FAIL/N/A"
    snmd_pass  = "PASS" if (snomed_r   is not None and snomed_r   >= 0.70) else "FAIL/N/A"
    lat_pass   = "PASS" if (lat_p95    is not None and lat_p95    <= 60_000) else "FAIL/N/A"

    print(f"  gold-label 파싱  : {len(gold_labels)}/5")
    print(f"  JSONL 레코드     : {len(records)}건")
    print(f"  필드 precision   : {_fmt_float(field_prec)}  (목표 >=0.800: {prec_pass})")
    print(f"  필드 recall      : {_fmt_float(field_rec)}   (목표 >=0.700: {rec_pass})")
    print(f"  SNOMED 일치율    : {_fmt_float(snomed_r)}    (목표 >=0.700: {snmd_pass})")
    print(f"  Latency p95      : {_fmt_ms(lat_p95)}        (목표 <=60,000 ms: {lat_pass})")
    print(f"  차트             : {len(chart_paths)}장")
    print(f"  리포트           : {args.output}")
    if args.dry_run:
        print("\n  [주의] dry_run 수치 — Day 6 오디오 재실행 전까지 공식 수치 아님")
    print("=" * 60)


if __name__ == "__main__":
    main()
