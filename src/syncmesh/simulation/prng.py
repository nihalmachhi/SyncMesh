"""Mulberry32 generator shared with the TypeScript website simulator."""


class Mulberry32:
    """Deterministic 32-bit PRNG with the same output sequence as JavaScript."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF

    def random(self) -> float:
        """Return one float in [0, 1), matching the project's TS implementation."""
        self.state = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        value = self.state
        value = ((value ^ (value >> 15)) * (value | 1)) & 0xFFFFFFFF
        mixed = (value + (((value ^ (value >> 7)) * (value | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF
        value ^= mixed
        value = (value ^ (value >> 14)) & 0xFFFFFFFF
        return value / 4294967296

    def randrange(self, stop: int) -> int:
        """Return a deterministic integer in ``range(stop)``."""
        if stop <= 0:
            raise ValueError("stop must be positive")
        return int(self.random() * stop)
