"""
aad_launcher.py – Android Auto WirelessStartupActivity Intent Launcher
========================================================================
Uses the Android ``am`` (Activity Manager) command available inside Termux
to send an explicit Intent to the Android Auto wireless startup activity.

This requires the Termux app to have been granted the "Draw over other apps"
permission (or for Android Auto to be the current top activity), but in
practice ``am start`` works from a Termux shell without extra permissions on
most Android 10+ devices.
"""

from __future__ import annotations

import subprocess
from typing import Callable


# Android Auto package and activity
AA_PACKAGE = "com.google.android.projection.gearhead"
AA_ACTIVITY = f"{AA_PACKAGE}/com.google.android.projection.gearhead.WirelessStartupActivity"


def launch_wireless_startup(
    ip: str,
    port: int,
    service_network: str = "",
    bt_device: str = "",
    extra_flags: dict[str, str] | None = None,
    log_fn: Callable[[str], None] = print,
) -> bool:
    """
    Launch the Android Auto WirelessStartupActivity via ``am start``.

    Parameters
    ----------
    ip:
        Target IP address string passed as the ``ip_address`` extra.
    port:
        Target TCP port passed as the ``port`` integer extra.
    service_network:
        Optional Wi-Fi SSID / service network name.
    bt_device:
        Optional Bluetooth device name.
    extra_flags:
        Optional dict of additional string extras (key → value).
    log_fn:
        Callable used for logging output lines.

    Returns
    -------
    bool
        True if ``am start`` exited with code 0, False otherwise.
    """
    cmd = [
        "am", "start",
        "-n", AA_ACTIVITY,
        "--es", "ip_address", ip,
        "--ei", "port", str(port),
    ]

    if service_network:
        cmd += ["--es", "service_network_name", service_network]
    if bt_device:
        cmd += ["--es", "bluetooth_device_name", bt_device]
    if extra_flags:
        for k, v in extra_flags.items():
            cmd += ["--es", k, v]

    log_fn(f"Launching: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.stdout.strip():
            log_fn(f"am stdout: {result.stdout.strip()}")
        if result.stderr.strip():
            log_fn(f"am stderr: {result.stderr.strip()}")
        if result.returncode == 0:
            log_fn("Intent dispatched successfully.")
            return True
        else:
            log_fn(f"ERROR: am start returned exit code {result.returncode}")
            return False
    except FileNotFoundError:
        log_fn(
            "ERROR: 'am' command not found.  "
            "This script must run inside Termux on an Android device."
        )
        return False
    except subprocess.TimeoutExpired:
        log_fn("ERROR: am start timed out after 10 seconds.")
        return False
    except Exception as exc:  # noqa: BLE001
        log_fn(f"ERROR launching activity: {exc}")
        return False
