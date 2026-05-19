"""Entrypoint: `opspilot-gateway` console script."""

from __future__ import annotations

import uvicorn


def main() -> None:
    uvicorn.run("opspilot.gateway.app:app", host="0.0.0.0", port=8090)
