"""Hybrid logical clocks for stable causal ordering across replicas."""

from collections.abc import Callable
from dataclasses import dataclass
from time import time_ns


@dataclass(frozen=True, order=True)
class HLC:
    """A physical millisecond component plus a logical tie-break counter."""

    physical_ms: int
    logical: int = 0

    def __post_init__(self) -> None:
        if self.physical_ms < 0 or self.logical < 0:
            raise ValueError("HLC components must be non-negative")


class HybridLogicalClock:
    """Monotonic local HLC that observes remote timestamps."""

    def __init__(self, initial: HLC | None = None, clock_ms: Callable[[], int] | None = None):
        self._last = initial or HLC(0, 0)
        self._clock_ms = clock_ms or (lambda: time_ns() // 1_000_000)

    @property
    def last(self) -> HLC:
        """Return the last emitted or observed timestamp."""
        return self._last

    def tick(self) -> HLC:
        """Generate a timestamp greater than the previous local timestamp."""
        now = self._clock_ms()
        if now > self._last.physical_ms:
            self._last = HLC(now, 0)
        else:
            self._last = HLC(self._last.physical_ms, self._last.logical + 1)
        return self._last

    def observe(self, remote: HLC) -> HLC:
        """Merge a remote timestamp and advance beyond both clocks."""
        now = self._clock_ms()
        physical = max(now, self._last.physical_ms, remote.physical_ms)
        if physical == self._last.physical_ms == remote.physical_ms:
            logical = max(self._last.logical, remote.logical) + 1
        elif physical == self._last.physical_ms:
            logical = self._last.logical + 1
        elif physical == remote.physical_ms:
            logical = remote.logical + 1
        else:
            logical = 0
        self._last = HLC(physical, logical)
        return self._last
