"""N-1 §3-1-5 #2 fix 검증 — T12/T13/T14 외부 도구 트리거 3건만 재실행.

UMLS/PubMed에 reformulated query 전달하도록 agentic_pipeline.py 수정 후
markdown 섹션 정확도가 95% 이상 회복되는지 확인.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from src.retrieval.agentic_pipeline import AgenticRAGPipeline
from src.retrieval.rag_pipeline import SNOMEDRagPipeline


QUERIES = [
    ("T12", "diabetes mellitus ICD-10 cross-walk", "73211009", ["umls"]),
    ("T13", "rare feline endocrine literature", None, ["pubmed"]),
    ("T14", "고양이 당뇨 ICD-10 매핑", "73211009", ["umls"]),
]


def main():
    base = SNOMEDRagPipeline(
        llm_backend="none",
        reformulator_backend="gemini",
        enable_rerank=True,
    )
    agentic = AgenticRAGPipeline(base_pipeline=base)
    print(f"[INFO] UMLS enabled={agentic.umls.enabled} timeout={agentic.umls.timeout}s")
    print(f"[INFO] PubMed enabled={agentic.pubmed.enabled}")

    md_correct = 0
    md_total = 0
    for qid, q, expected, expected_ext in QUERIES:
        print(f"\n{'─' * 60}")
        print(f"[{qid}] {q!r}  expected_ext={expected_ext}")
        time.sleep(30)
        t0 = time.perf_counter()
        result = agentic.agentic_query(q, top_k=10, rerank=True)
        dur = time.perf_counter() - t0

        called = list(result.external_results.keys())
        summary = {t: len(v) for t, v in result.external_results.items()}
        umls_md = "[UMLS Cross-Walk]" in result.final_answer
        pubmed_md = "[PubMed Evidence]" in result.final_answer

        print(f"  latency: {dur:.2f}s")
        print(f"  external_tools_called: {called}")
        print(f"  external_results_summary: {summary}")
        print(f"  UMLS md: {umls_md}  PubMed md: {pubmed_md}")
        flat = [r for sr in result.last_sub_results for r in sr.get("results", [])]
        top1 = getattr(flat[0], "concept_id", None) if flat else None
        print(f"  Top-1: {top1}  (expected={expected})")
        # tail of final_answer (markdown 섹션 노출)
        print("  --- final_answer tail ---")
        print(result.final_answer[-400:].replace("\n", "\n    "))

        for tool in expected_ext:
            md_total += 1
            if tool == "umls" and umls_md:
                md_correct += 1
            elif tool == "pubmed" and pubmed_md:
                md_correct += 1

    base.close()

    print("\n" + "=" * 70)
    print(f" external markdown 정확도: {md_correct}/{md_total} ({md_correct/md_total*100:.0f}%)")
    print(f" §3-1-5 #2 ≥ 95% : {'PASS' if md_correct/md_total >= 0.95 else 'FAIL'}")


if __name__ == "__main__":
    main()
