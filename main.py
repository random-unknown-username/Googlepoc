"""
Google TV Emulator
==================
Emulates a Google TV / Chromecast device on the local network by:
  - Announcing itself via mDNS under the _googlecast._tcp.local. service type
  - Serving the standard Chromecast discovery endpoints
  - Displaying a web UI where the device name and cast device ID can be copied

Usage
-----
    pip install -r requirements.txt
    python main.py

Then open  http://localhost:8008  in a browser.
The device will also appear in Google Home and compatible cast apps.
"""

import json
import os
import socket
import threading
import uuid

from flask import Flask, jsonify, render_template, request
from zeroconf import ServiceInfo, Zeroconf

# ---------------------------------------------------------------------------
# Persistent device identity
# ---------------------------------------------------------------------------
CONFIG_FILE = os.path.join(os.path.dirname(__file__), ".device_config.json")

CAST_PORT = 8008


def _load_or_create_config() -> dict:
    """Load device identity from disk, or generate and persist new values."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as fh:
            try:
                cfg = json.load(fh)
                # Validate required keys
                if "cast_device_id" in cfg and "device_name" in cfg:
                    return cfg
            except (json.JSONDecodeError, KeyError):
                pass

    cfg = {
        "cast_device_id": str(uuid.uuid4()),
        "device_name": "Google TV (Emulated)",
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
    return cfg


config = _load_or_create_config()
CAST_DEVICE_ID: str = config["cast_device_id"]
DEVICE_NAME: str = config["device_name"]

# ---------------------------------------------------------------------------
# Flask application
# ---------------------------------------------------------------------------
app = Flask(__name__)


@app.route("/")
def index():
    return render_template(
        "index.html",
        device_name=DEVICE_NAME,
        cast_device_id=CAST_DEVICE_ID,
        cast_port=CAST_PORT,
    )


@app.route("/api/info")
def api_info():
    """JSON endpoint returning device identity."""
    return jsonify(
        {
            "device_name": DEVICE_NAME,
            "cast_device_id": CAST_DEVICE_ID,
            "model_name": "Google TV",
            "cast_port": CAST_PORT,
        }
    )


@app.route("/setup/eureka_info")
def eureka_info():
    """
    Chromecast-compatible /setup/eureka_info endpoint.
    Real Chromecasts respond here with device details.
    """
    params = request.args.get("params", "")
    data: dict = {}
    if "name" in params or not params:
        data["name"] = DEVICE_NAME
    if "cast_device_id" in params or not params:
        data["cast_device_id"] = CAST_DEVICE_ID
    if "model_name" in params or not params:
        data["model_name"] = "Google TV"
    return jsonify(data)


@app.route("/ssdp/device-desc.xml")
def device_desc():
    """UPnP device description (Chromecast-compatible)."""
    xml = f"""<?xml version="1.0"?>
<root xmlns="urn:schemas-upnp-org:device-1-0">
  <specVersion><major>1</major><minor>0</minor></specVersion>
  <device>
    <deviceType>urn:dial-multiscreen-org:device:dial:1</deviceType>
    <friendlyName>{DEVICE_NAME}</friendlyName>
    <manufacturer>Google Inc.</manufacturer>
    <modelName>Google TV</modelName>
    <UDN>uuid:{CAST_DEVICE_ID}</UDN>
  </device>
</root>"""
    return app.response_class(xml, mimetype="application/xml")


# ---------------------------------------------------------------------------
# mDNS / Zeroconf advertisement
# ---------------------------------------------------------------------------

def _get_local_ip() -> str:
    """Return the best-guess LAN IP address of this machine."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def start_mdns_broadcast() -> tuple[Zeroconf, ServiceInfo]:
    """Register this device as a _googlecast._tcp.local. mDNS service."""
    local_ip = _get_local_ip()

    # Chromecast TXT record fields
    txt_records = {
        "id": CAST_DEVICE_ID,          # unique device identifier
        "fn": DEVICE_NAME,              # friendly name shown in cast UIs
        "md": "Google TV",              # model description
        "ve": "05",                     # receiver capabilities version
        "ic": "/setup/icon.png",        # icon path
        "ca": "4101",                   # capabilities bitmask
        "st": "0",                      # state (0 = idle)
        # bs: base station ID – Chromecast uses the first 12 hex chars of the
        # device UUID (with hyphens removed) as a short hardware identifier.
        "bs": CAST_DEVICE_ID[:12].replace("-", ""),  # base station ID
        "rs": "",                       # running status
    }

    service_name = f"{DEVICE_NAME}._googlecast._tcp.local."

    info = ServiceInfo(
        type_="_googlecast._tcp.local.",
        name=service_name,
        addresses=[socket.inet_aton(local_ip)],
        port=CAST_PORT,
        properties=txt_records,
        server=f"{socket.gethostname()}.local.",
    )

    zc = Zeroconf()
    # allow_name_change=True avoids NonUniqueNameException if the name was
    # already registered (e.g. from a previous run that didn't clean up).
    zc.register_service(info, allow_name_change=True)
    print(f"[mDNS] Registered '{DEVICE_NAME}' on {local_ip}:{CAST_PORT}")
    return zc, info


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  Google TV Emulator")
    print("=" * 60)
    print(f"  Device name  : {DEVICE_NAME}")
    print(f"  Cast device ID: {CAST_DEVICE_ID}")
    print(f"  Web UI        : http://localhost:{CAST_PORT}")
    print("=" * 60)

    # Start mDNS broadcast in a background thread so Flask can run normally
    zc, info = start_mdns_broadcast()

    try:
        # host="0.0.0.0" so LAN devices can reach the HTTP endpoints
        app.run(host="0.0.0.0", port=CAST_PORT, debug=False, use_reloader=False)
    finally:
        print("[mDNS] Unregistering service …")
        zc.unregister_service(info)
        zc.close()


if __name__ == "__main__":
    main()
