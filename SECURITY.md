# Security policy

SyncMesh is an educational lab, not a production inventory service. Keep node
ports on a trusted network. In non-development environments,
configure distinct high-entropy `SYNCMESH_ADMIN_TOKEN` and shared
`SYNCMESH_PEER_SECRET` values. Peer requests use a timestamped HMAC signature;
use TLS when traffic crosses a network you do not control.

Please report vulnerabilities privately to the repository owner before opening
a public issue. Include the affected version, reproduction steps, and impact.
