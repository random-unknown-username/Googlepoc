# Google TV Emulator

A Python application that emulates a **Google TV / Chromecast** device on your local network.

It announces itself via mDNS (`_googlecast._tcp.local.`) so it appears in Google Home and
compatible cast apps, and serves a web UI where you can view and **copy** the device name
and cast device ID with a single click.

---

## Features

| Feature | Detail |
|---|---|
| mDNS broadcast | Appears as a Google TV on the local network |
| Copy device name | One-click copy from the web UI |
| Copy cast device ID | One-click copy from the web UI |
| Persistent identity | Device name & ID are saved in `.device_config.json` |
| Chromecast endpoints | `/setup/eureka_info` and `/ssdp/device-desc.xml` |
| JSON API | `GET /api/info` returns device identity as JSON |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the emulator

```bash
python main.py
```

### 3. Open the web UI

Navigate to **http://localhost:8008** in your browser.

You will see your device name and cast device ID, each with a **Copy** button.

---

## Configuration

On first run, `.device_config.json` is created with a generated device name and UUID.
Edit this file to change the device name or fix the cast device ID:

```json
{
  "cast_device_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "device_name": "Google TV (Emulated)"
}
```

---

## API Endpoints

| Path | Description |
|---|---|
| `GET /` | Web UI (device name + cast device ID with copy buttons) |
| `GET /api/info` | JSON: device name, cast device ID, model, port |
| `GET /setup/eureka_info` | Chromecast-compatible device info |
| `GET /ssdp/device-desc.xml` | UPnP device description |
