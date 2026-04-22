#!/usr/bin/env python3
"""
Day 3 A1: 4모드 회귀 결과 차트 생성 스크립트.

출력:
  benchmark/charts/v2_pass_by_mode.png
  benchmark/charts/v2_mrr_by_mode.png
  benchmark/charts/v2_latency_by_mode.png

기존 generate_charts.py 스타일 (AppleGothic 폰트, 동일 색상 체계) 준수.
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW_PATH = ROOT / "benchmark" / "reranker_regression_raw.json"
OUT_DIR = ROOT / "benchmark" / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

mpl.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False

# 색상: 기존 스타일 준수 (회색=baseline, 파란 계열=신규)
COLORS = {
    "M1": "#B0B0B0",   # baseline (회색)
    "M2": "#1F77B4",   # reformulator only (파랑)
    "M3": "#FF7F0E",   # rerank only (주황)
    "M4": "#2CA02C",   # v2.0 후보 (초록)
}
MODE_LABELS = {
    "M1": "M1\n(baseline)",
    "M2": "M2\n(reformulator\nonly)",
    "M3": "M3\n(rerank\nonly)",
    "M4": "M4\n(rerank+\nreformulator)",
}

with RAW_PATH.open(encoding="utf-8") as f:
    raw = json.load(f)

# 데이터 추출
mode_ids = [d["mode"]["mode_id"] for d in raw]
summaries = {d["mode"]["mode_id"]: d["summary"] for d in raw}
latency_summaries = {d["mode"]["mode_id"]: d["latency_summary"] for d in raw}
queries_by_mode = {d["mode"]["mode_id"]: d["queries"] for d in raw}

# 쿼리 ID 목록 (T5 NA 포함)
query_ids = [q["query_id"] for q in queries_by_mode["M1"]]


# ─── Chart 1: PASS/FAIL 비율 막대 차트 ─────────────────────
fig1, ax1 = plt.subplots(figsize=(8, 5))

x = np.arange(len(mode_ids))
width = 0.55

pass_counts = [summaries[m]["pass_count"] for m in mode_ids]
fail_counts = [summaries[m]["fail_count"] for m in mode_ids]
evaluable_counts = [summaries[m]["evaluable_count"] for m in mode_ids]

bars_pass = ax1.bar(x, pass_counts, width, label="PASS", color=[COLORS[m] for m in mode_ids], alpha=0.9)
bars_fail = ax1.bar(x, fail_counts, width, bottom=pass_counts, label="FAIL", color="salmon", alpha=0.7)

# PASS 수치 표기
for bar, pc, ec in zip(bars_pass, pass_counts, evaluable_counts):
    ax1.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() / 2,
        f"{pc}/{ec}",
        ha="center", va="center",
        fontsize=13, fontweight="bold", color="white",
    )

ax1.set_xticks(x)
ax1.set_xticklabels([MODE_LABELS[m] for m in mode_ids], fontsize=10)
ax1.set_ylabel("쿼리 수 (T5 NA 제외: 10건)", fontsize=11)
ax1.set_title("모드별 PASS/FAIL (11쿼리, T5 NA 제외)", fontsize=13, fontweight="bold")
ax1.set_ylim(0, 12)
ax1.legend(loc="upper right", fontsize=10)
ax1.axhline(y=10, color="red", linestyle="--", linewidth=1.0, alpha=0.5, label="목표 10/10")
ax1.text(3.4, 10.1, "목표", color="red", fontsize=9, alpha=0.8)

# v1.0 baseline 점수 주석 (M1과 같음 — v1.0 공식 수치는 10/10이었으나 본 측정 재현 기준)
ax1.annotate(
    "v1.0 공식\n10/10",
    xy=(0, pass_counts[0]),
    xytext=(0.35, pass_counts[0] + 0.5),
    fontsize=8, color="gray",
    arrowprops=dict(arrowstyle="->", color="gray", lw=0.8),
)

plt.tight_layout()
out1 = OUT_DIR / "v2_pass_by_mode.png"
fig1.savefig(out1, dpi=150, bbox_inches="tight")
print(f"저장: {out1}")
plt.close(fig1)


# ─── Chart 2: MRR 막대 차트 ─────────────────────────────────
fig2, ax2 = plt.subplots(figsize=(8, 5))

mrr_values = [summaries[m]["mrr"] for m in mode_ids]
bars_mrr = ax2.bar(x, mrr_values, width, color=[COLORS[m] for m in mode_ids], alpha=0.9)

for bar, mrr in zip(bars_mrr, mrr_values):
    ax2.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 0.01,
        f"{mrr:.4f}",
        ha="center", va="bottom",
        fontsize=11, fontweight="bold",
    )

ax2.set_xticks(x)
ax2.set_xticklabels([MODE_LABELS[m] for m in mode_ids], fontsize=10)
ax2.set_ylabel("MRR (Mean Reciprocal Rank)", fontsize=11)
ax2.set_title("모드별 MRR (T5 NA 제외 10쿼리)", fontsize=13, fontweight="bold")
ax2.set_ylim(0, 1.15)

# v1.0 baseline MRR 수평선 (M1 MRR 기준)
v1_mrr = mrr_values[0]
ax2.axhline(y=v1_mrr, color="gray", linestyle="--", linewidth=1.0, alpha=0.5)
ax2.text(3.5, v1_mrr + 0.01, f"v1.0 MRR\n{v1_mrr:.4f}", color="gray", fontsize=8, ha="right")

plt.tight_layout()
out2 = OUT_DIR / "v2_mrr_by_mode.png"
fig2.savefig(out2, dpi=150, bbox_inches="tight")
print(f"저장: {out2}")
plt.close(fig2)


# ─── Chart 3: Latency p50/p95 그룹 막대 차트 ────────────────
fig3, ax3 = plt.subplots(figsize=(9, 5))

p50_vals = [latency_summaries[m]["p50_ms"] for m in mode_ids]
p95_vals = [latency_summaries[m]["p95_ms"] for m in mode_ids]

bar_w = 0.35
x_p50 = x - bar_w / 2
x_p95 = x + bar_w / 2

bars_p50 = ax3.bar(x_p50, p50_vals, bar_w, label="p50", color=[COLORS[m] for m in mode_ids], alpha=0.85)
bars_p95 = ax3.bar(x_p95, p95_vals, bar_w, label="p95", color=[COLORS[m] for m in mode_ids], alpha=0.5, hatch="//")

for bar, val in zip(bars_p50, p50_vals):
    ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 20, f"{val}", ha="center", va="bottom", fontsize=9)
for bar, val in zip(bars_p95, p95_vals):
    ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 20, f"{val}", ha="center", va="bottom", fontsize=9)

# +30% 목표선 (v1.0 baseline p95 × 1.3)
# M1 p95를 baseline으로 사용
v1_p95 = p95_vals[0]
threshold_30pct = int(v1_p95 * 1.3)
ax3.axhline(y=threshold_30pct, color="red", linestyle="--", linewidth=1.2, alpha=0.7)
ax3.text(3.5, threshold_30pct + 30, f"+30% 목표\n{threshold_30pct}ms", color="red", fontsize=8, ha="right")

ax3.set_xticks(x)
ax3.set_xticklabels([MODE_LABELS[m] for m in mode_ids], fontsize=10)
ax3.set_ylabel("Latency (ms)", fontsize=11)
ax3.set_title("모드별 Latency p50 / p95 (warm cache, 각 3회 평균)", fontsize=13, fontweight="bold")
ax3.legend(loc="upper right", fontsize=10)

plt.tight_layout()
out3 = OUT_DIR / "v2_latency_by_mode.png"
fig3.savefig(out3, dpi=150, bbox_inches="tight")
print(f"저장: {out3}")
plt.close(fig3)

print("\n차트 3장 생성 완료.")
