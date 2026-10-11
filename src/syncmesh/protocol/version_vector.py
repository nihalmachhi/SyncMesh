"""Pure version-vector causal comparison and merge."""

from enum import StrEnum


class CausalOrder(StrEnum):
    """Causal relation between two vectors."""

    BEFORE = "before"
    AFTER = "after"
    EQUAL = "equal"
    CONCURRENT = "concurrent"


Vector = dict[str, int]


def compare(left: Vector, right: Vector) -> CausalOrder:
    """Return causal order without consulting wall clocks."""
    keys = left.keys() | right.keys()
    lte = all(left.get(key, 0) <= right.get(key, 0) for key in keys)
    gte = all(left.get(key, 0) >= right.get(key, 0) for key in keys)
    if lte and gte:
        return CausalOrder.EQUAL
    if lte:
        return CausalOrder.BEFORE
    if gte:
        return CausalOrder.AFTER
    return CausalOrder.CONCURRENT


def merge(*vectors: Vector) -> Vector:
    """Return pointwise maximum of all vectors."""
    result: Vector = {}
    for vector in vectors:
        for node, seq in vector.items():
            result[node] = max(seq, result.get(node, 0))
    return result


def concurrent(left: Vector, right: Vector) -> bool:
    """Return whether neither vector causally follows the other."""
    return compare(left, right) is CausalOrder.CONCURRENT
