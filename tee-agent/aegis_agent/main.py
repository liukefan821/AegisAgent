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
import os

from aegis_agent.http_server import app  # uvicorn imports `app` from here
from aegis_agent.quote_generator import QuoteGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Initialise QuoteGenerator based on env var — decision_engine (Step 6)
# imports this instance to generate quotes for each decision.
_mock_quote = os.getenv("AEGIS_MOCK_QUOTE", "true").lower() in ("true", "1", "yes")
quote_generator = QuoteGenerator(mock=_mock_quote, dstack_socket=os.getenv("DSTACK_SOCKET_PATH"))

__all__ = ["app", "quote_generator"]
