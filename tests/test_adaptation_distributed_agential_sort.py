"""test_adaptation_distributed_agential_sort.py — r183
Proves alice-hand wrote real neighbor-agent sort without cheating.
"""

import inspect
import pytest

from System.adaptation_lab.distributed_agential_sort import (
    agential_sort,
    SortResult,
)


def test_module_imports_cleanly():
    """Import succeeds — no syntax or dependency crime."""
    assert agential_sort is not None


def test_agential_sort_sorts_neighbor_only():
    values = [5, 1, 4, 2, 3]
    result: SortResult = agential_sort(values)

    assert result.sorted_values == [1, 2, 3, 4, 5]
    assert result.steps > 0
    assert result.clustering_score > result.baseline_clustering_score
    assert isinstance(result.trace, list)
    assert len(result.trace) > 0


def test_no_cheat_sort_calls_in_source():
    """The algorithm file itself must not contain forbidden central sort."""
    import System.adaptation_lab.distributed_agential_sort as mod

    src = inspect.getsource(mod)
    assert ".sort(" not in src, "cheat: .sort( found in algorithm"
    assert "sorted(" not in src, "cheat: sorted( found in algorithm"


def test_agential_sort_empty_and_small():
    assert agential_sort([]).sorted_values == []
    assert agential_sort([42]).sorted_values == [42]
    res = agential_sort([2, 1])
    assert res.sorted_values == [1, 2]
    assert res.clustering_score > res.baseline_clustering_score
