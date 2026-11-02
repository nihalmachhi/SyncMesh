"""Uvicorn application factory; importing this module has no database side effects."""

from fastapi import FastAPI

from syncmesh.node.api import create_app as build_app


def create_app() -> FastAPI:
    """Create an ASGI app using environment-provided node settings."""
    return build_app()
