"""Environment settings for one replica."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for one independently stored node."""

    model_config = SettingsConfigDict(env_prefix="SYNCMESH_", env_file=".env", extra="ignore")
    node_id: str = "node-a"
    db_path: str = "data/node-a/node.db"
    peers: str = ""
    sync_interval_seconds: float = Field(default=5, gt=0)
    cors_origins: str = "http://localhost:5173"

    def peer_urls(self) -> tuple[str, ...]:
        """Split configured peer URLs."""
        return tuple(url.strip().rstrip("/") for url in self.peers.split(",") if url.strip())

    def origins(self) -> list[str]:
        """Split allowed browser origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
