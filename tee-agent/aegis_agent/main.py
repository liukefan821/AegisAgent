"""
main.py — entry point for the AegisAgent TEE agent HTTP server.

Local development:
    cd tee-agent
    uvicorn aegis_agent.main:app --port 8080 --reload

Production (Phala Cloud TDX CVM):
    uvicorn aegis_agent.main:app --host 0.0.0.0 --port 8080

Environment variables:
    AEGIS_MOCK_QUOTE=true|false  — controls QuoteGenerator backend.
        Default: true (mock backend for local dev).
        Set to false in docker-compose.yaml for Phala Cloud deploy.

The frontend (Next.js, http://localhost:3000) polls:
    GET /health                — every ~10s for the status panel
    GET /quotes/{digest}       — on AttestationBadge click after on-chain event
"""

import logging

from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local", override=False)

from aegis_agent.http_server import app  # uvicorn imports `app` from here

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

__all__ = ["app"]
