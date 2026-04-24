"""DAG 빌드 + 위상 정렬 (Kahn 알고리즘) — LLM 호출 불필요."""
from __future__ import annotations

from collections import deque


def topological_sort(sub_queries: list[dict]) -> list[int]:
    """sub_queries 의존성 DAG 위상 정렬.

    Args:
        sub_queries: [{"id": int, "sub_query": str, "depends_on": [int]}, ...]

    Returns:
        해결 순서 (id 리스트)

    Raises:
        ValueError: cyclic dependency 발견 시
    """
    if not sub_queries:
        return []

    ids = {q["id"] for q in sub_queries}
    in_degree: dict[int, int] = {qid: 0 for qid in ids}
    edges: dict[int, list[int]] = {qid: [] for qid in ids}

    for q in sub_queries:
        for dep in q.get("depends_on", []):
            if dep not in ids:
                raise ValueError(
                    f"sub_query id={q['id']}가 존재하지 않는 dep id={dep}을 참조"
                )
            edges[dep].append(q["id"])
            in_degree[q["id"]] += 1

    queue: deque[int] = deque(qid for qid, d in in_degree.items() if d == 0)
    order: list[int] = []
    while queue:
        qid = queue.popleft()
        order.append(qid)
        for next_qid in edges[qid]:
            in_degree[next_qid] -= 1
            if in_degree[next_qid] == 0:
                queue.append(next_qid)

    if len(order) != len(ids):
        unresolved = ids - set(order)
        raise ValueError(f"Cyclic dependency 감지: 미해결 id = {unresolved}")
    return order


def max_depth(sub_queries: list[dict]) -> int:
    """DAG 최대 깊이 (over-decomposition 감지용)."""
    if not sub_queries:
        return 0
    by_id = {q["id"]: q for q in sub_queries}
    memo: dict[int, int] = {}

    def _depth(qid: int) -> int:
        if qid in memo:
            return memo[qid]
        deps = by_id[qid].get("depends_on", [])
        if not deps:
            memo[qid] = 1
        else:
            memo[qid] = 1 + max(_depth(d) for d in deps)
        return memo[qid]

    return max(_depth(qid) for qid in by_id)
