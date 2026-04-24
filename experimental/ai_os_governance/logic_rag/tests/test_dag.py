"""DAG 위상 정렬 단위 테스트 (LLM 호출 없이 순수 알고리즘 검증)."""
from __future__ import annotations

import pytest

from logic_rag.dag import max_depth, topological_sort


def test_empty():
    assert topological_sort([]) == []
    assert max_depth([]) == 0


def test_single_node():
    sub = [{"id": 0, "sub_query": "Q0", "depends_on": []}]
    assert topological_sort(sub) == [0]
    assert max_depth(sub) == 1


def test_linear_chain():
    """0 → 1 → 2"""
    sub = [
        {"id": 0, "sub_query": "Q0", "depends_on": []},
        {"id": 1, "sub_query": "Q1", "depends_on": [0]},
        {"id": 2, "sub_query": "Q2", "depends_on": [1]},
    ]
    assert topological_sort(sub) == [0, 1, 2]
    assert max_depth(sub) == 3


def test_diamond():
    """0 → 1 → 3, 0 → 2 → 3"""
    sub = [
        {"id": 0, "sub_query": "Q0", "depends_on": []},
        {"id": 1, "sub_query": "Q1", "depends_on": [0]},
        {"id": 2, "sub_query": "Q2", "depends_on": [0]},
        {"id": 3, "sub_query": "Q3", "depends_on": [1, 2]},
    ]
    order = topological_sort(sub)
    assert order[0] == 0
    assert order[-1] == 3
    assert {order[1], order[2]} == {1, 2}
    assert max_depth(sub) == 3


def test_cycle_rejected():
    """0 → 1 → 2 → 0 (cycle)"""
    sub = [
        {"id": 0, "sub_query": "Q0", "depends_on": [2]},
        {"id": 1, "sub_query": "Q1", "depends_on": [0]},
        {"id": 2, "sub_query": "Q2", "depends_on": [1]},
    ]
    with pytest.raises(ValueError, match="Cyclic"):
        topological_sort(sub)


def test_unknown_dep_rejected():
    sub = [
        {"id": 0, "sub_query": "Q0", "depends_on": [99]},
    ]
    with pytest.raises(ValueError, match="존재하지 않는"):
        topological_sort(sub)


def test_independent_nodes():
    """0, 1, 2 (no edges) — 모두 starting node"""
    sub = [
        {"id": 0, "sub_query": "Q0", "depends_on": []},
        {"id": 1, "sub_query": "Q1", "depends_on": []},
        {"id": 2, "sub_query": "Q2", "depends_on": []},
    ]
    order = topological_sort(sub)
    assert sorted(order) == [0, 1, 2]
    assert max_depth(sub) == 1
