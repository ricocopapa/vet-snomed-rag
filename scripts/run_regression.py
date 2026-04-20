"""
11쿼리 × Backend 회귀 테스트.

설계서: 20260419_vet_snomed_rag_T7_fix_design_v1.md §7.1

[실행]
    cd ~/claude-cowork/07_Projects/vet-snomed-rag
    source venv/bin/activate
    python scripts/run_regression.py

[출력]
    graphify_out/regression_metrics.json  — 11 entries × modes
    graphify_out/backend_comparison.md    — Gemini vs Claude 비교 보고서
"""

import json
import os
import sys
import time
from pathlib import Path
from datetime import datetime

# 프로젝트 루트를 sys.path에 추가
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# .env 로드
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.retrieval.rag_pipeline import SNOMEDRagPipeline

# ─── 11쿼리 정의 ─────────────────────────────────────────

QUERIES = [
    ("T1",  "feline panleukopenia SNOMED code",         "339181000009108"),
    ("T2",  "canine parvovirus enteritis",               "47457000"),
    ("T3",  "diabetes mellitus in cat",                  "73211009"),
    ("T4",  "pancreatitis in dog",                       "75694006"),
    ("T5",  "chronic kidney disease in cat",             None),       # CKD 계열, 복수 가능
    ("T6",  "cat bite wound",                            "283782004"),
    ("T7",  "feline diabetes",                           "73211009"),  # 핵심 타겟
    ("T8",  "diabetes mellitus type 1",                  "46635009"),
    ("T9",  "고양이 당뇨",                                "73211009"),
    ("T10", "개 췌장염",                                  "75694006"),
    ("T11", "고양이 범백혈구감소증 SNOMED 코드",            "339181000009108"),
]

# 사용 가능 backend 결정
BACKENDS = ["none", "gemini"]
if os.environ.get("ANTHROPIC_API_KEY"):
    BACKENDS.append("claude")
    print("[INFO] ANTHROPIC_API_KEY 감지 — claude 백엔드 포함")
else:
    print("[INFO] ANTHROPIC_API_KEY 미설정 — claude 백엔드 스킵")


def find_rank(results, expected_concept_id: str | None) -> int | None:
    """검색 결과에서 expected_concept_id의 순위(1-based)를 반환한다."""
    if expected_concept_id is None:
        return None
    for i, r in enumerate(results, 1):
        if r.concept_id == expected_concept_id:
            return i
    return None


def run_single(pipeline, query_text: str, top_k: int = 10) -> dict:
    """단일 쿼리 실행 후 결과를 반환한다."""
    t0 = time.perf_counter()
    result = pipeline.query(query_text, top_k=top_k)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    return result, latency_ms


def verdict(rank: int | None, expected: str | None) -> str:
    """순위와 기대값으로 PASS/FAIL/NA를 판정한다."""
    if expected is None:
        return "NA"  # T5처럼 단일 기대값 없는 경우
    if rank is not None and rank <= 5:
        return "PASS"
    return "FAIL"


