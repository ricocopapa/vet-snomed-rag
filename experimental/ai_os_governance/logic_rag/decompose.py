"""Query Decomposition — LLM으로 사용자 질의를 서브 쿼리 그래프로 분해."""
from __future__ import annotations

import json
import os
from pathlib import Path

# vet-snomed-rag .env 자동 로드 (GOOGLE_API_KEY)
_ENV_PATH = Path.home() / "claude-cowork" / "07_Projects" / "vet-snomed-rag" / ".env"
if _ENV_PATH.exists():
    for _line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#"):
            continue
        if "=" in _line:
            _k, _v = _line.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


_DECOMPOSE_PROMPT_TEMPLATE = """당신은 Logic RAG 시스템의 query decomposer입니다.
사용자 질의를 {max_subqueries}개 이하 서브 쿼리로 분해하세요.

원칙:
- 각 서브 쿼리는 단일 답변 가능한 원자 질문이어야 합니다.
- 서브 쿼리 간 논리적 의존성이 있으면 depends_on으로 표시합니다.
- 의존성은 DAG (cyclic 금지) 형태여야 합니다.

질의: {query}

JSON 형식으로만 응답 (다른 텍스트 금지):
{{
  "sub_queries": [
    {{"id": 0, "sub_query": "...", "depends_on": []}},
    {{"id": 1, "sub_query": "...", "depends_on": [0]}}
  ]
}}"""


def decompose_query(
    query: str,
    max_subqueries: int = 5,
    model: str = "gemini-2.5-flash",
) -> list[dict]:
    """LLM으로 query를 sub-queries로 분해.

    Returns: [{"id": int, "sub_query": str, "depends_on": [int]}, ...]
    """
    from google import genai

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    prompt = _DECOMPOSE_PROMPT_TEMPLATE.format(
        max_subqueries=max_subqueries, query=query
    )
    response = client.models.generate_content(model=model, contents=prompt)
    text = response.text.strip()

    if text.startswith("```"):
        text = "\n".join(line for line in text.split("\n") if not line.startswith("```"))

    try:
        data = json.loads(text)
        return data["sub_queries"]
    except (json.JSONDecodeError, KeyError) as e:
        raise ValueError(f"Decomposition 응답 파싱 실패: {e}\nRaw: {text[:300]}")
