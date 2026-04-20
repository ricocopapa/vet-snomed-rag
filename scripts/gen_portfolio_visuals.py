#!/usr/bin/env python3
"""
Portfolio Visual Generator — LG CNS 지원용 시각 자료 3종.

A1: 시스템 아키텍처 1-page 인포그래픽 (3-Track Retrieval + Dual Backend + 3단 검증)
A2: 3단 에이전트 검증 파이프라인 다이어그램
A3: SOAP 4축 SNOMED 매핑 커버리지 대시보드

출력: graphify_out/portfolio/{A1_architecture,A2_verification,A3_coverage}.png
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

# 한글 폰트 설정 (macOS)
mpl.rcParams["font.family"] = ["Apple SD Gothic Neo", "AppleGothic", "Noto Sans KR", "Nanum Gothic"]
mpl.rcParams["axes.unicode_minus"] = False

OUT_DIR = Path(__file__).resolve().parent.parent / "graphify_out" / "portfolio"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- 색상 팔레트 (LG 톤 호환) ---
C_DARK = "#1F2937"
C_ACCENT = "#A50034"   # LG 마젠타
C_BLUE = "#0064B3"
C_TEAL = "#0D9488"
C_AMBER = "#D97706"
C_SUCCESS = "#059669"
C_GRAY = "#6B7280"
C_LIGHT = "#F8FAFC"
C_BORDER = "#CBD5E1"
C_CARD = "#FFFFFF"


def _box(ax, xy, w, h, label, *,
         facecolor=C_CARD, edgecolor=C_BORDER, textcolor=C_DARK,
         fontsize=10, fontweight="normal", lw=1.5, radius=0.08):
    x, y = xy
    box = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.02,rounding_size={radius}",
        linewidth=lw, edgecolor=edgecolor, facecolor=facecolor,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, label,
            ha="center", va="center",
            color=textcolor, fontsize=fontsize, fontweight=fontweight,
            wrap=True)
    return (x + w / 2, y + h / 2, x, y, w, h)


def _arrow(ax, start, end, *, color=C_GRAY, lw=1.8, style="-|>", mutation_scale=16):
    arrow = FancyArrowPatch(
        start, end,
        arrowstyle=style, mutation_scale=mutation_scale,
        color=color, linewidth=lw, shrinkA=4, shrinkB=4,
    )
    ax.add_patch(arrow)


# ==================================================================
# A1: System Architecture 1-page
# ==================================================================
def draw_a1():
    fig, ax = plt.subplots(figsize=(16, 10), dpi=180)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    # 제목
    ax.text(8, 9.55, "vet-snomed-rag — System Architecture",
            ha="center", va="center",
            fontsize=18, fontweight="bold", color=C_DARK)
    ax.text(8, 9.15,
            "Hybrid RAG × Dual Backend × 3-Stage Agent Verification",
            ha="center", va="center",
            fontsize=11, color=C_GRAY, style="italic")

    # Layer 1: Input
    _box(ax, (0.5, 7.8), 3.0, 0.8,
         "사용자 질의\n(한국어 / 영어)",
         facecolor="#FEF3C7", edgecolor=C_AMBER, fontsize=10, fontweight="bold")

    # Layer 2: Dual Backend Reformulator
    _box(ax, (4.0, 7.6), 4.5, 1.2,
         "Dual Backend Query Reformulator\n(Strategy Pattern · L2 Cache 분리)",
         facecolor="#E0F2FE", edgecolor=C_BLUE, fontsize=10, fontweight="bold")
    _box(ax, (4.15, 7.7), 2.05, 0.5,
         "Gemini 2.5 Flash (Primary)",
         facecolor=C_CARD, edgecolor=C_BLUE, fontsize=8)
    _box(ax, (6.30, 7.7), 2.05, 0.5,
         "Claude Sonnet 4.6 (Optional)",
         facecolor=C_CARD, edgecolor=C_BLUE, fontsize=8)

    # Layer 3: 3-Track Hybrid Retrieval
    _box(ax, (0.5, 5.4), 8.0, 1.7,
         "",
         facecolor="#FDF2F8", edgecolor=C_ACCENT, lw=2)
    ax.text(4.5, 6.85, "3-Track Hybrid Retrieval",
            ha="center", fontsize=11, fontweight="bold", color=C_ACCENT)

    _box(ax, (0.75, 5.6), 2.4, 1.05,
         "Track A · Vector\nChromaDB\n414,848 concepts",
         facecolor=C_CARD, edgecolor=C_ACCENT, fontsize=9)
    _box(ax, (3.30, 5.6), 2.4, 1.05,
         "Track B · SQL\nSQLite\nRF2 Reference DB",
         facecolor=C_CARD, edgecolor=C_ACCENT, fontsize=9)
    _box(ax, (5.85, 5.6), 2.4, 1.05,
         "Track C · RRF\nReciprocal Rank\nFusion (k=60)",
         facecolor=C_CARD, edgecolor=C_ACCENT, fontsize=9)

    # Layer 4: Context Assembly
    _box(ax, (0.5, 3.8), 8.0, 1.2,
         "Context Assembly\n(Top-K 검색 결과 + is-a 관계 + Post-Coordination 877 표현식)",
         facecolor="#ECFDF5", edgecolor=C_TEAL, fontsize=10, fontweight="bold")

    # Layer 5: Generation
    _box(ax, (0.5, 2.0), 8.0, 1.2,
         "LLM Generation — Claude API (sonnet-4) / Ollama (local)\n구조화된 답변: concept_id, FSN, Post-coord, 매핑 상태",
         facecolor="#DBEAFE", edgecolor=C_BLUE, fontsize=10, fontweight="bold")

    # 우측 컬럼: Verification Layer
    _box(ax, (9.2, 2.0), 6.3, 7.0,
         "", facecolor="#FEF2F2", edgecolor=C_ACCENT, lw=2, radius=0.1)
    ax.text(12.35, 8.7, "Verification Layer",
            ha="center", fontsize=12, fontweight="bold", color=C_ACCENT)
    ax.text(12.35, 8.35,
            "3단 에이전트 독립 검증",
            ha="center", fontsize=9, color=C_GRAY, style="italic")

    _box(ax, (9.5, 7.2), 5.7, 0.9,
         "Agent B — Code Knowledge Graph\ngraphify_lite · 209 nodes / 458 edges",
         facecolor=C_CARD, edgecolor=C_ACCENT, fontsize=9, fontweight="bold")
    _box(ax, (9.5, 5.9), 5.7, 0.9,
         "Agent A — Implementation & Regression\n11-query test · Before/After metrics",
         facecolor=C_CARD, edgecolor=C_ACCENT, fontsize=9, fontweight="bold")
    _box(ax, (9.5, 4.6), 5.7, 0.9,
         "Agent C — Independent Reviewer\n설계-구현 역방향 동기화 (v1.2 → v1.2.1)",
         facecolor=C_CARD, edgecolor=C_ACCENT, fontsize=9, fontweight="bold")

    _box(ax, (9.5, 2.4), 5.7, 1.8,
         "Output Quality Gate O1~O12\n"
         "Source-First · DB-Authoritative · CoVe\n"
         "Adversarial Verification (Layer A / B)\n"
         "Feedback Memory Protocol",
         facecolor="#FEE2E2", edgecolor=C_ACCENT, fontsize=9, fontweight="bold")

    # 세로 화살표 (왼쪽 컬럼)
    _arrow(ax, (4.75, 7.6), (4.5, 7.1), color=C_DARK)
    _arrow(ax, (4.5, 5.4), (4.5, 5.0), color=C_DARK)
    _arrow(ax, (4.5, 3.8), (4.5, 3.2), color=C_DARK)

    # 가로 화살표 (Input → Reformulator)
    _arrow(ax, (3.5, 8.2), (4.0, 8.2), color=C_DARK)

    # 수평 연결 (Retrieval → Verification)
    _arrow(ax, (8.5, 6.25), (9.2, 6.25), color=C_ACCENT, lw=2, style="-|>")

    # 하단 배너 — 핵심 지표
    banner = FancyBboxPatch((0.5, 0.4), 15.0, 1.2,
                            boxstyle="round,pad=0.02,rounding_size=0.12",
                            linewidth=2, edgecolor=C_DARK, facecolor=C_DARK)
    ax.add_patch(banner)
    ax.text(4.0, 1.0,
            "11-쿼리 회귀\n10/10 PASS",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#FCD34D")
    ax.text(8.0, 1.0,
            "Latency\n−14.7%  (1,247→1,063 ms)",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#86EFAC")
    ax.text(12.0, 1.0,
            "Cost\n~$0.00000128 / query",
            ha="center", va="center", fontsize=11, fontweight="bold", color="#93C5FD")

    # 데이터 규모 요약 (하단 왼쪽)
    ax.text(0.5, 0.1,
            "SNOMED CT  INT 378,938 + VET 35,910 = 414,848 concepts  ·  "
            "Relationships 1,379,816  ·  Post-Coord 877 (A 346 + P 495 + O 36)",
            ha="left", va="center", fontsize=8, color=C_GRAY, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "A1_system_architecture.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# A2: 3-Stage Verification Pipeline
# ==================================================================
def draw_a2():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=180)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    ax.text(8, 8.55,
            "3-Stage Agent Verification Pipeline",
            ha="center", fontsize=18, fontweight="bold", color=C_DARK)
    ax.text(8, 8.15,
            "Agent B (Graph Analysis) → Agent A (Implementation) → Agent C (Independent Review) + 역방향 동기화",
            ha="center", fontsize=10, color=C_GRAY, style="italic")

    # Agent B
    _box(ax, (0.5, 5.4), 4.5, 2.2, "", facecolor="#EEF2FF", edgecolor=C_BLUE, lw=2, radius=0.1)
    ax.text(2.75, 7.35, "Agent B", ha="center", fontsize=13, fontweight="bold", color=C_BLUE)
    ax.text(2.75, 7.00, "Code Knowledge Graph Analyzer",
            ha="center", fontsize=9, color=C_GRAY, style="italic")
    ax.text(2.75, 6.55, "• graphify_lite 자체 구현", ha="center", fontsize=9, color=C_DARK)
    ax.text(2.75, 6.25, "• 209 nodes / 458 edges 추출", ha="center", fontsize=9, color=C_DARK)
    ax.text(2.75, 5.95, "• 의심 지점 자동 탐지", ha="center", fontsize=9, color=C_DARK)
    ax.text(2.75, 5.65, "• 대안 구조 Suggested Q 7개", ha="center", fontsize=9, color=C_DARK)

    # Agent A
    _box(ax, (5.75, 5.4), 4.5, 2.2, "", facecolor="#FEF3C7", edgecolor=C_AMBER, lw=2, radius=0.1)
    ax.text(8.0, 7.35, "Agent A", ha="center", fontsize=13, fontweight="bold", color=C_AMBER)
    ax.text(8.0, 7.00, "Implementation & Regression",
            ha="center", fontsize=9, color=C_GRAY, style="italic")
    ax.text(8.0, 6.55, "• Strategy Pattern Dual Backend 구현", ha="center", fontsize=9, color=C_DARK)
    ax.text(8.0, 6.25, "• 11-쿼리 회귀 테스트 자동화", ha="center", fontsize=9, color=C_DARK)
    ax.text(8.0, 5.95, "• Before/After 메트릭 수집", ha="center", fontsize=9, color=C_DARK)
    ax.text(8.0, 5.65, "• 6/10 → 10/10 PASS 달성", ha="center", fontsize=9, color=C_DARK)

    # Agent C
    _box(ax, (11.0, 5.4), 4.5, 2.2, "", facecolor="#FEE2E2", edgecolor=C_ACCENT, lw=2, radius=0.1)
    ax.text(13.25, 7.35, "Agent C", ha="center", fontsize=13, fontweight="bold", color=C_ACCENT)
    ax.text(13.25, 7.00, "Independent Reviewer",
            ha="center", fontsize=9, color=C_GRAY, style="italic")
    ax.text(13.25, 6.55, "• 설계서 ↔ 구현체 정합성 감사", ha="center", fontsize=9, color=C_DARK)
    ax.text(13.25, 6.25, "• feedback_execution_conformity 검증", ha="center", fontsize=9, color=C_DARK)
    ax.text(13.25, 5.95, "• 결함 근본 원인 분석 (5-Why)", ha="center", fontsize=9, color=C_DARK)
    ax.text(13.25, 5.65, "• 역방향 동기화 권고 발행", ha="center", fontsize=9, color=C_DARK)

    # 에이전트 간 화살표
    _arrow(ax, (5.0, 6.5), (5.75, 6.5), color=C_DARK, lw=2.5, style="-|>", mutation_scale=20)
    _arrow(ax, (10.25, 6.5), (11.0, 6.5), color=C_DARK, lw=2.5, style="-|>", mutation_scale=20)

    # 산출물 레이어
    _box(ax, (0.5, 3.5), 4.5, 1.3,
         "산출물\ngraph.html · graph.png\nnodes.csv · edges.csv\nreport.md · cache.json",
         facecolor=C_CARD, edgecolor=C_BLUE, fontsize=9)
    _box(ax, (5.75, 3.5), 4.5, 1.3,
         "산출물\nregression_metrics.json (11 entries)\nbackend_comparison.md\ncharts/latency · pass_rate · rank",
         facecolor=C_CARD, edgecolor=C_AMBER, fontsize=9)
    _box(ax, (11.0, 3.5), 4.5, 1.3,
         "산출물\nreview_report.md (10.8 KB)\nDESIGN_PATCH_v1.2.1.md\n감사 결과 FLAG 5건",
         facecolor=C_CARD, edgecolor=C_ACCENT, fontsize=9)

    # 수직 화살표
    for x in [2.75, 8.0, 13.25]:
        _arrow(ax, (x, 5.4), (x, 4.8), color=C_GRAY, lw=1.5, style="-|>")

    # 역방향 동기화 루프 (하단)
    _box(ax, (0.5, 1.3), 15.0, 1.5,
         "",
         facecolor="#1F2937", edgecolor=C_ACCENT, lw=2, radius=0.1)
    ax.text(8.0, 2.5,
            "↓  설계-구현 역방향 동기화 루프  ↓",
            ha="center", fontsize=11, fontweight="bold", color="#FCD34D")
    ax.text(8.0, 2.05,
            "설계서 v1.2 → 구현 Deviation 발견 → Agent C 권고 → 설계서 v1.2.1 확정",
            ha="center", fontsize=10, color="#E5E7EB")
    ax.text(8.0, 1.65,
            "Output Quality Gate O1~O12 · Source-First · DB-Authoritative · CoVe · Feedback Memory Protocol",
            ha="center", fontsize=9, color="#9CA3AF", style="italic")

    # Agent C → 루프 화살표
    _arrow(ax, (13.25, 3.5), (13.25, 2.8), color=C_ACCENT, lw=2, style="-|>")
    # 루프 → Agent A 화살표 (피드백 업스트림)
    _arrow(ax, (8.0, 2.8), (8.0, 3.5), color="#FCD34D", lw=2, style="-|>")

    # 하단 뱃지 — JD 매칭
    ax.text(0.5, 0.5,
            "LG CNS JD 매칭: 우대 3.2 — AI 품질·운영·안정성 체계 (Evaluation · Observability · Guardrails · PII)",
            ha="left", fontsize=9, fontweight="bold", color=C_ACCENT, style="italic")
    ax.text(0.5, 0.15,
            "근거 파일: graphify_out/{report.md, regression_metrics.json, review_report.md}  ·  설계서 v1.2.1",
            ha="left", fontsize=8, color=C_GRAY, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "A2_verification_pipeline.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# A3: SOAP 4-Axis SNOMED Coverage Dashboard
# ==================================================================
def draw_a3():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=180)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    ax.text(8, 8.55,
            "SOAP 4-Axis · SNOMED CT VET Extension Mapping Coverage",
            ha="center", fontsize=17, fontweight="bold", color=C_DARK)
    ax.text(8, 8.15,
            "국제 표준 의료 온톨로지 기반 수의 EMR 데이터 아키텍처 실증",
            ha="center", fontsize=10, color=C_GRAY, style="italic")

    # 4축 progress bar
    axes_data = [
        {
            "label": "S축 — Symptom",
            "version": "v23.7.1",
            "pct_main": 100.0, "pct_sub": None,
            "detail": "Pattern A · field 375 + enum 329",
            "color": C_SUCCESS,
        },
        {
            "label": "O축 — Observation",
            "version": "v23 E73 Naming Refactor",
            "pct_main": 94.8, "pct_sub": None,
            "detail": "exam_meta_item 4,231 active",
            "color": C_TEAL,
        },
        {
            "label": "A축 — Assessment",
            "version": "v8 (2026-04-06)",
            "pct_main": 100.0, "pct_sub": None,
            "detail": "LOCAL 1,451 → 0 전수 해소 · 사전조합 189 + 후조합 1,262",
            "color": C_ACCENT,
        },
        {
            "label": "P축 — Plan",
            "version": "v3.4 (Wave12 Gemini Audit)",
            "pct_main": 99.53, "pct_sub": 96.96,
            "detail": "TX 99.53% · RX 96.96%",
            "color": C_BLUE,
        },
    ]

    # Progress bar area
    y_start = 7.0
    row_h = 1.2
    for i, d in enumerate(axes_data):
        y = y_start - i * row_h
        # 라벨
        ax.text(0.5, y + 0.45, d["label"],
                fontsize=12, fontweight="bold", color=C_DARK)
        ax.text(0.5, y + 0.12, d["version"],
                fontsize=9, color=C_GRAY, style="italic")

        # 배경 바
        bar_x, bar_y, bar_w, bar_h = 4.2, y, 8.0, 0.55
        _box(ax, (bar_x, bar_y), bar_w, bar_h, "",
             facecolor="#E5E7EB", edgecolor=C_BORDER, radius=0.05, lw=0.8)

        # 진행 바
        fill_w = bar_w * (d["pct_main"] / 100.0)
        _box(ax, (bar_x, bar_y), fill_w, bar_h, "",
             facecolor=d["color"], edgecolor=d["color"], radius=0.05, lw=0)

        # 퍼센트 텍스트
        pct_text = f'{d["pct_main"]:.2f}%'
        if d["pct_sub"] is not None:
            pct_text = f'TX {d["pct_main"]:.2f}% · RX {d["pct_sub"]:.2f}%'
        ax.text(bar_x + bar_w + 0.15, bar_y + bar_h / 2,
                pct_text, fontsize=11, fontweight="bold",
                color=d["color"], va="center")

        # 세부 설명
        ax.text(4.2, y - 0.15, d["detail"],
                fontsize=9, color=C_GRAY)

    # 하단 통계 카드 3개
    card_y = 1.2
    card_h = 1.1
    cards = [
        ("35,910", "VET Extension\nactive concepts", C_ACCENT),
        ("877", "Post-Coordination\n표현식 (A 346 + P 495 + O 36)", C_BLUE),
        ("8,651+", "전체 SNOMED CT VET\n매핑 수행", C_TEAL),
    ]
    for i, (big, label, color) in enumerate(cards):
        x0 = 0.5 + i * 5.17
        w = 4.83
        _box(ax, (x0, card_y), w, card_h, "",
             facecolor=C_CARD, edgecolor=color, lw=2, radius=0.08)
        ax.text(x0 + w / 2, card_y + card_h - 0.4, big,
                ha="center", fontsize=24, fontweight="bold", color=color)
        ax.text(x0 + w / 2, card_y + 0.28, label,
                ha="center", fontsize=10, color=C_DARK)

    # 하단 태그
    ax.text(0.5, 0.55,
            "LG CNS JD 매칭: 우대 3.4 Data Architecture · 우대 3.6 도메인 경험  |  K-AI 제약 프로젝트 연결 가능",
            ha="left", fontsize=9, fontweight="bold", color=C_ACCENT, style="italic")
    ax.text(0.5, 0.2,
            "출처: project_p_axis_snomed · project_a_axis_snomed · project_s_axis_v23.3 · project_o_axis_progress (MEMORY.md)",
            ha="left", fontsize=8, color=C_GRAY, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "A3_soap_coverage.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# B1: Enterprise Integration Layer (VetSTT → Whisper → SNOMED → EMR)
# ==================================================================
def draw_b1():
    fig, ax = plt.subplots(figsize=(17, 9), dpi=180)
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 9)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    ax.text(8.5, 8.55, "Enterprise Integration Layer — VetSTT → EMR",
            ha="center", fontsize=18, fontweight="bold", color=C_DARK)
    ax.text(8.5, 8.15,
            "이기종 4+개 시스템 연계 파이프라인 · 음성 녹취에서 SNOMED 기반 EMR 필드까지",
            ha="center", fontsize=10, color=C_GRAY, style="italic")

    # 5단계 파이프라인
    stages = [
        {
            "label": "① 음성 입력", "title": "Audio Capture",
            "tech": "mic / recording\nWAV / MP3",
            "system": "Clinical Workstation",
            "color": C_AMBER, "bg": "#FEF3C7",
        },
        {
            "label": "② STT 변환", "title": "Whisper STT",
            "tech": "OpenAI Whisper\nlarge-v3 (KR/EN)",
            "system": "STT Engine",
            "color": C_BLUE, "bg": "#DBEAFE",
        },
        {
            "label": "③ 도메인 탐지", "title": "Domain Classifier",
            "tech": "25+ domain ontology\nkeyword + embedding",
            "system": "AI Layer",
            "color": C_TEAL, "bg": "#CCFBF1",
        },
        {
            "label": "④ SNOMED 매핑", "title": "Concept Matcher",
            "tech": "vet-snomed-rag\nHybrid Retrieval",
            "system": "Terminology Service",
            "color": C_ACCENT, "bg": "#FCE7F3",
        },
        {
            "label": "⑤ EMR 필드", "title": "SOAP Schema Mapper",
            "tech": "S/O/A/P 4-axis\nfield 375 + enum 329",
            "system": "EMR Database",
            "color": C_SUCCESS, "bg": "#D1FAE5",
        },
    ]

    box_w = 2.8
    box_h = 2.4
    gap = 0.45
    x_start = 0.4

    for i, s in enumerate(stages):
        x = x_start + i * (box_w + gap)
        # 상단 라벨
        ax.text(x + box_w / 2, 6.9, s["label"],
                ha="center", fontsize=10, fontweight="bold", color=s["color"])
        # 박스
        _box(ax, (x, 4.3), box_w, 2.4, "",
             facecolor=s["bg"], edgecolor=s["color"], lw=2, radius=0.08)
        ax.text(x + box_w / 2, 6.25, s["title"],
                ha="center", fontsize=11, fontweight="bold", color=C_DARK)
        ax.text(x + box_w / 2, 5.55, s["tech"],
                ha="center", fontsize=9, color=C_DARK)
        ax.text(x + box_w / 2, 4.65, f'[{s["system"]}]',
                ha="center", fontsize=8, color=C_GRAY, style="italic")

        # 화살표
        if i < len(stages) - 1:
            _arrow(ax,
                   (x + box_w + 0.02, 5.5),
                   (x + box_w + gap - 0.02, 5.5),
                   color=C_DARK, lw=2.5, style="-|>", mutation_scale=18)

    # 시스템 경계 배너 (상단)
    ax.text(0.4, 7.45, "시스템 경계 (System Boundary)",
            ha="left", fontsize=10, fontweight="bold", color=C_DARK)
    boundaries = [
        (0.4, 3.25, "Local Workstation"),
        (3.65, 3.25, "STT Cloud / Local"),
        (6.90, 3.25, "AI Routing Engine"),
        (10.15, 3.25, "Terminology DB"),
        (13.40, 3.25, "EMR RDBMS"),
    ]
    for (x, w, lbl) in boundaries:
        _box(ax, (x, 7.15), 2.8, 0.25, "",
             facecolor=C_DARK, edgecolor=C_DARK, radius=0.03, lw=0)
        ax.text(x + 1.4, 7.27, lbl,
                ha="center", fontsize=8, fontweight="bold", color="#FCD34D")

    # 하단 데이터 흐름
    _box(ax, (0.4, 2.1), 16.2, 1.9, "",
         facecolor="#1F2937", edgecolor=C_ACCENT, lw=2, radius=0.1)
    ax.text(8.5, 3.75, "데이터 흐름 (Data Flow)",
            ha="center", fontsize=11, fontweight="bold", color="#FCD34D")
    flow_items = [
        ("Audio Buffer", "16kHz PCM"),
        ("Transcript", "KR/EN 혼합"),
        ("Domain Tag", "SOAP 4축"),
        ("Concept IDs", "SNOMED CT + Post-coord"),
        ("EMR Row", "field_code + value"),
    ]
    for i, (label, desc) in enumerate(flow_items):
        x = 1.4 + i * 3.25
        ax.text(x, 3.25, label, ha="center", fontsize=9, fontweight="bold", color="#93C5FD")
        ax.text(x, 2.85, desc, ha="center", fontsize=8, color="#E5E7EB")
        if i < 4:
            ax.annotate("", xy=(x + 2.5, 3.0), xytext=(x + 0.75, 3.0),
                        arrowprops=dict(arrowstyle="->", color="#FCD34D", lw=1.5))

    # 하단 JD 매칭 및 실측
    ax.text(0.4, 1.55,
            "실측 현황: 향남병원 101건 STT 변환 진행 · vetstt_lite.html 프로토타입 · vet_stt_pipeline.py 개발 패키지 구축",
            ha="left", fontsize=9, color=C_DARK)
    ax.text(0.4, 1.15,
            "LG CNS JD 매칭: 필수 1.3 Enterprise 시스템 아키텍처 · 기술 2.4 Enterprise IT 통합 · K-AI 제약(종근당 Agent 30개) 연결",
            ha="left", fontsize=9, fontweight="bold", color=C_ACCENT, style="italic")
    ax.text(0.4, 0.75,
            "증거 파일: 05_Output_Workspace/EMR/VetSTT_Developer_Package/{00_README, 01~05_*}",
            ha="left", fontsize=8, color=C_GRAY, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "B1_enterprise_integration.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# B2: Dual Backend Strategy Pattern
# ==================================================================
def draw_b2():
    fig, ax = plt.subplots(figsize=(16, 10), dpi=180)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 10)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    ax.text(8, 9.55, "Dual Backend Strategy Pattern",
            ha="center", fontsize=18, fontweight="bold", color=C_DARK)
    ax.text(8, 9.15,
            "query_reformulator.py 324 lines · 벤더 종속 제거 · L2 Cache 분리",
            ha="center", fontsize=10, color=C_GRAY, style="italic")

    # 중앙 상단: Client (rag_pipeline)
    _box(ax, (5.5, 7.5), 5.0, 1.1,
         "Client — rag_pipeline.py\n(Step 0.7: Query Reformulation)",
         facecolor="#DBEAFE", edgecolor=C_BLUE, fontsize=11, fontweight="bold", lw=2)

    # Strategy Interface (추상)
    _box(ax, (5.5, 5.8), 5.0, 1.1,
         "«interface» BackendStrategy\nreformulate(query) → dict",
         facecolor="#F1F5F9", edgecolor=C_DARK, fontsize=10, fontweight="bold",
         lw=2, textcolor=C_DARK)
    ax.text(8.0, 5.55, "(추상 타입 · abstract type)",
            ha="center", fontsize=8, color=C_GRAY, style="italic")

    # Client → Interface 화살표
    _arrow(ax, (8.0, 7.5), (8.0, 6.9), color=C_BLUE, lw=2.5, style="-|>")

    # Concrete Strategies 좌우 (하단에 명확히 분리 배치)
    # Gemini (좌)
    _box(ax, (0.5, 1.8), 5.5, 3.0, "",
         facecolor="#DCFCE7", edgecolor=C_SUCCESS, lw=2, radius=0.1)
    ax.text(3.25, 4.5, "GeminiReformulator", ha="center",
            fontsize=13, fontweight="bold", color=C_SUCCESS)
    ax.text(3.25, 4.20, "Primary · 기본 활성화",
            ha="center", fontsize=9, color=C_GRAY, style="italic")
    gemini_lines = [
        "• Model: gemini-2.5-flash",
        "• Free Tier 활용 (비용 최소화)",
        "• Prompt: 수의학 용어 보정 + 영어 번역",
        "• L2 Cache: reformulations_gemini.json",
        "• 11 entries · 4.1 KB · 재현 100%",
        "• 평균 비용: ~$0.00000128 / query",
    ]
    for i, line in enumerate(gemini_lines):
        ax.text(0.8, 3.80 - i * 0.32, line, fontsize=9, color=C_DARK)

    # Claude (우)
    _box(ax, (10.0, 1.8), 5.5, 3.0, "",
         facecolor="#FEE2E2", edgecolor=C_ACCENT, lw=2, radius=0.1)
    ax.text(12.75, 4.5, "ClaudeReformulator", ha="center",
            fontsize=13, fontweight="bold", color=C_ACCENT)
    ax.text(12.75, 4.20, "Optional · 고품질 대체",
            ha="center", fontsize=9, color=C_GRAY, style="italic")
    claude_lines = [
        "• Model: claude-sonnet-4-6",
        "• Prompt Caching (cache_control)",
        "• Prompt: Tool use 가능, 상세 해설",
        "• L2 Cache: reformulations_claude.json",
        "• 벤더 장애 시 즉시 스위칭",
        "• Backend 독립 벤치마크 지원",
    ]
    for i, line in enumerate(claude_lines):
        ax.text(10.3, 3.80 - i * 0.32, line, fontsize=9, color=C_DARK)

    # 상속 관계 점선 (Gemini/Claude 박스 상단 → Interface 박스 하단)
    ax.annotate("", xy=(6.5, 5.8), xytext=(3.25, 4.8),
                arrowprops=dict(arrowstyle="-|>", color=C_SUCCESS, lw=2, linestyle="dashed"))
    ax.annotate("", xy=(9.5, 5.8), xytext=(12.75, 4.8),
                arrowprops=dict(arrowstyle="-|>", color=C_ACCENT, lw=2, linestyle="dashed"))

    # 상속 라벨
    ax.text(5.1, 5.3, "«implements»", ha="center", fontsize=7,
            color=C_SUCCESS, style="italic", fontweight="bold")
    ax.text(10.9, 5.3, "«implements»", ha="center", fontsize=7,
            color=C_ACCENT, style="italic", fontweight="bold")

    # 하단 비교 테이블
    _box(ax, (0.5, 0.3), 15.0, 1.4, "",
         facecolor=C_CARD, edgecolor=C_BORDER, lw=1.2, radius=0.06)
    header_y = 1.45
    row1_y = 1.10
    row2_y = 0.75
    row3_y = 0.45
    cols = [
        ("Backend", 1.3), ("L2 Cache Key", 3.5),
        ("Entries", 6.0), ("Cost/Query", 7.8),
        ("Latency(avg)", 10.0), ("벤더 종속", 12.5),
        ("비고", 14.2),
    ]
    for (h, x) in cols:
        ax.text(x, header_y, h, ha="center", fontsize=9,
                fontweight="bold", color=C_DARK)
    # Gemini row
    for (v, x) in zip(["Gemini 2.5 Flash", "reformulations_gemini.json",
                       "11", "$0.00000128", "1,063 ms", "L2 분리", "Primary"],
                      [1.3, 3.5, 6.0, 7.8, 10.0, 12.5, 14.2]):
        ax.text(x, row1_y, v, ha="center", fontsize=8, color=C_SUCCESS)
    # Claude row
    for (v, x) in zip(["Claude Sonnet 4.6", "reformulations_claude.json",
                       "(설정 시)", "(backend 선택)", "(ANTHROPIC_API_KEY)", "L2 분리", "Optional"],
                      [1.3, 3.5, 6.0, 7.8, 10.0, 12.5, 14.2]):
        ax.text(x, row2_y, v, ha="center", fontsize=8, color=C_ACCENT)

    ax.text(0.5, 0.1,
            "LG CNS JD 매칭: 우대 3.1 멀티 벤더 LLM 아키텍처 · 기술 2.2 모델 운영 · DAP GenAI / LXM 방향성 연결",
            ha="left", fontsize=9, fontweight="bold", color=C_ACCENT, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "B2_dual_backend_strategy.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# B3: AI OS 3-Tier Model Routing
# ==================================================================
def draw_b3():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=180)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    ax.text(8, 8.55, "AI OS — 3-Tier Model Routing",
            ha="center", fontsize=18, fontweight="bold", color=C_DARK)
    ax.text(8, 8.15,
            "작업 복잡도 기반 모델 차등 배정 · LG CNS AgenticWorks의 개인용 프레임워크",
            ha="center", fontsize=10, color=C_GRAY, style="italic")

    # 좌측: 복잡도 판정
    _box(ax, (0.3, 3.5), 3.2, 3.6, "",
         facecolor="#F1F5F9", edgecolor=C_DARK, lw=2, radius=0.08)
    ax.text(1.9, 6.85, "Complexity Gate",
            ha="center", fontsize=12, fontweight="bold", color=C_DARK)
    ax.text(1.9, 6.55, "§1 Adaptive Gate",
            ha="center", fontsize=9, color=C_GRAY, style="italic")

    complexity = [
        ("Trivial", "1 파일 · 10줄 미만", C_SUCCESS),
        ("Standard", "2~3 파일 · 분석 필요", C_BLUE),
        ("Complex", "Goal-Backward\n분해 + 설계서", C_ACCENT),
    ]
    for i, (lvl, desc, col) in enumerate(complexity):
        y = 5.9 - i * 0.75
        _box(ax, (0.55, y - 0.25), 2.7, 0.55, lvl,
             facecolor="#FFFFFF", edgecolor=col, fontsize=10, fontweight="bold",
             textcolor=col, lw=1.5, radius=0.04)
        ax.text(1.9, y - 0.52, desc,
                ha="center", fontsize=8, color=C_GRAY)

    # 중앙 화살표
    _arrow(ax, (3.5, 5.3), (4.2, 5.3), color=C_DARK, lw=2.5, style="-|>")

    # 중앙·우측: 3 티어
    tiers = [
        {
            "name": "Orchestrator Tier",
            "model": "Opus 4.7 (1M context)",
            "role": "Planner · Router · Quality Gate",
            "agents": ["orchestrator", "reviewer", "adversarial-verifier", "evaluator"],
            "color": C_ACCENT,
            "bg": "#FEE2E2",
            "x": 4.3,
        },
        {
            "name": "Specialist Tier",
            "model": "Sonnet 4.6",
            "role": "Executor · Analyst · Designer",
            "agents": ["emr-planner", "emr-designer", "workflow-architect",
                       "data-analyzer", "invest-analyzer", "fact-checker",
                       "security-reviewer"],
            "color": C_BLUE,
            "bg": "#DBEAFE",
            "x": 8.1,
        },
        {
            "name": "Utility Tier",
            "model": "Haiku 4.5",
            "role": "Explorer · Tagger · Summarizer",
            "agents": ["Explore", "gsd-doc-classifier", "gsd-ui-checker"],
            "color": C_TEAL,
            "bg": "#CCFBF1",
            "x": 11.9,
        },
    ]

    for t in tiers:
        _box(ax, (t["x"], 3.5), 3.7, 3.6, "",
             facecolor=t["bg"], edgecolor=t["color"], lw=2, radius=0.1)
        ax.text(t["x"] + 1.85, 6.85, t["name"],
                ha="center", fontsize=12, fontweight="bold", color=t["color"])
        ax.text(t["x"] + 1.85, 6.5, t["model"],
                ha="center", fontsize=9, fontweight="bold", color=C_DARK)
        ax.text(t["x"] + 1.85, 6.2, t["role"],
                ha="center", fontsize=8, color=C_GRAY, style="italic")

        for i, ag in enumerate(t["agents"]):
            y = 5.8 - i * 0.32
            _box(ax, (t["x"] + 0.2, y - 0.12), 3.3, 0.26, ag,
                 facecolor=C_CARD, edgecolor=t["color"],
                 fontsize=8, radius=0.03, lw=0.8)

    # 하단 배너 — 스펙 비교
    _box(ax, (0.3, 0.3), 15.4, 2.7, "",
         facecolor="#1F2937", edgecolor=C_DARK, lw=1.5, radius=0.1)
    ax.text(8.0, 2.75, "Model Spec Comparison",
            ha="center", fontsize=11, fontweight="bold", color="#FCD34D")

    spec_rows = [
        ("", "Context", "비용(input/1M)", "비용(output/1M)", "속도", "주 역할"),
        ("Opus 4.7", "1M tokens", "$15", "$75", "느림", "계획·라우팅·품질"),
        ("Sonnet 4.6", "200K", "$3", "$15", "보통", "구현·분석·검증"),
        ("Haiku 4.5", "200K", "$1", "$5", "빠름", "탐색·태깅·요약"),
    ]
    cols_x = [1.3, 4.0, 6.5, 9.2, 11.8, 13.8]
    for r_idx, row in enumerate(spec_rows):
        y = 2.35 - r_idx * 0.4
        color = "#FCD34D" if r_idx == 0 else "#E5E7EB"
        weight = "bold" if r_idx == 0 else "normal"
        for c_idx, cell in enumerate(row):
            ax.text(cols_x[c_idx], y, cell,
                    ha="center", fontsize=9,
                    color=color, fontweight=weight)

    ax.text(0.3, 0.05,
            "LG CNS JD 매칭: 기술 2.2 모델 운영 · 우대 3.1 오케스트레이션 · AgenticWorks 프레임워크 방향",
            ha="left", fontsize=9, fontweight="bold", color=C_ACCENT, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "B3_ai_os_routing.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# C1: Data Scale Infographic
# ==================================================================
def draw_c1():
    fig, ax = plt.subplots(figsize=(16, 9), dpi=180)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 9)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    ax.text(8, 8.55, "Data Scale — By the Numbers",
            ha="center", fontsize=18, fontweight="bold", color=C_DARK)
    ax.text(8, 8.15,
            "vet-snomed-rag + 수의 EMR 프로젝트 데이터 규모 실측",
            ha="center", fontsize=10, color=C_GRAY, style="italic")

    # 2x2 grid, 4 big numbers
    cards = [
        {
            "number": "414,848",
            "label": "SNOMED CT\nactive concepts",
            "detail": "INT 378,938 + VET 35,910\nRF2 2026-03",
            "color": C_ACCENT,
            "bg": "#FCE7F3",
            "source": "data/snomed_ct_vet.db · SELECT count(*) WHERE active=1",
        },
        {
            "number": "1,379,816",
            "label": "SNOMED CT\nRelationships",
            "detail": "is-a · finding_site\nassociated_morphology 등",
            "color": C_BLUE,
            "bg": "#DBEAFE",
            "source": "SNOMED RF2 Relationship File",
        },
        {
            "number": "877",
            "label": "Post-Coordination\n표현식",
            "detail": "A 346 + P 495 + O 36\nSCG 문법 · MRCM 검증",
            "color": C_TEAL,
            "bg": "#CCFBF1",
            "source": "VetSTT_Developer_Package/02_SNOMED_매핑/",
        },
        {
            "number": "8,651+",
            "label": "VET Extension\n매핑 수행",
            "detail": "S v23.7.1 · O v23 E73\nA v8 · P v3.4",
            "color": C_SUCCESS,
            "bg": "#D1FAE5",
            "source": "project_{s,o,a,p}_axis (MEMORY.md)",
        },
    ]

    positions = [(0.5, 4.3), (8.2, 4.3), (0.5, 0.9), (8.2, 0.9)]
    card_w = 7.3
    card_h = 3.2

    for (x, y), c in zip(positions, cards):
        _box(ax, (x, y), card_w, card_h, "",
             facecolor=c["bg"], edgecolor=c["color"], lw=2, radius=0.1)
        ax.text(x + card_w / 2, y + card_h - 0.8, c["number"],
                ha="center", fontsize=46, fontweight="bold", color=c["color"])
        ax.text(x + card_w / 2, y + card_h - 1.7, c["label"],
                ha="center", fontsize=13, fontweight="bold", color=C_DARK)
        ax.text(x + card_w / 2, y + card_h - 2.35, c["detail"],
                ha="center", fontsize=10, color=C_DARK)
        ax.text(x + card_w / 2, y + 0.25, c["source"],
                ha="center", fontsize=8, color=C_GRAY, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "C1_data_scale.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# C2: Project Timeline
# ==================================================================
def draw_c2():
    fig, ax = plt.subplots(figsize=(17, 8), dpi=180)
    ax.set_xlim(0, 17)
    ax.set_ylim(0, 8)
    ax.set_facecolor(C_LIGHT)
    ax.axis("off")

    ax.text(8.5, 7.55, "Project Timeline — 2026-03 ~ 2026-04",
            ha="center", fontsize=18, fontweight="bold", color=C_DARK)
    ax.text(8.5, 7.15,
            "AI OS 프레임워크 구축 → vet-snomed-rag PoC → v1.0 GitHub Public",
            ha="center", fontsize=10, color=C_GRAY, style="italic")

    # 가로 타임라인 축
    timeline_y = 4.2
    ax.plot([0.8, 16.2], [timeline_y, timeline_y],
            color=C_DARK, linewidth=3, zorder=1)
    # 시간 눈금
    months = ["03-01", "03-15", "04-01", "04-15", "04-30"]
    month_x = [1.5, 5.0, 8.5, 12.0, 15.5]
    for mx, mo in zip(month_x, months):
        ax.plot([mx, mx], [timeline_y - 0.15, timeline_y + 0.15],
                color=C_DARK, linewidth=2)
        ax.text(mx, timeline_y - 0.5, mo,
                ha="center", fontsize=9, color=C_GRAY)

    # 마일스톤
    milestones = [
        {
            "x": 1.8, "above": True,
            "title": "AI OS 착수",
            "date": "2026-03-01",
            "detail": "00_Core_Context · 03_Working_Rules\nAgent Routing · Model Selection",
            "color": C_BLUE,
        },
        {
            "x": 4.2, "above": False,
            "title": "Sub Agent 확장",
            "date": "2026-03-15~",
            "detail": "11+ Sub Agents · Skill System\nOutput Quality Gate O1~O12",
            "color": C_TEAL,
        },
        {
            "x": 6.8, "above": True,
            "title": "수의 EMR SNOMED",
            "date": "2026-04-02~06",
            "detail": "A축 LOCAL 1,451→0 해소\nPost-Coord 877건 구축",
            "color": C_AMBER,
        },
        {
            "x": 9.5, "above": False,
            "title": "vet-snomed-rag 착수",
            "date": "2026-04-16",
            "detail": "Hybrid RAG PoC 설계·구현\nChromaDB 414K 인덱싱",
            "color": C_ACCENT,
        },
        {
            "x": 11.5, "above": True,
            "title": "Dual Backend + T7 fix",
            "date": "2026-04-19",
            "detail": "Strategy Pattern 도입\n11-쿼리 6/10 → 10/10 PASS",
            "color": C_ACCENT,
        },
        {
            "x": 14.2, "above": False,
            "title": "v1.0 GitHub Public",
            "date": "2026-04-20",
            "detail": "ricocopapa/vet-snomed-rag MIT\n차트 3 + 스크린샷 6 + social preview",
            "color": C_SUCCESS,
        },
        {
            "x": 15.8, "above": True,
            "title": "LG CNS 지원",
            "date": "2026-04-30",
            "detail": "AI PM/PL 서류 제출 D-Day",
            "color": C_DARK,
        },
    ]

    for m in milestones:
        # 노드 점
        ax.plot(m["x"], timeline_y, marker="o", markersize=16,
                markerfacecolor=m["color"], markeredgecolor="white",
                markeredgewidth=2.5, zorder=3)

        # 박스 위치
        if m["above"]:
            box_y = timeline_y + 0.6
            text_y = timeline_y + 0.4
        else:
            box_y = timeline_y - 2.3
            text_y = timeline_y - 0.4

        # 수직 연결선
        line_y1 = timeline_y + 0.2 if m["above"] else timeline_y - 0.2
        line_y2 = box_y if m["above"] else box_y + 1.6
        ax.plot([m["x"], m["x"]], [line_y1, line_y2],
                color=m["color"], linewidth=1.5, linestyle="--", zorder=2)

        # 박스
        _box(ax, (m["x"] - 1.2, box_y), 2.4, 1.6, "",
             facecolor=C_CARD, edgecolor=m["color"], lw=1.8, radius=0.06)
        ax.text(m["x"], box_y + 1.3, m["title"],
                ha="center", fontsize=10, fontweight="bold", color=m["color"])
        ax.text(m["x"], box_y + 0.95, m["date"],
                ha="center", fontsize=8, color=C_GRAY, style="italic")
        ax.text(m["x"], box_y + 0.35, m["detail"],
                ha="center", fontsize=8, color=C_DARK)

    # 하단 배너 — 누적 성과
    ax.text(0.8, 0.55,
            "누적 성과: AI OS 9세션 · Sub Agents 11+ · Feedback Memory 28 · Project Memory 17 · Skill 14종",
            ha="left", fontsize=9, color=C_DARK)
    ax.text(0.8, 0.25,
            "LG CNS JD 매칭: 기술 2.1 Agentic AI 아키텍처 · 우대 3.1 오케스트레이션 프로젝트 경험 (9세션 실증)",
            ha="left", fontsize=9, fontweight="bold", color=C_ACCENT, style="italic")

    plt.tight_layout()
    out_path = OUT_DIR / "C2_project_timeline.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


# ==================================================================
# C3: Streamlit Screenshot Collage (6-query 2x3 grid)
# ==================================================================
def draw_c3_collage():
    from matplotlib import image as mpimg

    root = Path(__file__).resolve().parent.parent
    shots = [
        ("01_query_feline_panleukopenia.png", "Q1 · Feline panleukopenia (EN)"),
        ("02_query_goyangi_dangnyo.png", "Q2 · 고양이 당뇨 (KR)"),
        ("03_query_gae_chejangyeom.png", "Q3 · 개 췌장염 (KR)"),
        ("04_query_pancreatitis_dog.png", "Q4 · Pancreatitis dog (EN)"),
        ("05_query_malui_jeyeopyeom.png", "Q5 · 말의 제엽염 (KR)"),
        ("06_query_canine_parvovirus.png", "Q6 · Canine parvovirus (EN)"),
    ]

    fig, axes = plt.subplots(2, 3, figsize=(17, 10), dpi=180)
    fig.patch.set_facecolor(C_LIGHT)

    # 상단 타이틀 (전체 figure)
    fig.suptitle("Streamlit Demo — 6-Query Screenshot Collage",
                 fontsize=18, fontweight="bold", color=C_DARK, y=0.98)
    fig.text(0.5, 0.945,
             "한국어 · 영어 교차 검증 · Top-1 정확 검색 성공 6종",
             ha="center", fontsize=11, color=C_GRAY, style="italic")

    for ax, (fname, caption) in zip(axes.flat, shots):
        img_path = root / "docs" / "screenshots" / fname
        if img_path.exists():
            img = mpimg.imread(img_path)
            ax.imshow(img)
            ax.set_title(caption, fontsize=11, fontweight="bold",
                         color=C_DARK, pad=8)
        else:
            ax.text(0.5, 0.5, f"(이미지 누락\n{fname})",
                    ha="center", va="center", fontsize=9, color=C_GRAY,
                    transform=ax.transAxes)
            ax.set_title(caption, fontsize=11, color=C_GRAY, pad=8)
        ax.axis("off")

    # 하단 JD 매칭 태그 (전체 figure)
    fig.text(0.5, 0.04,
             "LG CNS JD 매칭: 기술 2.1 Retrieval (한국어 쿼리 성공 증명) · 우대 3.1 Agentic AI 이행 경험 실증",
             ha="center", fontsize=10, fontweight="bold", color=C_ACCENT, style="italic")
    fig.text(0.5, 0.015,
             "원본 경로: docs/screenshots/01~06_*.png  ·  11-쿼리 회귀 10/10 PASS · T5 복수정답 NA 제외",
             ha="center", fontsize=8, color=C_GRAY, style="italic")

    plt.tight_layout(rect=[0, 0.06, 1, 0.93])
    out_path = OUT_DIR / "C3_screenshot_collage.png"
    plt.savefig(out_path, bbox_inches="tight", facecolor=C_LIGHT, dpi=180)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    print("Generating portfolio visuals...")
    for name, fn in [
        ("A1", draw_a1), ("A2", draw_a2), ("A3", draw_a3),
        ("B1", draw_b1), ("B2", draw_b2), ("B3", draw_b3),
        ("C1", draw_c1), ("C2", draw_c2),
        ("C3", draw_c3_collage),
    ]:
        path = fn()
        print(f"  {name} → {path}")
    print("Done.")
