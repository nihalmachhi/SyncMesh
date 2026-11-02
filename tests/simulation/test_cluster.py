"""Seeded replication schedule checks."""

from syncmesh.simulation.cluster import run_schedule, run_simulation


def test_cluster_replays_same_seed_identically():
    """A recorded seed reproduces identical schedule output."""
    assert run_schedule(42) == run_schedule(42)


def test_cluster_batch_converges_across_randomized_schedules():
    """Every simulated permutation satisfies the current merge invariants."""
    result = run_simulation(seed=100, schedules=200)

    assert result["schedules_run"] == 200
    assert result["converged"] == 200
    assert result["failed_seeds"] == []
