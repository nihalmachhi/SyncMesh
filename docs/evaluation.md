# Reproducible evaluation

Run `make reproduce` (or `uv run python -m syncmesh.simulation.run --reproduce`)
to regenerate `reports/reproduce.json` and, once the site exists,
`site/src/data/results.generated.json`.

The report contains seeded operation schedules, gossip simulations across ring,
star, Erdős–Rényi, and small-world graphs, and a duplicate-name scoring run on
ten fixed synthetic pairs. The pair set and seed are intentionally small and
do not estimate production accuracy or performance. Gossip byte counts are
approximate payload-ID counts, not measured HTTP traffic. All report rows are
marked synthetic.

Use `make simulate SEED=42` to replay one schedule. A failure includes its seed
in the command output, so the same case can be reproduced with that seed.