def main():
    print("=" * 70)
    print(" 11쿼리 × Backend 회귀 테스트")
    print(f" 실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 테스트 backend: {BACKENDS}")
    print("=" * 70)

    # 파이프라인 인스턴스 (backend별로 별도 생성)
    pipelines: dict[str, SNOMEDRagPipeline] = {}
    for backend in BACKENDS:
        print(f"\n[초기화] backend={backend}")
        pipelines[backend] = SNOMEDRagPipeline(
            llm_backend="none",
            reformulator_backend=backend,
        )
        print(f"[완료] backend={backend} 초기화")

    # 결과 수집
    metrics: list[dict] = []
    summary_rows = []  # 콘솔 출력용

    for qid, qtext, expected in QUERIES:
        print(f"\n{'─' * 60}")
        print(f"[{qid}] {qtext}  (기대: {expected})")

        entry = {
            "query_id": qid,
            "query_text": qtext,
            "expected_concept_id": expected,
            "modes": {},
            "verdict_per_backend": {},
        }

        for backend in BACKENDS:
            pipeline = pipelines[backend]

            # Gemini Free Tier: 분당 5회 제한 — API 호출 간 13초 대기 (5회/분 = 12초 간격 + 여유)
            # none 백엔드는 API 호출 없으므로 대기 불필요
            if backend == "gemini":
                time.sleep(13)

            result, latency_ms = run_single(pipeline, qtext, top_k=10)

            rank = find_rank(result["search_results"], expected)
            top1 = result["search_results"][0].concept_id if result["search_results"] else None
            top1_term = result["search_results"][0].preferred_term if result["search_results"] else ""
            v = verdict(rank, expected)

            mode_entry: dict = {
                "top_1_id": top1,
                "top_1_term": top1_term,
                "rank_of_correct": rank,
                "latency_ms": latency_ms,
                "cost_usd": 0.0,
                "cached": False,
                "model_used": None,
            }

            # 리포매팅 정보 추가
            if backend != "none" and result.get("reformulation"):
                ref = result["reformulation"]
                mode_entry.update({
                    "reformulated": ref.get("reformulated"),
                    "post_coord_hint": ref.get("post_coord_hint"),
                    "confidence": ref.get("confidence"),
                    "cached": ref.get("cached", False),
                    "model_used": ref.get("model_used"),
                    "cost_usd": ref.get("cost_usd", 0.0),
                    "latency_ms": ref.get("latency_ms", latency_ms),
                })

            entry["modes"][backend] = mode_entry
            entry["verdict_per_backend"][backend] = v

            rank_str = f"#{rank}" if rank else "없음"
            print(f"  [{backend:6s}] rank={rank_str:4s}  top1={top1}  verdict={v}")

        metrics.append(entry)

    # 파이프라인 종료
    for p in pipelines.values():
        p.close()

    # ─── 결과 저장 ──────────────────────────────────────────
    out_dir = PROJECT_ROOT / "graphify_out"
    out_dir.mkdir(exist_ok=True)

    # regression_metrics.json
    metrics_path = out_dir / "regression_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)
    print(f"\n[저장] {metrics_path}")

    # ─── 요약 집계 ───────────────────────────────────────────
    print("\n" + "=" * 70)
    print(" 회귀 결과 요약")
    print("=" * 70)

    for backend in BACKENDS:
        pass_count = sum(
            1 for e in metrics
            if e["verdict_per_backend"].get(backend) == "PASS"
        )
        na_count = sum(
            1 for e in metrics
            if e["verdict_per_backend"].get(backend) == "NA"
        )
        judged = len(metrics) - na_count
        print(f"  [{backend:6s}] PASS {pass_count}/{judged}  (NA={na_count}건 제외)")

    # T7 상세
    t7 = next(e for e in metrics if e["query_id"] == "T7")
    print("\n[T7 핵심 상세]")
    for backend in BACKENDS:
        m = t7["modes"].get(backend, {})
        print(f"  [{backend}] rank={m.get('rank_of_correct')}  "
              f"reformulated={m.get('reformulated', 'N/A')}  "
              f"conf={m.get('confidence', 'N/A')}  "
              f"verdict={t7['verdict_per_backend'].get(backend)}")

    # ─── backend_comparison.md 생성 ─────────────────────────
    _write_comparison_report(metrics, BACKENDS, out_dir)

    print(f"\n[완료] regression_metrics.json: {len(metrics)}entries")
    return metrics


