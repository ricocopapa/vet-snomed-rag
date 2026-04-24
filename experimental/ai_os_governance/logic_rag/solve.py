"""DAG 위상 순서대로 재귀 해결 + 답변 합성."""
from __future__ import annotations

import os
from pathlib import Path

# .env 자동 로드 (decompose.py와 동일 패턴)
_ENV_PATH = Path.home() / "claude-cowork" / "07_Projects" / "vet-snomed-rag" / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#"):
            continue
        if "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def solve_subquery(
    sub_query: str,
    context: list[str],
    model: str = "gemini-3.1-flash-lite-preview",
) -> str:
    """단일 서브 쿼리 해결 (선행 답변 컨텍스트 활용)."""
    from google import genai

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    context_block = "\n".join(f"- {c}" for c in context) if context else "(선행 답변 없음)"
    prompt = f"""다음 컨텍스트를 활용해 서브 쿼리에 답변하세요.

선행 답변 컨텍스트:
{context_block}

서브 쿼리: {sub_query}

간결하게 1-3문장으로 답변:"""
    return client.models.generate_content(model=model, contents=prompt).text.strip()


def solve_dag(
    sub_queries: list[dict],
    order: list[int],
    model: str = "gemini-3.1-flash-lite-preview",
) -> dict[int, str]:
    """위상 순서대로 모든 서브 쿼리 해결.

    Returns: {sub_query_id: answer_text}
    """
    by_id = {q["id"]: q for q in sub_queries}
    answers: dict[int, str] = {}
    for qid in order:
        q = by_id[qid]
        context = [answers[d] for d in q.get("depends_on", []) if d in answers]
        answers[qid] = solve_subquery(q["sub_query"], context, model=model)
    return answers


def synthesize(
    original_query: str,
    sub_queries: list[dict],
    answers: dict[int, str],
    model: str = "gemini-3.1-flash-lite-preview",
) -> str:
    """모든 서브 답변을 통합한 최종 답변."""
    from google import genai

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    by_id = {q["id"]: q for q in sub_queries}
    answer_block = "\n".join(
        f"- [{qid}] {by_id[qid]['sub_query']} → {ans}" for qid, ans in answers.items()
    )
    prompt = f"""원본 질의에 대한 최종 답변을 작성하세요.

원본 질의: {original_query}

서브 답변 (Logic RAG DAG 해결 결과):
{answer_block}

위 서브 답변을 통합하여 5-10문장으로 최종 답변 작성:"""
    return client.models.generate_content(model=model, contents=prompt).text.strip()


def run_logic_rag_e2e(query: str, max_subqueries: int = 5) -> dict:
    """Logic RAG 전체 파이프라인 E2E 실행.

    Returns:
        {
            "query": str,
            "sub_queries": [...],
            "order": [...],
            "max_depth": int,
            "answers": {id: str},
            "final_answer": str,
        }
    """
    from .dag import max_depth, topological_sort
    from .decompose import decompose_query

    sub_queries = decompose_query(query, max_subqueries=max_subqueries)
    order = topological_sort(sub_queries)
    depth = max_depth(sub_queries)
    answers = solve_dag(sub_queries, order)
    final = synthesize(query, sub_queries, answers)
    return {
        "query": query,
        "sub_queries": sub_queries,
        "order": order,
        "max_depth": depth,
        "answers": answers,
        "final_answer": final,
    }
