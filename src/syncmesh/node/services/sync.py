"""Paginated, authenticated, observable peer synchronization."""

import asyncio
import hashlib
import hmac
import logging
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import cast

import httpx

from syncmesh.node.storage.repository import ReceiveOutcome, Repository
from syncmesh.protocol.digest import differing_ranges
from syncmesh.protocol.messages import ExchangeRequest, ExchangeResponse, NodeSnapshot
from syncmesh.protocol.optimize import select_operations

LOGGER = logging.getLogger(__name__)
PAGE_SIZE = 500
MAX_BACKOFF_SECONDS = 60.0


class Synchronizer:
    """Keep one node's operation log exchanged with configured peers."""

    def __init__(
        self,
        repo: Repository,
        peer_urls: tuple[str, ...],
        interval: float,
        peer_secret: str | None = None,
        byte_budget: int = 65_536,
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
        random_source: random.Random | None = None,
    ) -> None:
        self.repo = repo
        self.peer_urls = peer_urls
        self.interval = interval
        self.current_interval = interval
        self.byte_budget = byte_budget
        self.peer_secret = peer_secret
        self.client_factory = client_factory
        self.random = random_source or random.SystemRandom()
        self.online = True
        self._failures: dict[str, int] = {}
        self._retry_at: dict[str, float] = {}
        self._peer_status: dict[str, dict[str, object]] = {
            url: {"online": False, "lag": 0, "last_error": None} for url in peer_urls
        }

    @property
    def peer_status(self) -> dict[str, dict[str, object]]:
        """Return a copy of the latest lag and health view for each peer."""
        return {url: dict(status) for url, status in self._peer_status.items()}

    def _headers(self, body: bytes = b"") -> dict[str, str]:
        """Sign a request body and timestamp when shared-secret auth is configured."""
        if self.peer_secret is None:
            return {}
        timestamp = str(int(time.time()))
        signature = hmac.new(
            self.peer_secret.encode("utf-8"),
            timestamp.encode("ascii") + b"." + body,
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-SyncMesh-Timestamp": timestamp,
            "X-SyncMesh-Signature": signature,
        }

    async def _get_peer_state(self, client: httpx.AsyncClient, url: str) -> dict[str, object]:
        """Read a peer vector and the compacted prefix it cannot replay from its log."""
        request = client.build_request("GET", url + "/sync/vector", headers=self._headers())
        response = await client.send(request)
        response.raise_for_status()
        return response.json()

    async def _send_snapshot(
        self, client: httpx.AsyncClient, url: str, snapshot: NodeSnapshot
    ) -> None:
        """Send a signed materialized snapshot to a stale peer."""
        request = client.build_request(
            "POST", url + "/sync/snapshot", json=snapshot.model_dump(mode="json")
        )
        request.headers.update(self._headers(request.content))
        response = await client.send(request)
        response.raise_for_status()

    async def _receive_snapshot(self, client: httpx.AsyncClient, url: str) -> NodeSnapshot:
        """Fetch a peer snapshot when its compacted prefix is ahead of local history."""
        request = client.build_request("GET", url + "/sync/snapshot", headers=self._headers())
        response = await client.send(request)
        response.raise_for_status()
        return NodeSnapshot.model_validate(response.json())

    async def _post_exchange(
        self, client: httpx.AsyncClient, url: str, request_body: ExchangeRequest
    ) -> ExchangeResponse:
        """Send one authenticated bounded operation page."""
        payload = request_body.model_dump(mode="json")
        request = client.build_request("POST", url + "/sync/exchange", json=payload)
        request.headers.update(self._headers(request.content))
        response = await client.send(request)
        response.raise_for_status()
        return ExchangeResponse.model_validate(response.json())

    async def _exchange_peer(self, client: httpx.AsyncClient, url: str) -> dict[str, int | float]:
        """Exchange bounded pages until both peers report no further work."""
        started = datetime.now(UTC)
        started_clock = time.perf_counter()
        sent = received = duplicates = conflicts_before = 0
        conflicts_before = len(self.repo.conflicts())
        buffered = 0
        lag = 0
        local_digest = self.repo.operation_digest()
        digest_response = await client.get(url + "/sync/digest", headers=self._headers())
        digest_response.raise_for_status()
        digest_mismatches = differing_ranges(local_digest, digest_response.json().get("ranges", {}))
        remote_state = await self._get_peer_state(client, url)
        local_vector = self.repo.stats()["vector"]
        local_compacted = self.repo.compacted_vector()
        remote_vector = cast(dict[str, int], remote_state.get("vector", {}))
        remote_compacted = cast(dict[str, int], remote_state.get("compacted_vector", {}))
        if any(
            local_vector.get(origin, 0) < sequence for origin, sequence in remote_compacted.items()
        ):
            snapshot = await self._receive_snapshot(client, url)
            self.repo.apply_snapshot(snapshot)
        if any(
            remote_vector.get(origin, 0) < sequence for origin, sequence in local_compacted.items()
        ):
            await self._send_snapshot(client, url, self.repo.export_snapshot())
        if local_compacted or remote_compacted:
            remote_state = await self._get_peer_state(client, url)
        while True:
            remote_vector = cast(dict[str, int], remote_state.get("vector", {}))
            candidates = self.repo.since(remote_vector, PAGE_SIZE)
            outgoing = select_operations(candidates, remote_vector, self.byte_budget)
            lag = len(candidates)
            sender_vector = self.repo.stats()["vector"]
            request_body = ExchangeRequest(
                sender_node_id=self.repo.node_id,
                sender_vector=sender_vector,
                operations=outgoing,
            )
            response = await self._post_exchange(client, url, request_body)
            sent += len(outgoing)
            outcomes = self.repo.receive_batch(response.operations)
            received += sum(outcome is ReceiveOutcome.APPLIED for outcome in outcomes)
            duplicates += response.duplicates_ignored
            duplicates += sum(outcome is ReceiveOutcome.DUPLICATE for outcome in outcomes)
            buffered += sum(outcome is ReceiveOutcome.BUFFERED for outcome in outcomes)
            remote_state = await self._get_peer_state(client, url)
            remote_vector = cast(dict[str, int], remote_state.get("vector", {}))
            local_vector = self.repo.stats()["vector"]
            more_to_send = bool(self.repo.since(remote_vector, PAGE_SIZE))
            more_to_receive = bool(self.repo.since(local_vector, PAGE_SIZE))
            if not more_to_send and not more_to_receive:
                break

        duration = (time.perf_counter() - started_clock) * 1000
        conflict_count = max(0, len(self.repo.conflicts()) - conflicts_before)
        self.repo.record_sync(url, started, duration, sent, received, duplicates, conflict_count)
        self._peer_status[url] = {
            "online": True,
            "lag": lag,
            "last_error": None,
            "last_sync": started.isoformat(),
            "ops_sent": sent,
            "ops_received": received,
            "buffered": buffered,
            "duration_ms": duration,
            "digest_mismatches": len(digest_mismatches),
        }
        self._failures.pop(url, None)
        self._retry_at.pop(url, None)
        LOGGER.info(
            "peer exchange completed",
            extra={
                "peer_id": url,
                "ops_sent": sent,
                "ops_received": received,
                "duplicates_ignored": duplicates,
                "buffered": buffered,
                "duration_ms": duration,
            },
        )
        return {
            "sent": sent,
            "received": received,
            "duplicates": duplicates,
            "buffered": buffered,
            "conflicts": conflict_count,
            "duration_ms": duration,
        }

    def _record_failure(self, url: str, error: Exception) -> None:
        """Apply bounded exponential retry delay and record the peer error."""
        failures = self._failures.get(url, 0) + 1
        self._failures[url] = failures
        base_delay = min(MAX_BACKOFF_SECONDS, self.interval * (2 ** min(failures - 1, 6)))
        delay = base_delay * self.random.uniform(0.85, 1.15)
        retry_at = time.monotonic() + delay
        self._retry_at[url] = retry_at
        previous = self._peer_status.get(url, {})
        self._peer_status[url] = {
            **previous,
            "online": False,
            "last_error": str(error),
            "retry_in_seconds": round(delay, 2),
        }
        LOGGER.warning(
            "peer exchange failed",
            extra={"peer_id": url, "attempt": failures, "retry_in_seconds": delay},
            exc_info=error,
        )

    async def exchange(self, client: httpx.AsyncClient | None = None) -> dict[str, int]:
        """Synchronize peers concurrently using a reusable client when supplied."""
        if not self.online:
            return {"sent": 0, "received": 0, "duplicates": 0, "buffered": 0}
        owned_client = client is None
        if client is None:
            client = self.client_factory(timeout=3)
        try:
            now = time.monotonic()
            eligible = [url for url in self.peer_urls if self._retry_at.get(url, 0) <= now]
            results = await asyncio.gather(
                *(self._exchange_peer(client, url) for url in eligible), return_exceptions=True
            )
            totals = {"sent": 0, "received": 0, "duplicates": 0, "buffered": 0}
            had_failure = False
            for url, result in zip(eligible, results, strict=True):
                if isinstance(result, BaseException):
                    had_failure = True
                    error = result if isinstance(result, Exception) else RuntimeError(str(result))
                    self._record_failure(url, error)
                    continue
                for key in totals:
                    totals[key] += int(result[key])
            if had_failure:
                self.current_interval = min(max(self.interval, self.current_interval + 0.5), 60.0)
            else:
                self.current_interval = max(min(self.interval, self.current_interval * 0.9), 0.5)
            return totals
        finally:
            if owned_client:
                await client.aclose()

    async def run(self) -> None:
        """Run periodic peer exchange with one client reused across all cycles."""
        async with self.client_factory(timeout=3) as client:
            while True:
                await self.exchange(client)
                jitter = self.random.uniform(0.9, 1.1)
                await asyncio.sleep(self.current_interval * jitter)