def _write_comparison_report(metrics: list[dict], backends: list[str], out_dir: Path):
    """backend_comparison.md 생성."""
    report_path = out_dir / "backend_comparison.md"

    lines = []
    lines.append("# Backend Comparison — Gemini 2.5 Flash vs Claude Sonnet 4.6")
    lines.append(f"\n생성 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("\n## 요약 테이블\n")

    # 헤더
    header_cols = ["메트릭", "none (기준선)"]
    if "gemini" in backends:
        header_cols.append("Gemini 2.5 Flash")
    if "claude" in backends:
        header_cols.append("Claude Sonnet 4.6")
    else:
        header_cols.append("Claude Sonnet 4.6 (미실행)")

    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("| " + " | ".join(["---"] * len(header_cols)) + " |")

    # PASS율 행
    def pass_rate(backend):
        if backend not in backends:
            return "API 키 미설정으로 실측 생략"
        judged = [e for e in metrics if e["verdict_per_backend"].get(backend) != "NA"]
        p = sum(1 for e in judged if e["verdict_per_backend"].get(backend) == "PASS")
        return f"{p}/{len(judged)}"

    lines.append(f"| 11쿼리 PASS율 | {pass_rate('none')} | "
                 f"{pass_rate('gemini')} | "
                 f"{pass_rate('claude')} |")

    # T7 해결 행
    t7 = next(e for e in metrics if e["query_id"] == "T7")

    def t7_result(backend):
        if backend not in backends:
            return "미실행"
        v = t7["verdict_per_backend"].get(backend, "N/A")
        rank = t7["modes"].get(backend, {}).get("rank_of_correct")
        return f"{'✓' if v == 'PASS' else '✗'} (rank #{rank})" if rank else f"{'✓' if v == 'PASS' else '✗'} (없음)"

    lines.append(f"| T7 (feline diabetes→73211009) | {t7_result('none')} | "
                 f"{t7_result('gemini')} | "
                 f"{t7_result('claude')} |")

    # 총 비용
    def total_cost(backend):
        if backend not in backends:
            return "미실행"
        c = sum(e["modes"].get(backend, {}).get("cost_usd", 0.0) for e in metrics)
        return f"${c:.5f}"

    lines.append(f"| 총 비용 | $0.00000 | "
                 f"{total_cost('gemini')} | "
                 f"{total_cost('claude')} |")

    # 평균 레이턴시
    def avg_latency(backend):
        if backend not in backends:
            return "미실행"
        lats = [e["modes"].get(backend, {}).get("latency_ms", 0) for e in metrics]
        return f"{int(sum(lats)/len(lats))}ms" if lats else "N/A"

    lines.append(f"| 평균 레이턴시 | {avg_latency('none')} | "
                 f"{avg_latency('gemini')} | "
                 f"{avg_latency('claude')} |")

    # 쿼리별 상세
    lines.append("\n## 쿼리별 상세 (T1~T11)\n")
    detail_header = ["쿼리ID", "쿼리", "기대 concept_id"]
    for b in backends:
        detail_header.append(f"{b} rank")
        detail_header.append(f"{b} verdict")
    if "claude" not in backends:
        detail_header.append("claude 비고")

    lines.append("| " + " | ".join(detail_header) + " |")
    lines.append("| " + " | ".join(["---"] * len(detail_header)) + " |")

    for e in metrics:
        row = [e["query_id"], e["query_text"], e["expected_concept_id"] or "복수"]
        for b in backends:
            rank = e["modes"].get(b, {}).get("rank_of_correct")
            v = e["verdict_per_backend"].get(b, "N/A")
            row.append(f"#{rank}" if rank else "없음")
            row.append(v)
        if "claude" not in backends:
            row.append("API 키 미설정으로 실측 생략")
        lines.append("| " + " | ".join(str(x) for x in row) + " |")

    # T7 리포매팅 상세
    lines.append("\n## T7 해결 상세 (핵심)\n")
    lines.append(f"- 원본 쿼리: `{t7['query_text']}`")
    if "gemini" in backends:
        gm = t7["modes"].get("gemini", {})
        lines.append(f"- Gemini 리포매팅 결과: `{gm.get('reformulated', 'N/A')}`")
        lines.append(f"- Gemini confidence: `{gm.get('confidence', 'N/A')}`")
        lines.append(f"- Gemini post_coord_hint: `{gm.get('post_coord_hint', 'N/A')}`")
        lines.append(f"- 최종 Top-1: `{gm.get('top_1_id')} {gm.get('top_1_term', '')}`")
        lines.append(f"- 판정: **{t7['verdict_per_backend'].get('gemini')}**")
    if "claude" not in backends:
        lines.append("\n**Claude Sonnet 4.6 섹션**: API 키 미설정으로 실측 생략.")

    # 결론
    lines.append("\n## 결론 (권장 기본 backend)\n")
    gemini_pass = pass_rate("gemini") if "gemini" in backends else "N/A"
    if "gemini" in backends:
        judged_n = len([e for e in metrics if e["verdict_per_backend"].get("gemini") != "NA"])
        pass_n = sum(1 for e in metrics if e["verdict_per_backend"].get("gemini") == "PASS")
        if pass_n == judged_n:
            lines.append(f"Gemini 2.5 Flash가 {pass_n}/{judged_n} PASS 달성 — "
                         "단일 백엔드로 프로덕션 투입 가능.")
        else:
            lines.append(f"Gemini 2.5 Flash: {pass_n}/{judged_n} PASS. "
                         "일부 쿼리 추가 검토 필요.")
    if "claude" not in backends:
        lines.append("\nClaude Sonnet 4.6: API 키 미설정으로 비교 불가. "
                     "키 설정 후 동일 스크립트 재실행 시 자동 포함.")

    lines.append("\n---")
    lines.append("*생성: scripts/run_regression.py (Agent A)*")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[저장] {report_path}")


if __name__ == "__main__":
    main()
