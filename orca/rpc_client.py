"""Manage 32-bit ORCA worker subprocess and JSON-RPC communication."""

import subprocess
import threading
import time
import os
import sys
from collections.abc import Callable

from orca.json_rpc import encode_request, encode_shutdown, decode_line

ProgressCallback = Callable[[int, int, str], None]  # current, total, entry_name
LogCallback = Callable[[str, str], None]  # level, message


class OrcaRpcClient:
    """Manages the 32-bit Python worker subprocess.

    Usage:
        client = OrcaRpcClient(worker_python="python.exe", worker_script="orca_worker.py",
                               ide_path="C:\\...\\IDE", runtime_path="C:\\...\\Runtime")
        client.start()
        result = client.call("ping", {})
        client.stop()
    """

    def __init__(self, worker_python: str, worker_script: str,
                 ide_path: str, runtime_path: str, pb_version: str = "25"):
        self._worker_python = worker_python
        self._worker_script = worker_script
        self._ide_path = ide_path
        self._runtime_path = runtime_path
        self._pb_version = pb_version
        self._proc: subprocess.Popen | None = None
        self._req_id = 0
        self._pending: dict[int, threading.Event] = {}
        self._results: dict[int, dict] = {}
        self._lock = threading.Lock()
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self._on_progress: ProgressCallback | None = None
        self._on_log: LogCallback | None = None

    def set_progress_callback(self, cb: ProgressCallback | None):
        self._on_progress = cb

    def set_log_callback(self, cb: LogCallback | None):
        self._on_log = cb

    def start(self) -> str | None:
        """Launch the worker subprocess. Returns None on success, error string on failure."""
        if self._running:
            return None

        cmd = [
            self._worker_python,
            self._worker_script,
            f"--ide={self._ide_path}",
            f"--runtime={self._runtime_path}",
            f"--pb-version={self._pb_version}",
        ]

        try:
            self._proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,  # unbuffered: crucial for real-time pipe reads on Windows
            )
        except FileNotFoundError:
            return f"32-bit Python not found at: {self._worker_python}"
        except Exception as e:
            return str(e)

        self._running = True
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

        # Quick check: did the worker crash immediately?
        time.sleep(0.5)
        if self._proc and self._proc.poll() is not None:
            self._running = False
            return f"Worker exited immediately with code {self._proc.returncode}. Is it 32-bit Python?"

    def stop(self):
        """Gracefully shut down the worker."""
        if not self._running or not self._proc:
            return
        try:
            self._proc.stdin.write(encode_shutdown())
            self._proc.stdin.flush()
            self._proc.wait(timeout=5)
        except Exception:
            try:
                self._proc.kill()
            except Exception:
                pass
        self._running = False

    def is_alive(self) -> bool:
        return self._running and self._proc is not None and self._proc.poll() is None

    def call(self, method: str, params: dict, timeout: float = 60.0) -> dict:
        """Send an RPC request and wait for the response."""
        if not self.is_alive():
            exit_code = self._proc.poll() if self._proc else None
            return {"error": {"code": -99, "message": f"Worker not running (exit code: {exit_code})"}}

        with self._lock:
            self._req_id += 1
            req_id = self._req_id
            event = threading.Event()
            self._pending[req_id] = event

        try:
            data = encode_request(req_id, method, params)
            self._proc.stdin.write(data)
            self._proc.stdin.flush()
        except Exception as e:
            with self._lock:
                self._pending.pop(req_id, None)
            return {"error": {"code": -99, "message": f"Write failed: {e}"}}

        if not event.wait(timeout):
            with self._lock:
                self._pending.pop(req_id, None)
            return {"error": {"code": -99, "message": "Request timed out"}}

        with self._lock:
            result = self._results.pop(req_id, {})
        return result

    def _read_loop(self):
        """Read JSON lines from worker stdout in a background thread."""
        leftover = b""
        while self._running and self._proc and self._proc.poll() is None:
            try:
                chunk = self._proc.stdout.read(4096)
                if not chunk:
                    time.sleep(0.01)
                    continue
                leftover += chunk
            except Exception:
                break

            while b"\n" in leftover:
                line, leftover = leftover.split(b"\n", 1)
                msg = decode_line(line)
                if msg is not None:
                    self._handle_message(msg)

    def _handle_message(self, msg: dict):
        msg_id = msg.get("id")
        if msg_id is not None:
            # Response to a pending request
            with self._lock:
                event = self._pending.pop(msg_id, None)
                if event is not None:
                    self._results[msg_id] = msg
                    event.set()
            return

        method = msg.get("method")
        params = msg.get("params", {})

        if method == "progress":
            if self._on_progress:
                try:
                    self._on_progress(
                        params.get("current", 0),
                        params.get("total", 0),
                        params.get("entry", ""),
                    )
                except Exception:
                    pass
        elif method == "log":
            if self._on_log:
                try:
                    self._on_log(params.get("level", "INFO"), params.get("message", ""))
                except Exception:
                    pass
