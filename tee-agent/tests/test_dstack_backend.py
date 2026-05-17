"""
test_dstack_backend.py — Unit tests for the Dstack TDX backend in QuoteGenerator.

Tests the real backend path with mocked Unix socket responses,
ensuring the socket call, JSON parsing, and mr_enclave extraction work.
"""

import json
import os
import socket
import tempfile
import threading
import pytest

from aegis_agent.quote_generator import (
    QuoteGenerator,
    QuoteGenerationError,
    HASH_SIZE,
)


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_hash(seed: int = 0) -> bytes:
    """Create a deterministic 32-byte hash for testing."""
    return bytes([(seed + i) % 256 for i in range(HASH_SIZE)])


def _make_fake_quote(report_data_hex: str) -> str:
    """Build a fake TDX quote long enough for MRTD extraction (≥352 bytes)."""
    # Pad to 400 bytes: header(304) + MRTD(32) + tail(64)
    header = b"\x00" * 304
    mrtd = b"\xab" * 32  # recognisable pattern at offset 304-336
    tail = b"\xcd" * 64
    return (header + mrtd + tail).hex()


def _run_mock_server(socket_path: str, response_body: dict, status: int = 200):
    """Run a one-shot Unix socket HTTP server that returns a canned response."""
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(socket_path)
    srv.listen(1)
    srv.settimeout(5)

    def handle():
        conn, _ = srv.accept()
        # Read request (we don't parse it)
        conn.recv(4096)
        body = json.dumps(response_body).encode()
        response = (
            f"HTTP/1.1 {status} OK\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"Connection: close\r\n"
            f"\r\n"
        ).encode() + body
        conn.sendall(response)
        conn.close()
        srv.close()

    t = threading.Thread(target=handle, daemon=True)
    t.start()
    return t


# ── Tests ──────────────────────────────────────────────────────────────────

class TestDstackBackendInit:
    """Tests for QuoteGenerator(mock=False) initialisation."""

    def test_missing_socket_raises(self):
        """Should raise QuoteGenerationError if socket doesn't exist."""
        with pytest.raises(QuoteGenerationError, match="not found"):
            QuoteGenerator(mock=False, dstack_socket="/nonexistent/sock")

    def test_init_with_existing_socket(self, tmp_path):
        """Should initialise when socket file exists."""
        sock_path = str(tmp_path / "dstack.sock")
        # Create a dummy file to simulate the socket existing
        with open(sock_path, "w") as f:
            f.write("")
        gen = QuoteGenerator(mock=False, dstack_socket=sock_path)
        assert gen.mock is False


class TestDstackBackendGenerate:
    """Tests for the real Dstack quote generation path."""

    def test_successful_quote_generation(self):
        """Full happy path: mock Unix socket returns a valid quote."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = os.path.join(tmpdir, "dstack.sock")

            fake_quote_hex = _make_fake_quote("deadbeef")
            server_thread = _run_mock_server(
                sock_path,
                {"quote": "0x" + fake_quote_hex},
            )

            gen = QuoteGenerator(mock=False, dstack_socket=sock_path)
            result = gen.generate(_make_hash(1), _make_hash(2))

            assert result.is_mock is False
            assert result.quote_hex == fake_quote_hex
            # MRTD at offset 304-336 should be 0xab * 32
            assert result.mr_enclave == "ab" * 32
            assert len(result.report_data) == 64
            server_thread.join(timeout=2)

    def test_short_quote_uses_sha256_mr_enclave(self):
        """If TDX quote is too short, mr_enclave = SHA-256(quote)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = os.path.join(tmpdir, "dstack.sock")

            short_quote = "aa" * 100  # 100 bytes, < 352
            server_thread = _run_mock_server(
                sock_path,
                {"quote": short_quote},
            )

            gen = QuoteGenerator(mock=False, dstack_socket=sock_path)
            result = gen.generate(_make_hash(3), _make_hash(4))

            assert result.is_mock is False
            import hashlib
            expected_mr = hashlib.sha256(bytes.fromhex(short_quote)).hexdigest()
            assert result.mr_enclave == expected_mr
            server_thread.join(timeout=2)

    def test_empty_quote_raises(self):
        """Should raise QuoteGenerationError when quote field is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = os.path.join(tmpdir, "dstack.sock")

            server_thread = _run_mock_server(
                sock_path,
                {"quote": ""},
            )

            gen = QuoteGenerator(mock=False, dstack_socket=sock_path)
            with pytest.raises(QuoteGenerationError, match="No 'quote' field"):
                gen.generate(_make_hash(5), _make_hash(6))
            server_thread.join(timeout=2)

    def test_socket_timeout_raises(self):
        """Should raise QuoteGenerationError on socket timeout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = os.path.join(tmpdir, "dstack.sock")
            # Create a server that accepts but never responds
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(sock_path)
            srv.listen(1)

            gen = QuoteGenerator(mock=False, dstack_socket=sock_path)
            # Override timeout to 0.5s for fast test
            import aegis_agent.quote_generator as qg
            original_timeout = qg.DSTACK_TIMEOUT
            qg.DSTACK_TIMEOUT = 0.5
            try:
                with pytest.raises(QuoteGenerationError, match="Timeout"):
                    gen.generate(_make_hash(7), _make_hash(8))
            finally:
                qg.DSTACK_TIMEOUT = original_timeout
                srv.close()

    def test_invalid_json_raises(self):
        """Should raise QuoteGenerationError on non-JSON response."""
        with tempfile.TemporaryDirectory() as tmpdir:
            sock_path = os.path.join(tmpdir, "dstack.sock")

            # Manually serve garbage
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(sock_path)
            srv.listen(1)

            def handle():
                conn, _ = srv.accept()
                conn.recv(4096)
                conn.sendall(
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Length: 11\r\n"
                    b"Connection: close\r\n"
                    b"\r\n"
                    b"not json!!!"
                )
                conn.close()
                srv.close()

            t = threading.Thread(target=handle, daemon=True)
            t.start()

            gen = QuoteGenerator(mock=False, dstack_socket=sock_path)
            with pytest.raises(QuoteGenerationError, match="JSON"):
                gen.generate(_make_hash(9), _make_hash(10))
            t.join(timeout=2)
