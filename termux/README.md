# Android Auto Diagnostic Tool – Termux (Python)

A set of Python scripts that perform the same diagnostic work as the Android
APK, but run entirely in **[Termux](https://termux.dev)** — no Android Studio
or separate device required.

---

## What it does

| File | Role |
|---|---|
| `aad_tool.py` | Interactive CLI entry point |
| `aad_server.py` | TCP diagnostic server (logs every inbound connection) |
| `aad_launcher.py` | Sends the Intent via Android's `am` command |
| `requirements.txt` | Optional Python dependencies |

---

## Prerequisites

### 1. Install Termux

Download from [F-Droid](https://f-droid.org/en/packages/com.termux/) (recommended) or the Play Store.

### 2. Install Python inside Termux

```bash
pkg update && pkg upgrade
pkg install python
```

### 3. (Optional) Install `rich` for coloured output

```bash
pip install rich
```

> **Without `rich`** the tool still works — output is plain monochrome text.

### 4. Copy the scripts to your device

You can push the files with `adb`:

```bash
adb push termux/ /data/data/com.termux/files/home/aad_tool/
```

Or clone / download directly inside Termux:

```bash
pkg install git
git clone https://github.com/<your-fork>
```

---

## Usage

### Interactive mode (recommended)

```bash
cd ~/aad_tool
python aad_tool.py
```

The tool will prompt you for each parameter, then:

1. Start a TCP listener on the chosen port.
2. Send an `am start` Intent to Android Auto's `WirelessStartupActivity`.
3. Log every incoming connection attempt (timestamp, remote address, raw bytes).
4. On Ctrl-C: stop the server and save the full log to a timestamped file.

### Command-line mode (non-interactive)

```bash
python aad_tool.py \
    --ip 192.168.1.100 \
    --port 5288 \
    --network "MyHomeWifi" \
    --bt "Galaxy S24" \
    --flags "key1=val1,key2=val2"
```

### Server-only mode (no Intent launch)

```bash
python aad_tool.py --ip 192.168.1.100 --port 5288 --no-launch
```

---

## Intent parameters sent to Android Auto

| Parameter | Intent extra key | Type |
|---|---|---|
| IP address | `ip_address` | String |
| Port | `port` | Integer |
| Service network name | `service_network_name` | String |
| Bluetooth device name | `bluetooth_device_name` | String |
| Extra flags | any custom key | String |

The target component is:

```
com.google.android.projection.gearhead/
  com.google.android.projection.gearhead.WirelessStartupActivity
```

---

## Log output

### On-screen (example)

```
[09:41:22.001] Parameters: ip=192.168.1.100  port=5288
[09:41:22.512] >>> TCP listener started on 0.0.0.0:5288
[09:41:22.513] Server status: LISTENING
[09:41:22.514] Launching: am start -n ...
[09:41:23.102] Intent dispatched successfully.
[09:41:24.871] ─── [09:41:24.871] Connection from 192.168.1.100:49320
[09:41:24.873]   [192.168.1.100:49320] received 48 bytes
[09:41:24.874]   HEX : 47 45 54 20 2F 61 75 74 6F ...
[09:41:24.875]   TEXT: GET /auto ...
```

### Saved file

Logs are saved to:
```
aad_diagnostic_YYYYMMDD_HHMMSS.txt
```

in the current working directory (override with `--output-dir /path/to/dir`).

---

## Permissions note

`am start` works from Termux without root on most Android 10+ devices.
If you see _"Error: Activity not started, unable to resolve …"_ it means
Android Auto is not installed or the activity is not exported on your ROM.

---

## Differences from the APK

| Feature | APK | Termux Python |
|---|---|---|
| GUI | ✅ | ❌ (CLI only) |
| No install required | ❌ | ✅ (just copy files) |
| Root / special perms | ❌ | ❌ |
| Coloured output | ✅ | ✅ (with `rich`) |
| Log to file | ✅ | ✅ |
| Works on any Android | Only 10+ | Only 10+ (Termux) |
