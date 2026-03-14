"""
aad_tool.py – Android Auto Diagnostic Tool (Termux / CLI edition)
==================================================================
Interactive command-line tool that:
  1. Prompts for connection parameters (IP, port, optional extras).
  2. Starts a local TCP listener so Android Auto's outbound connection
     attempt can be observed and logged.
  3. Sends an explicit Intent to Android Auto's WirelessStartupActivity
     via the Android ``am`` command.
  4. Saves the session log to a timestamped file.

Usage
-----
    python aad_tool.py [--ip IP] [--port PORT] [--network SSID]
                       [--bt BT_DEVICE] [--flags key=val,key2=val2]
                       [--no-launch]

Requirements
------------
    • Python 3.9+ (available via: pkg install python)
    • Must run inside Termux on an Android device
    • Optional rich display: pkg install python && pip install rich
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from aad_server import DiagnosticServer
from aad_launcher import launch_wireless_startup


# ── Optional rich terminal formatting ─────────────────────────────────────────
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    _console = Console()
    _USE_RICH = True
except ImportError:
    _console = None  # type: ignore[assignment]
    _USE_RICH = False


# ── Logging ────────────────────────────────────────────────────────────────────

_log_lines: list[str] = []
_log_lock = threading.Lock()


def _log(message: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {message}"
    with _log_lock:
        _log_lines.append(line)
    if _USE_RICH:
        colour = "red" if "ERROR" in message else "cyan" if ">>>" in message else "green"
        _console.print(f"[{colour}]{line}[/{colour}]")  # type: ignore[union-attr]
    else:
        print(line)


def _save_log(output_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"aad_diagnostic_{ts}.txt"
    with _log_lock:
        lines = list(_log_lines)
    log_file.write_text(
        "Android Auto Diagnostic Tool – Session Log\n"
        f"Saved: {ts}\n"
        + "─" * 60 + "\n"
        + "\n".join(lines)
        + "\n",
        encoding="utf-8",
    )
    return log_file


# ── UI helpers ─────────────────────────────────────────────────────────────────

def _banner() -> None:
    title = "Android Auto Diagnostic Tool (Termux)"
    if _USE_RICH:
        _console.print(Panel(Text(title, style="bold white"), style="blue"))  # type: ignore[union-attr]
    else:
        print("=" * 60)
        print(f"  {title}")
        print("=" * 60)


def _prompt(label: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        val = input(f"  {label}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return val or default


def _status(running: bool) -> None:
    if running:
        _log("Server status: LISTENING")
    else:
        _log("Server status: STOPPED")


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Android Auto Diagnostic Tool – Termux CLI"
    )
    parser.add_argument("--ip",      default="", help="Target IP address")
    parser.add_argument("--port",    default="", help="Target TCP port (1-65535)")
    parser.add_argument("--network", default="", help="Service network / Wi-Fi SSID")
    parser.add_argument("--bt",      default="", help="Bluetooth device name")
    parser.add_argument(
        "--flags",
        default="",
        help="Extra Intent extras as key=value pairs, comma-separated",
    )
    parser.add_argument(
        "--no-launch",
        action="store_true",
        help="Start the server only; do not launch the Android Auto activity",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory for the saved log file (default: current directory)",
    )
    args = parser.parse_args()

    _banner()
    print()

    # ── Gather parameters ──────────────────────────────────────────────────────
    ip   = args.ip   or _prompt("Target IP address",  "192.168.1.100")
    port_str = args.port or _prompt("Target port",    "5288")
    try:
        port = int(port_str)
        if not 1 <= port <= 65535:
            raise ValueError
    except ValueError:
        print(f"ERROR: '{port_str}' is not a valid port number (1–65535).")
        sys.exit(1)

    service_network = args.network or _prompt("Service network name (optional, Enter to skip)", "")
    bt_device       = args.bt      or _prompt("Bluetooth device name (optional, Enter to skip)", "")
    flags_raw       = args.flags   or _prompt("Extra flags (key=val,key2=val2, or Enter to skip)", "")

    extra_flags: dict[str, str] = {}
    for pair in flags_raw.split(","):
        kv = pair.strip().split("=", 1)
        if len(kv) == 2:
            extra_flags[kv[0].strip()] = kv[1].strip()

    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    print()
    _log(f"Parameters: ip={ip}  port={port}")
    if service_network:
        _log(f"  service_network={service_network}")
    if bt_device:
        _log(f"  bt_device={bt_device}")
    if extra_flags:
        _log(f"  extra_flags={extra_flags}")

    # ── Start diagnostic server ────────────────────────────────────────────────
    server = DiagnosticServer(port=port, log_fn=_log, on_status=_status)
    server.start()

    # Give the socket time to bind before launching the intent
    time.sleep(0.5)

    # ── Launch Android Auto (unless --no-launch) ───────────────────────────────
    if not args.no_launch:
        print()
        launch_wireless_startup(
            ip=ip,
            port=port,
            service_network=service_network,
            bt_device=bt_device,
            extra_flags=extra_flags or None,
            log_fn=_log,
        )

    # ── Wait for user to stop ──────────────────────────────────────────────────
    print()
    print("  Listening for connections… Press Ctrl+C to stop and save the log.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print()

    # ── Stop server and save log ───────────────────────────────────────────────
    server.stop()
    time.sleep(0.2)

    log_file = _save_log(output_dir)
    _log(f"Log saved to: {log_file}")

    print()
    if _USE_RICH:
        _console.print(Panel(f"[green]Log saved to:[/green] {log_file}", style="green"))  # type: ignore[union-attr]
    else:
        print(f"Log saved to: {log_file}")


if __name__ == "__main__":
    main()
