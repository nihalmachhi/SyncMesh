"""Paginated, authenticated, observable peer synchronization."""

import asyncio
import hashlib
import hmac
import logging
import random
import time
from collections.abc import Callable
from datetime import UTC, datetime

import httpx

from syncmesh.node.storage.repository import ReceiveOutcome, Repository
from syncmesh.protocol.messages import ExchangeRequest, ExchangeResponse

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
        client_factory: Callable[..., httpx.AsyncClient] = httpx.AsyncClient,
        random_source: random.Random | None = None,
    ) -> None:
        self.repo = repo
        self.peer_urls = peer_urls
        self.interval = interval
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

    async def _get_vector(self, client: httpx.AsyncClient, url: str) -> dict[str, int]:
        """Read a peer vector with authentication for deployments that require it."""
        request = client.build_request("GET", url + "/sync/vector", headers=self._headers())
        response = await client.send(request)
        response.raise_for_status()
        return response.json()["vector"]

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
        while True:
            remote_vector = await self._get_vector(client, url)
            outgoing = self.repo.since(remote_vector, PAGE_SIZE)
            lag = len(outgoing)
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
            if len(outgoing) < PAGE_SIZE and len(response.operations) < PAGE_SIZE:
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
            for url, result in zip(eligible, results, strict=True):
                if isinstance(result, BaseException):
                    error = result if isinstance(result, Exception) else RuntimeError(str(result))
                    self._record_failure(url, error)
                    continue
                for key in totals:
                    totals[key] += int(result[key])
            return totals
        finally:
            if owned_client:
                await client.aclose()

    async def run(self) -> None:
        """Run periodic peer exchange with one client reused across all cycles."""
        async with self.client_factory(timeout=3) as client:
            while True:
                await self.exchange(client)
                await asyncio.sleep(self.interval)
