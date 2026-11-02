"""Content-addressed image storage and resumable in-memory chunk assembly."""

import hashlib
from pathlib import Path


def store_blob(data: bytes, root: Path) -> str:
    """Write a blob under its SHA-256 digest and return the lowercase digest."""
    digest = hashlib.sha256(data).hexdigest()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / digest
    if not destination.exists():
        destination.write_bytes(data)
    return digest


class ChunkAssembler:
    """Collect sequential chunks and verify the requested final content hash."""

    def __init__(self, expected_sha256: str, total_bytes: int) -> None:
        if len(expected_sha256) != 64 or total_bytes < 0:
            raise ValueError("invalid blob digest or size")
        self.expected_sha256 = expected_sha256.lower()
        self.total_bytes = total_bytes
        self._buffer = bytearray()

    @property
    def offset(self) -> int:
        """Return the next accepted chunk offset for resumable transfer."""
        return len(self._buffer)

    def append(self, offset: int, chunk: bytes) -> bool:
        """Accept the next contiguous chunk; return true once verified complete."""
        if offset != len(self._buffer):
            raise ValueError("chunk offset does not match the next expected position")
        if len(self._buffer) + len(chunk) > self.total_bytes:
            raise ValueError("chunk exceeds the declared blob size")
        self._buffer.extend(chunk)
        if len(self._buffer) == self.total_bytes:
            digest = hashlib.sha256(self._buffer).hexdigest()
            if digest != self.expected_sha256:
                raise ValueError("completed blob digest does not match")
            return True
        return False

    def bytes(self) -> bytes:
        """Return the complete verified payload; reject incomplete transfers."""
        if len(self._buffer) != self.total_bytes:
            raise ValueError("blob transfer is incomplete")
        if hashlib.sha256(self._buffer).hexdigest() != self.expected_sha256:
            raise ValueError("completed blob digest does not match")
        return bytes(self._buffer)
