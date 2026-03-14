"""
aad_server.py – Android Auto Diagnostic TCP Server
===================================================
Opens a TCP socket listener on the specified port, logs every incoming
connection attempt (timestamp, remote address, first 256-512 bytes of data),
and reports whether the connection was immediately closed or sent data.

Designed to run inside Termux on Android.
"""

from __future__ import annotations

import socket
import threading
import time
from datetime import datetime
from typing import Callable

# Maximum bytes to capture per connection
CAPTURE_BYTES = 512
# Read timeout (seconds)
READ_TIMEOUT = 5.0


class DiagnosticServer:
    """
    A simple TCP server that logs all inbound connection attempts.

    Parameters
    ----------
    port:
        TCP port to listen on.
    log_fn:
        Callable that accepts a single string.  Will be called from
        background threads – implementations must be thread-safe
        (e.g. just call ``print`` or append to a thread-safe list).
    on_status:
        Optional callable invoked with ``True`` when the server starts
        and ``False`` when it stops.
    """

    def __init__(
        self,
        port: int,
        log_fn: Callable[[str], None],
        on_status: Callable[[bool], None] | None = None,
        bind_address: str = "0.0.0.0",
    ) -> None:
        self.port = port
        # bind_address defaults to all interfaces so that Android Auto can reach
        # the listener regardless of which local network interface it uses.
        # Restrict to a specific IP (e.g. your Wi-Fi address) for narrower exposure.
        self.bind_address = bind_address
        self._log = log_fn
        self._on_status = on_status or (lambda _: None)
        self._server_sock: socket.socket | None = None
        self._running = False
        self._thread: threading.Thread | None = None

    # ── Public API ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the listener in a background thread."""
        if self._running:
            self._log("Server already running.")
            return
        self._running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the listener and close the server socket."""
        self._running = False
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
            self._server_sock = None

    def wait(self) -> None:
        """Block until the server thread finishes (useful in CLI mode)."""
        if self._thread:
            self._thread.join()

    # ── Internal ────────────────────────────────────────────────────────────────

    def _accept_loop(self) -> None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ss:
                ss.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                ss.bind((self.bind_address, self.port))
                ss.listen(8)
                self._server_sock = ss
                self._log(f">>> TCP listener started on {self.bind_address}:{self.port}")
                self._on_status(True)
                while self._running:
                    try:
                        ss.settimeout(1.0)
                        try:
                            client, addr = ss.accept()
                        except socket.timeout:
                            continue
                        t = threading.Thread(
                            target=self._handle_connection,
                            args=(client, addr),
                            daemon=True,
                        )
                        t.start()
                    except OSError:
                        break
        except Exception as exc:
            self._log(f"ERROR starting server: {exc}")
        finally:
            self._running = False
            self._on_status(False)
            self._log(">>> TCP listener stopped")

    def _handle_connection(
        self, sock: socket.socket, addr: tuple[str, int]
    ) -> None:
        remote = f"{addr[0]}:{addr[1]}"
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self._log(f"─── [{ts}] Connection from {remote}")
        try:
            sock.settimeout(READ_TIMEOUT)
            with sock:
                data = sock.recv(CAPTURE_BYTES)
            if data:
                hex_str = " ".join(f"{b:02X}" for b in data)
                text = "".join(chr(b) if 0x20 <= b <= 0x7E else "." for b in data)
                self._log(f"  [{remote}] received {len(data)} bytes")
                self._log(f"  HEX : {hex_str}")
                self._log(f"  TEXT: {text}")
            else:
                self._log(f"  [{remote}] connection closed immediately (no data sent)")
        except socket.timeout:
            self._log(f"  [{remote}] read timeout ({READ_TIMEOUT}s) – no data received")
        except OSError as exc:
            self._log(f"  [{remote}] read error: {exc}")
