"""Lightweight JSON-lines RPC codec. No external dependencies."""

import json


def encode_request(req_id: int, method: str, params: dict) -> bytes:
    """Encode a JSON-RPC request as bytes with newline terminator."""
    msg = {"id": req_id, "method": method, "params": params}
    return json.dumps(msg, ensure_ascii=False).encode("utf-8") + b"\n"


def encode_shutdown() -> bytes:
    """Encode a shutdown notification."""
    return json.dumps({"method": "shutdown"}).encode("utf-8") + b"\n"


def decode_line(line: bytes) -> dict | None:
    """Decode a single JSON line. Returns None for parse failures."""
    try:
        return json.loads(line.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
