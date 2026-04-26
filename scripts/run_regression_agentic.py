"""N-1 agentic_query 정밀 회귀 — 14쿼리 × {agentic, base} × {RERANK on/off}.

핸드오프: docs/20260426_v2_6_roadmap_handoff.md §3-1

[실행]
    cd ~/claude-cowork/07_Projects/vet-snomed-rag
    venv/bin/python scripts/run_regression_agentic.py

[출력]
    graphify_out/agentic_regression_metrics.json
    graphify_out/agentic_vs_base_comparison.md

[Rate-Limit]
    Gemini Free Tier 5 RPM. agentic = 3 LLM burst/쿼리,
    base = 1 LLM/쿼리. 매 호출 후 throttle.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from src.retrieval.agentic_pipeline import AgenticRAGPipeline
from src.retrieval.rag_pipeline import SNOMEDRagPipeline


# ── 14쿼리 정의 (T1-T11 기존 + T12-T14 외부 도구 트리거) ──
QUERIES = [
    ("T1",  "feline panleukopenia SNOMED code",         "339181000009108"),
    ("T2",  "canine parvovirus enteritis",               "47457000"),
    ("T3",  "diabetes mellitus in cat",                  "73211009"),
    ("T4",  "pancreatitis in dog",                       "75694006"),
    ("T5",  "chronic kidney disease in cat",             None),
    ("T6",  "cat bite wound",                            "283782004"),
    ("T7",  "feline diabetes",                           "73211009"),
    ("T8",  "diabetes mellitus type 1",                  "46635009"),
    ("T9",  "고양이 당뇨",                                "73211009"),
    ("T10", "개 췌장염",                                  "75694006"),
    ("T11", "고양이 범백혈구감소증 SNOMED 코드",            "339181000009108"),
    # 신규 — Tier B 외부 도구 트리거 (핸드오프 §3-1-1 추가 권고)
    ("T12", "diabetes mellitus ICD-10 cross-walk",       "73211009"),
    ("T13", "rare feline endocrine literature",          None),
    ("T14", "고양이 당뇨 ICD-10 매핑",                     "73211009"),
]

# 외부 도구 기대 (라우터 룰 기반)
EXPECTED_EXTERNAL = {
    "T12": ["umls"],
    "T13": ["pubmed"],
    "T14": ["umls"],
}

# Gemini 5 RPM rate-limit (LLM 호출 사이 최소 간격, 초)
SLEEP_AGENTIC = 30  # 3 LLM burst 후 다음 쿼리까지
SLEEP_BASE = 13     # 1 LLM 후 다음까지


def find_rank(results, expected):
    if expected is None or not results:
        return None
    for i, r in enumerate(results, 1):
        if getattr(r, "concept_id", None) == expected:
            return i
    return None


def verdict(rank, expected):
    if expected is None:
        return "NA"
    if rank is not None and rank <= 5:
        return "PASS"
    return "FAIL"


def run_agentic(pipe, qtext, rerank, expected):
    t0 = time.perf_counter()
    result = pipe.agentic_query(qtext, top_k=10, rerank=rerank)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # search_results from last_sub_results (subqueries 평탄화)
    flat = [r for sr in result.last_sub_results for r in sr.get("results", [])]
    rank = find_rank(flat, expected)
    top1 = getattr(flat[0], "concept_id", None) if flat else None
    top1_term = getattr(flat[0], "preferred_term", "") if flat else ""

    return {
        "iterations": result.iterations,
        "top1_id": top1,
        "top1_term": top1_term,
        "rank_of_correct": rank,
        "verdict": verdict(rank, expected),
        "external_tools_called": list(result.external_results.keys()),
        "external_results_summary": {
            tool: len(items) for tool, items in result.external_results.items()
        },
        "answer_length": len(result.final_answer),
        "final_answer_preview": result.final_answer[:200],
        "relevance_verdict": result.relevance_verdict,
        "confidence": result.confidence,
        "sources_used": result.sources_used,
        "umls_section_present": "[UMLS Cross-Walk]" in result.final_answer,
        "pubmed_section_present": "[PubMed Evidence]" in result.final_answer,
        "latency_ms": latency_ms,
    }


def run_base(pipe, qtext, rerank, expected):
    t0 = time.perf_counter()
    result = pipe.query(qtext, top_k=10, rerank=rerank)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    sr_list = result.get("search_results", [])
    rank = find_rank(sr_list, expected)
    top1 = getattr(sr_list[0], "concept_id", None) if sr_list else None
    top1_term = getattr(sr_list[0], "preferred_term", "") if sr_list else ""

    return {
        "iterations": 1,
        "top1_id": top1,
        "top1_term": top1_term,
        "rank_of_correct": rank,
        "verdict": verdict(rank, expected),
        "external_tools_called": [],
        "external_results_summary": {},
        "answer_length": len(result.get("answer", "")),
        "latency_ms": latency_ms,
    }


def main():
    print("=" * 70)
    print(" N-1 agentic vs base 정밀 회귀")
    print(f" 실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 14쿼리 × {{agentic, base}} × {{RERANK on, off}}")
    print(f" Sleep policy: agentic={SLEEP_AGENTIC}s, base={SLEEP_BASE}s")
    print("=" * 70)

    base = SNOMEDRagPipeline(
        llm_backend="none",
        reformulator_backend="gemini",
        enable_rerank=True,
    )
    agentic = AgenticRAGPipeline(base_pipeline=base)
    print("[INFO] UMLS enabled:", agentic.umls.enabled)
    print("[INFO] PubMed enabled:", agentic.pubmed.enabled)

    metrics = []

    for qid, qtext, expected in QUERIES:
        print(f"\n{'─' * 60}")
        print(f"[{qid}] {qtext}  (기대: {expected})")

        entry = {
            "query_id": qid,
            "query_text": qtext,
            "expected_concept_id": expected,
            "expected_external_tools": EXPECTED_EXTERNAL.get(qid, []),
            "modes": {},
        }

        for mode_name, runner_kind, sleep_after, rerank in [
            ("agentic_rerank",   "agentic", SLEEP_AGENTIC, True),
            ("agentic_norerank", "agentic", SLEEP_AGENTIC, False),
            ("base_rerank",      "base",    SLEEP_BASE,    True),
            ("base_norerank",    "base",    SLEEP_BASE,    False),
        ]:
            print(f"  → [{mode_name}] sleep {sleep_after}s before...")
            time.sleep(sleep_after)
            try:
                if runner_kind == "agentic":
                    mode_result = run_agentic(agentic, qtext, rerank, expected)
                else:
                    mode_result = run_base(base, qtext, rerank, expected)
                entry["modes"][mode_name] = mode_result

                rank_str = (
                    f"#{mode_result['rank_of_correct']}"
                    if mode_result["rank_of_correct"]
                    else "없음"
                )
                print(
                    f"    rank={rank_str}  top1={mode_result['top1_id']}  "
                    f"verdict={mode_result['verdict']}  iter={mode_result['iterations']}"
                )
                if mode_result.get("external_tools_called"):
                    print(
                        f"    external={mode_result['external_tools_called']}  "
                        f"summary={mode_result['external_results_summary']}"
                    )
            except Exception as e:
                entry["modes"][mode_name] = {"error": str(e), "verdict": "ERROR"}
                print(f"    [ERROR] {type(e).__name__}: {e}")

        metrics.append(entry)

        # 진행률 + 중간 저장 (긴 실행에서 중단 대비)
        out_dir = PROJECT_ROOT / "graphify_out"
        out_dir.mkdir(exist_ok=True)
        with open(out_dir / "agentic_regression_metrics.json", "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)

    base.close()

    # 최종 저장
    out_dir = PROJECT_ROOT / "graphify_out"
    metrics_path = out_dir / "agentic_regression_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"\n[저장] {metrics_path}")

    _write_comparison(metrics, out_dir)
    _print_summary(metrics)
    return metrics


def _print_summary(metrics):
    print("\n" + "=" * 70)
    print(" 회귀 결과 요약")
    print("=" * 70)
    for mode in ["agentic_rerank", "agentic_norerank", "base_rerank", "base_norerank"]:
        p = sum(1 for e in metrics if e["modes"].get(mode, {}).get("verdict") == "PASS")
        n = sum(1 for e in metrics if e["modes"].get(mode, {}).get("verdict") in ("PASS", "FAIL"))
        err = sum(1 for e in metrics if e["modes"].get(mode, {}).get("verdict") == "ERROR")
        print(f"  [{mode:18s}] PASS {p}/{n}  (ERROR={err})")

    # 외부 도구 검증
    print("\n[외부 도구 활성 케이스]")
    for qid, expected_ext in EXPECTED_EXTERNAL.items():
        e = next(x for x in metrics if x["query_id"] == qid)
        ag = e["modes"].get("agentic_rerank", {})
        called = ag.get("external_tools_called", [])
        umls_md = ag.get("umls_section_present")
        pubmed_md = ag.get("pubmed_section_present")
        print(
            f"  [{qid}] expected={expected_ext}  called={called}  "
            f"UMLS_md={umls_md}  PubMed_md={pubmed_md}"
        )


def _write_comparison(metrics, out_dir):
    report_path = out_dir / "agentic_vs_base_comparison.md"

    def pass_count(mode_name):
        c = sum(1 for e in metrics if e["modes"].get(mode_name, {}).get("verdict") == "PASS")
        n = sum(1 for e in metrics if e["modes"].get(mode_name, {}).get("verdict") in ("PASS", "FAIL"))
        return c, n

    lines = []
    lines.append("# N-1 agentic_query vs base.query 회귀 비교")
    lines.append(f"\n생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("핸드오프: docs/20260426_v2_6_roadmap_handoff.md §3-1\n")

    lines.append("## 모드별 PASS율 (외부 도구 OFF 케이스 + ON 케이스 합산)\n")
    lines.append("| 모드 | PASS / 판정대상 |")
    lines.append("|---|---|")
    for m in ["agentic_rerank", "agentic_norerank", "base_rerank", "base_norerank"]:
        p, n = pass_count(m)
        lines.append(f"| {m} | {p}/{n} |")

    # 외부 도구 활성 케이스 (T12-T14)
    lines.append("\n## 외부 도구 활성 케이스 검증 (T12-T14)\n")
    lines.append("| qid | 쿼리 | 기대 도구 | 실제 호출 | UMLS md | PubMed md |")
    lines.append("|---|---|---|---|---|---|")
    md_correct = 0
    md_total = 0
    for qid in ["T12", "T13", "T14"]:
        e = next(x for x in metrics if x["query_id"] == qid)
        expected_ext = e["expected_external_tools"]
        ag = e["modes"].get("agentic_rerank", {})
        called = ag.get("external_tools_called", [])
        umls_p = ag.get("umls_section_present", False)
        pubmed_p = ag.get("pubmed_section_present", False)
        umls_str = "✓" if umls_p else "✗"
        pubmed_str = "✓" if pubmed_p else "✗"
        if "umls" in expected_ext:
            md_total += 1
            md_correct += int(umls_p)
        if "pubmed" in expected_ext:
            md_total += 1
            md_correct += int(pubmed_p)
        lines.append(
            f"| {qid} | `{e['query_text']}` | {','.join(expected_ext)} "
            f"| {','.join(called) or '없음'} | {umls_str} | {pubmed_str} |"
        )

    # 쿼리별 상세
    lines.append("\n## 쿼리별 상세 (Top-1 비교)\n")
    lines.append("| qid | query | 기대 | agentic_rerank | base_rerank | iter | latency(agentic, ms) |")
    lines.append("|---|---|---|---|---|---|---|")
    for e in metrics:
        ag = e["modes"].get("agentic_rerank", {})
        b = e["modes"].get("base_rerank", {})
        ag_rank = f"#{ag.get('rank_of_correct')}" if ag.get("rank_of_correct") else "없음"
        b_rank = f"#{b.get('rank_of_correct')}" if b.get("rank_of_correct") else "없음"
        lines.append(
            f"| {e['query_id']} | `{e['query_text']}` | {e['expected_concept_id'] or '복수'} "
            f"| {ag_rank} {ag.get('verdict','')} | {b_rank} {b.get('verdict','')} "
            f"| {ag.get('iterations','')} | {ag.get('latency_ms','')} |"
        )

    # base 모드 회귀 비교
    lines.append("\n## base 모드 회귀 (v2.5.1 정밀 회귀 baseline 대비)\n")
    lines.append("v2.5.1 baseline: graphify_out/regression_metrics_rerank.json (gemini 10/10)\n")
    lines.append("- 본 실행의 base_rerank 결과가 11쿼리 baseline과 동일하면 회귀 0 (T12-T14는 신규).\n")

    # 성공 기준 1:1 PASS/FAIL
    lines.append("\n## 성공 기준 (§3-1-5) 1:1 PASS/FAIL\n")
    lines.append("| # | 항목 | 결과 | 판정 |")
    lines.append("|---|---|---|---|")
    p_ag, n_ag = pass_count("agentic_rerank")
    lines.append(
        f"| 1 | agentic Top-1 ≥ 9/10 | {p_ag}/{n_ag} "
        f"| {'PASS' if p_ag >= 9 else 'FAIL'} |"
    )
    md_pct = (md_correct / md_total * 100) if md_total > 0 else 0
    lines.append(
        f"| 2 | 외부 도구 markdown ≥ 95% | {md_correct}/{md_total} ({md_pct:.0f}%) "
        f"| {'PASS' if md_pct >= 95 else 'FAIL'} |"
    )
    p_br, n_br = pass_count("base_rerank")
    lines.append(
        f"| 3 | base_rerank 회귀 0 (≥ 9/10) | {p_br}/{n_br} "
        f"| {'PASS' if p_br >= 9 else 'FAIL'} |"
    )

    lines.append("\n---")
    lines.append("*생성: scripts/run_regression_agentic.py (N-1)*")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[저장] {report_path}")


if __name__ == "__main__":
    main()
