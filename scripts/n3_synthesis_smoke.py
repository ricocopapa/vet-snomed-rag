"""N-3 §3-3-5 성공 기준 smoke — T12/T13/T14 합성 LLM 실제 호출.

검증 항목:
1. 합성 답변 ≥ +30% 길이 (base_answer_pre_synthesis 대비)
2. 외부 source 식별자(CUI / PMID) ≥ 80% 인용
3. 외부 OFF 케이스(T1/T7) skip → final_answer == base (회귀 0)
4. 케이스당 < $0.001 (대략 추정)

핸드오프: docs/20260426_v2_6_roadmap_handoff.md §3-3
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from src.retrieval.agentic_pipeline import AgenticRAGPipeline
from src.retrieval.rag_pipeline import SNOMEDRagPipeline


# 외부 도구 트리거 케이스
EXT_QUERIES = [
    ("T12", "diabetes mellitus ICD-10 cross-walk", "73211009", ["umls"]),
    ("T13", "rare feline endocrine literature", None, ["pubmed"]),
    ("T14", "고양이 당뇨 ICD-10 매핑", "73211009", ["umls"]),
]

# 회귀 0 확인용 (외부 OFF)
NO_EXT_QUERIES = [
    ("T1", "feline panleukopenia SNOMED code", "339181000009108"),
    ("T7", "feline diabetes", "73211009"),
]


def _citations_in_answer(answer: str, external_results: dict) -> tuple[int, int]:
    """외부 식별자가 답변 본문에서 몇 개 인용됐는지."""
    cited = 0
    total = 0
    for r in external_results.get("umls", []) or []:
        cui = r.get("cui", "")
        if cui:
            total += 1
            if cui in answer:
                cited += 1
    for r in external_results.get("pubmed", []) or []:
        pmid = r.get("pmid", "")
        if pmid:
            total += 1
            if pmid in answer:
                cited += 1
    return cited, total


def _estimate_cost(base_len: int, synth_len: int) -> float:
    """char 수 기반 Gemini Flash Lite 비용 대략 추정 ($).

    가정: 1 token ≈ 4 chars (영어/혼용).
    Gemini 2.5 Flash Lite: input ~$0.10/1M, output ~$0.40/1M tokens (2025년 공시 추정).
    """
    input_tokens = (base_len + 600) / 4  # base + prompt boilerplate
    output_tokens = synth_len / 4
    cost = input_tokens * 0.10 / 1_000_000 + output_tokens * 0.40 / 1_000_000
    return cost


def main():
    base = SNOMEDRagPipeline(
        llm_backend="none",
        reformulator_backend="gemini",
        enable_rerank=True,
    )
    agentic = AgenticRAGPipeline(base_pipeline=base)
    print(f"[INFO] UMLS enabled={agentic.umls.enabled}")
    print(f"[INFO] PubMed enabled={agentic.pubmed.enabled}")
    print(f"[INFO] synthesizer backend={agentic.synthesizer.backend}")

    print("\n" + "=" * 70)
    print(" Phase A — 외부 도구 트리거 케이스 (합성 활성)")
    print("=" * 70)

    pass_count = 0
    total = 0
    citation_ok = 0
    citation_total = 0
    cost_ok = 0
    cost_total = 0

    for qid, q, expected, expected_ext in EXT_QUERIES:
        print(f"\n[{qid}] {q!r}  expected_ext={expected_ext}")
        time.sleep(30)
        t0 = time.perf_counter()
        result = agentic.agentic_query(q, top_k=10, rerank=True)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        base_len = len(result.base_answer_pre_synthesis)
        synth_len = len(result.final_answer)
        ratio = (synth_len / base_len) if base_len > 0 else 0.0
        length_pass = ratio >= 1.30 and result.synthesis_used

        cited, citation_n = _citations_in_answer(result.final_answer, result.external_results)
        cite_pct = (cited / citation_n * 100) if citation_n else 0
        cite_pass = cite_pct >= 80 and citation_n > 0

        cost = _estimate_cost(base_len, synth_len)
        cost_pass = cost < 0.001

        print(f"  synthesis_used: {result.synthesis_used}")
        print(f"  base_len: {base_len}  synth_len: {synth_len}  ratio: {ratio:.2f}x"
              f"  → {'PASS' if length_pass else 'FAIL'} (≥ 1.30x)")
        print(f"  identifiers cited: {cited}/{citation_n} ({cite_pct:.0f}%)"
              f"  → {'PASS' if cite_pass else 'FAIL'} (≥ 80%)")
        print(f"  est cost: ${cost:.6f}"
              f"  → {'PASS' if cost_pass else 'FAIL'} (< $0.001)")
        print(f"  latency: {latency_ms}ms")
        print(f"  external_results keys: {list(result.external_results.keys())}")

        if length_pass:
            pass_count += 1
        total += 1
        if cite_pass:
            citation_ok += 1
        if citation_n > 0:
            citation_total += 1
        if cost_pass:
            cost_ok += 1
        cost_total += 1

    print("\n" + "=" * 70)
    print(" Phase B — 외부 도구 미활성 케이스 (회귀 0 검증)")
    print("=" * 70)

    no_regression = 0
    for qid, q, expected in NO_EXT_QUERIES:
        print(f"\n[{qid}] {q!r}")
        time.sleep(30)
        t0 = time.perf_counter()
        result = agentic.agentic_query(q, top_k=10, rerank=True)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        # 외부 OFF: synthesis_used=False + final_answer가 합성 안 된 base 그대로
        synth_skipped = result.synthesis_used is False
        external_empty = not result.external_results or not any(result.external_results.values())
        # base_answer_pre_synthesis와 final_answer가 동일해야 (회귀 0)
        equal_check = result.final_answer == result.base_answer_pre_synthesis

        skip_ok = synth_skipped and external_empty and equal_check
        print(f"  synthesis_used={result.synthesis_used}  external={list(result.external_results.keys())}")
        print(f"  final == base_pre: {equal_check}  → {'PASS' if skip_ok else 'FAIL'}")
        print(f"  latency: {latency_ms}ms")

        if skip_ok:
            no_regression += 1

    base.close()

    print("\n" + "=" * 70)
    print(" §3-3-5 성공 기준 1:1 PASS/FAIL")
    print("=" * 70)
    print(f"  1. 합성 답변 ≥ +30% 길이             : {pass_count}/{total}  "
          f"{'PASS' if pass_count == total else 'FAIL'}")
    print(f"  2. CUI/PMID 인용 ≥ 80%                : {citation_ok}/{citation_total}  "
          f"{'PASS' if citation_ok == citation_total else 'FAIL'}")
    print(f"  3. 외부 OFF 시 회귀 0 (final==base)   : {no_regression}/{len(NO_EXT_QUERIES)}  "
          f"{'PASS' if no_regression == len(NO_EXT_QUERIES) else 'FAIL'}")
    print(f"  4. 케이스당 < $0.001 (Gemini Flash Lite): {cost_ok}/{cost_total}  "
          f"{'PASS' if cost_ok == cost_total else 'FAIL'}")


if __name__ == "__main__":
    main()
