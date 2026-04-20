"""
GitHub Social Preview Image Generator (1280×640 PNG)
Output: docs/social_preview.png

업로드 방법:
    GitHub repo → Settings → General → Social preview → Edit → Upload image
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "social_preview.png"
OUT.parent.mkdir(parents=True, exist_ok=True)

mpl.rcParams["font.family"] = ["AppleGothic", "Arial Unicode MS", "DejaVu Sans"]
mpl.rcParams["axes.unicode_minus"] = False

BG = "#0D1117"
ACCENT = "#1F6FEB"
ACCENT_SOFT = "#58A6FF"
TEXT = "#F0F6FC"
MUTED = "#8B949E"
CARD_BG = "#161B22"
CARD_BORDER = "#30363D"
POSITIVE = "#3FB950"

# 1280×640 @ 100 dpi
fig, ax = plt.subplots(figsize=(12.8, 6.4), dpi=100)
ax.set_xlim(0, 12.8)
ax.set_ylim(0, 6.4)
ax.set_facecolor(BG)
fig.patch.set_facecolor(BG)
ax.set_axis_off()

# 좌측 상단 accent bar + caption
ax.add_patch(Rectangle((0, 5.85), 0.18, 0.55, color=ACCENT, zorder=2))
ax.text(0.45, 6.12, "vet-snomed-rag", fontsize=13, color=MUTED,
        va="center", family="monospace")
ax.text(12.35, 6.12, "v1.0 · MIT License", fontsize=11, color=ACCENT_SOFT,
        va="center", ha="right", fontweight="bold")

# 타이틀 (영문, 한 줄)
ax.text(
    0.5, 5.2,
    "Hybrid RAG for Veterinary SNOMED CT",
    fontsize=36,
    color=TEXT,
    fontweight="bold",
    va="center",
)

# 부제 (한국어)
ax.text(
    0.5, 4.55,
    "수의학 SNOMED CT 온톨로지 · 한국어 자연어 질의 · Gemini Reformulator",
    fontsize=14.5,
    color=MUTED,
    va="center",
)

# 수치 카드 3개 — 중단 가로 배치
def draw_card(x, y, w, h, big, label):
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.05,rounding_size=0.18",
        linewidth=1.4,
        edgecolor=CARD_BORDER,
        facecolor=CARD_BG,
        zorder=1,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h * 0.63, big, fontsize=32, color=POSITIVE,
            fontweight="bold", ha="center", va="center")
    ax.text(x + w / 2, y + h * 0.22, label, fontsize=11.5, color=MUTED,
            ha="center", va="center")


card_w = 3.7
card_h = 1.7
card_y = 2.25
total_w = card_w * 3 + 0.35 * 2
card_x0 = (12.8 - total_w) / 2

draw_card(card_x0,                       card_y, card_w, card_h, "10/10",  "PASS rate (was 6/10)")
draw_card(card_x0 + (card_w + 0.35),     card_y, card_w, card_h, "−14.7%", "Avg latency")
draw_card(card_x0 + (card_w + 0.35) * 2, card_y, card_w, card_h, "414K",   "SNOMED concepts")

# 하단 기술 스택 — 단일 라인 텍스트 (chip UI 제거, 잘림 방지)
stack_line = "ChromaDB  ·  SQLite + RRF  ·  Ollama  ·  Claude Sonnet  ·  Gemini 2.5  ·  Streamlit"
ax.text(6.4, 1.15, stack_line,
        fontsize=13, color=ACCENT_SOFT, ha="center", va="center",
        fontweight="medium")

# Footer URL
ax.text(6.4, 0.4, "github.com/ricocopapa/vet-snomed-rag",
        fontsize=12, color=MUTED, va="center", ha="center", family="monospace")

plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
fig.savefig(OUT, dpi=100, facecolor=BG, bbox_inches=None, pad_inches=0)
plt.close(fig)

print("=== Social preview generated ===")
print(f"Output: {OUT}")
