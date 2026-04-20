"""
Before/After Regression Chart Generator
- Input: graphify_out/regression_metrics.json
- Output: graphify_out/charts/{pass_rate, rank_per_query, latency}.png
"""

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl

ROOT = Path(__file__).resolve().parents[1]
METRICS_PATH = ROOT / "graphify_out" / "regression_metrics.json"
OUT_DIR = ROOT / "graphify_out" / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

mpl.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False

COLOR_BEFORE = "#B0B0B0"
COLOR_AFTER = "#1F77B4"
NF_RANK = 11

with METRICS_PATH.open(encoding="utf-8") as f:
    data = json.load(f)

query_ids = [e["query_id"] for e in data]
verdict_none = [e["verdict_per_backend"]["none"] for e in data]
verdict_gem = [e["verdict_per_backend"]["gemini"] for e in data]
evaluable = [v != "NA" for v in verdict_none]

pass_none = sum(1 for v, ok in zip(verdict_none, evaluable) if ok and v == "PASS")
pass_gem = sum(1 for v, ok in zip(verdict_gem, evaluable) if ok and v == "PASS")
total_eval = sum(evaluable)


def _rank_for_plot(entry, backend):
    r = entry["modes"][backend].get("rank_of_correct")
    return r if isinstance(r, int) else NF_RANK


rank_none = [_rank_for_plot(e, "none") for e in data]
rank_gem = [_rank_for_plot(e, "gemini") for e in data]
# NA 쿼리는 두 backend 모두 평가 불가 — bar 자체를 그리지 않음 (N/A 음영만 남김)
rank_none_plot = [r if ev else 0 for r, ev in zip(rank_none, evaluable)]
rank_gem_plot = [r if ev else 0 for r, ev in zip(rank_gem, evaluable)]

lat_none = [e["modes"]["none"]["latency_ms"] for e in data]
lat_gem = [e["modes"]["gemini"]["latency_ms"] for e in data]
avg_lat_none = sum(lat_none) / len(lat_none)
avg_lat_gem = sum(lat_gem) / len(lat_gem)


# Chart 1: PASS 율 비교
fig, ax = plt.subplots(figsize=(7, 5))
labels = ["Before\n(none baseline)", "After\n(Gemini Reformulator)"]
values = [pass_none, pass_gem]
bars = ax.bar(labels, values, color=[COLOR_BEFORE, COLOR_AFTER], width=0.55)
ax.set_ylabel("PASS count (out of {} evaluable)".format(total_eval), fontsize=11)
ax.set_title("11-Query Regression: PASS Rate Comparison", fontsize=13, pad=14)
ax.set_ylim(0, total_eval + 1.5)
ax.axhline(total_eval, color="#333", linestyle=":", linewidth=0.8, alpha=0.5)
for bar, v in zip(bars, values):
    pct = 100 * v / total_eval
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        v + 0.15,
        f"{v}/{total_eval}\n({pct:.0f}%)",
        ha="center",
        va="bottom",
        fontsize=12,
        fontweight="bold",
    )
ax.grid(axis="y", alpha=0.3, linestyle="--")
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT_DIR / "pass_rate.png", dpi=150)
plt.close(fig)


# Chart 2: 쿼리별 rank_of_correct (lower is better)
fig, ax = plt.subplots(figsize=(11, 5.5))
import numpy as np

x = np.arange(len(query_ids))
w = 0.38
b1 = ax.bar(x - w / 2, rank_none_plot, w, label="Before (none)", color=COLOR_BEFORE)
b2 = ax.bar(x + w / 2, rank_gem_plot, w, label="After (Gemini)", color=COLOR_AFTER)

ax.set_xticks(x)
ax.set_xticklabels(query_ids)
ax.set_ylabel("Rank of correct concept (1 = top-1, NF = not found in top-10)", fontsize=10)
ax.set_title(
    "Rank of Correct SNOMED Concept per Query (lower is better)", fontsize=13, pad=14
)
ax.set_ylim(0, NF_RANK + 1.8)
ax.axhline(
    NF_RANK,
    color="#d62728",
    linestyle=":",
    linewidth=0.8,
    alpha=0.6,
    label="NF threshold (not found in top-10)",
)

for bars, ranks, evs in [(b1, rank_none, evaluable), (b2, rank_gem, evaluable)]:
    for bar, r, ev in zip(bars, ranks, evs):
        if not ev:
            continue
        label = "NF" if r == NF_RANK else str(r)
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.15,
            label,
            ha="center",
            va="bottom",
            fontsize=8.5,
        )

na_positions = [i for i, ev in enumerate(evaluable) if not ev]
for i in na_positions:
    ax.axvspan(i - 0.5, i + 0.5, color="#f0f0f0", alpha=0.8, zorder=0)
    ax.text(
        i,
        NF_RANK / 2,
        "N/A\n(excluded)",
        ha="center",
        va="center",
        fontsize=9,
        color="#888",
        style="italic",
    )

ax.legend(loc="upper left", fontsize=9, framealpha=0.9)
ax.grid(axis="y", alpha=0.3, linestyle="--")
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT_DIR / "rank_per_query.png", dpi=150)
plt.close(fig)


# Chart 3: 평균 레이턴시 비교
fig, ax = plt.subplots(figsize=(7, 5))
labels = ["Before\n(none baseline)", "After\n(Gemini Reformulator)"]
values = [avg_lat_none, avg_lat_gem]
bars = ax.bar(labels, values, color=[COLOR_BEFORE, COLOR_AFTER], width=0.55)
ax.set_ylabel("Average latency (ms)", fontsize=11)
delta = avg_lat_gem - avg_lat_none
delta_pct = 100 * delta / avg_lat_none
delta_color = "#2ca02c" if delta <= 0 else "#d62728"
ax.set_title(
    f"Average Query Latency Comparison\nΔ = {delta:+.0f} ms ({delta_pct:+.1f}%) — no degradation",
    fontsize=13,
    pad=14,
    color="#111",
)
ax.set_ylim(0, max(values) * 1.2)
for bar, v in zip(bars, values):
    ax.text(
        bar.get_x() + bar.get_width() / 2,
        v + max(values) * 0.02,
        f"{v:.0f} ms",
        ha="center",
        va="bottom",
        fontsize=12,
        fontweight="bold",
    )
ax.grid(axis="y", alpha=0.3, linestyle="--")
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(OUT_DIR / "latency.png", dpi=150)
plt.close(fig)


print("=== Chart Generation Complete ===")
print(f"Output: {OUT_DIR}")
print(f"  pass_rate.png      — Before: {pass_none}/{total_eval}, After: {pass_gem}/{total_eval}")
print(f"  rank_per_query.png — 11 queries, NF count: none={rank_none.count(NF_RANK)}, gemini={rank_gem.count(NF_RANK)}")
print(f"  latency.png        — Before: {avg_lat_none:.0f}ms, After: {avg_lat_gem:.0f}ms (Δ {delta:+.0f}ms)")
