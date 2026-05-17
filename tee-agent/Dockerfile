# AegisAgent TEE Agent — runs inside Phala Cloud TDX CVM
# Build:  docker build -t <dockerhub-user>/aegis-tee-agent:latest ./tee-agent
# Run:    via docker-compose.yaml on Phala Cloud (see repo root)

FROM python:3.11-slim

LABEL maintainer="AegisAgent Team (NTU SC6107 Group 1)"
LABEL description="TEE-verified autonomous DeFi agent HTTP server"

WORKDIR /app

# Install dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY aegis_agent/ aegis_agent/

# Expose HTTP server port
EXPOSE 8080

# Health check — matches our /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Run uvicorn (production mode — no --reload)
CMD ["uvicorn", "aegis_agent.main:app", "--host", "0.0.0.0", "--port", "8080"]
