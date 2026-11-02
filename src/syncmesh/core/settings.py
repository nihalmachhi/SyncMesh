"""Environment settings for one replica."""

from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings for one independently stored node."""

    model_config = SettingsConfigDict(env_prefix="SYNCMESH_", env_file=".env", extra="ignore")
    node_id: str = "node-a"
    db_path: str = "data/node-a/node.db"
    peers: str = ""
    sync_interval_seconds: float = Field(default=5, gt=0)
    cors_origins: str = "http://localhost:5173"
    environment: Literal["dev", "test", "production"] = "dev"
    admin_token: SecretStr | None = None
    peer_secret: SecretStr | None = None
    peer_auth_window_seconds: int = Field(default=300, ge=1, le=3600)
    rate_limit_requests: int = Field(default=120, ge=1, le=10000)
    rate_limit_window_seconds: int = Field(default=60, ge=1, le=3600)
    sync_byte_budget: int = Field(default=65536, ge=1024, le=10_000_000)

    @field_validator("admin_token", "peer_secret", mode="before")
    @classmethod
    def empty_secret_is_unset(cls, value):
        """Treat empty environment variables like an absent secret."""
        return None if value == "" else value

    def peer_urls(self) -> tuple[str, ...]:
        """Split configured peer URLs."""
        return tuple(url.strip().rstrip("/") for url in self.peers.split(",") if url.strip())

    def origins(self) -> list[str]:
        """Split allowed browser origins."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
