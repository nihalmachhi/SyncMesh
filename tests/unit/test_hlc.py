"""Hybrid logical clock invariants."""

from syncmesh.protocol.hlc import HLC, HybridLogicalClock


def test_hlc_tick_is_monotonic_when_wall_clock_moves_backwards():
    """Logical time advances when physical time regresses or stalls."""
    times = iter((100, 90, 90))
    clock = HybridLogicalClock(clock_ms=lambda: next(times))

    first, second, third = clock.tick(), clock.tick(), clock.tick()

    assert first == HLC(100, 0)
    assert second == HLC(100, 1)
    assert third == HLC(100, 2)


def test_hlc_observe_advances_past_remote_clock():
    """Receiving a later peer timestamp makes the next local timestamp later."""
    clock = HybridLogicalClock(HLC(100, 4), clock_ms=lambda: 90)

    observed = clock.observe(HLC(100, 8))

    assert observed == HLC(100, 9)
    assert clock.tick() > observed
