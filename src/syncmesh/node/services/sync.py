from __future__ import annotations

import asyncio

import httpx

from syncmesh.node.storage.repository import Repository
from syncmesh.protocol.messages import ExchangeRequest


class Synchronizer:
    def __init__(self, repo: Repository, peer_urls: tuple[str, ...], interval: float):
        self.repo, self.peer_urls, self.interval = repo, peer_urls, interval
        self.online = True

    async def exchange(self):
        sent = received = 0
        if not self.online:
            return {"sent": sent, "received": received}
        async with httpx.AsyncClient(timeout=3) as client:
            for url in self.peer_urls:
                try:
                    remote = (await client.get(url + "/sync/vector")).json()["vector"]
                    outgoing = self.repo.since(remote)
                    req = ExchangeRequest(
                        sender_node_id=self.repo.node_id,
                        sender_vector=self.repo.stats()["vector"],
                        operations=outgoing,
                    )
                    response = (
                        await client.post(url + "/sync/exchange", json=req.model_dump(mode="json"))
                    ).json()
                    sent += len(outgoing)
                    for op in response["operations"]:
                        from syncmesh.protocol.messages import Operation

                        self.repo.receive(Operation.model_validate(op))
                        received += 1
                except (httpx.HTTPError, ValueError, KeyError):
                    continue
        return {"sent": sent, "received": received}

    async def run(self):
        while True:
            await self.exchange()
            await asyncio.sleep(self.interval)
