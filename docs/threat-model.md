# Threat model

SyncMesh is designed for a local educational lab. It is not hardened for
untrusted internet access, production inventory, or personal data.

## Protected paths

- Admin writes and conflict review use a bearer token with constant-time
  comparison when configured.
- Peer exchange, digest, and snapshot routes use HMAC-SHA256 over the exact
  request body plus a timestamp. Requests outside the configured time window
  are rejected.
- Protected routes have a per-process fixed-window request limit. This is not a
  distributed limiter and does not replace network-level controls.
- Production mode fails closed if the admin token or peer secret is missing.

## Assumptions and limits

- Nodes that share a peer secret trust one another to report honest version
  vectors. A compromised peer can submit false acknowledgements or malformed
  but schema-valid state.
- The timestamp window limits stale replays but does not maintain a nonce cache.
  Configure TLS on any network that is not fully trusted.
- The admin token is a single shared credential, not per-user identity or
  authorization. Never put production secrets in a browser bundle.
- `/health`, `/stats`, and `/metrics` expose operational data without admin
  authentication. Keep the node ports on a trusted network.
- CORS is a browser policy and is not an authentication boundary.
- Local NLP and vision helpers are heuristic utilities; do not use their
  suggestions as automatic inventory edits.

See [SECURITY.md](../SECURITY.md) for reporting guidance.
