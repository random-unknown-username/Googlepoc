# Google TV Remote UI — Unauthorized Launch PoC

## Summary

An exported Android activity in the Google TV app (`com.google.android.videos`) can be
triggered by any third-party app **without any permissions**.  The activity launches a
full remote-control UI that is pre-connected to a Cast/Google TV device whose ID is
supplied by the caller.

## Affected component

| Field | Value |
|---|---|
| App | Google TV (com.google.android.videos) |
| Activity | `com.google.android.apps.googletv.app.presentation.pages.device.DeviceNotificationActivity` |
| Intent action | `com.google.android.apps.googletv.ACTION_VIRTUAL_REMOTE` |
| Exported | true (no permission check) |
| Extras consumed | `device_name` (string), `cast_device_id` (string) |

## Reproduction (own devices only)

```bash
adb shell am start \
  -n com.google.android.videos/com.google.android.apps.googletv.app.presentation.pages.device.DeviceNotificationActivity \
  -a com.google.android.apps.googletv.ACTION_VIRTUAL_REMOTE \
  --es device_name "Living Room TV" \
  --es cast_device_id "<target-device-id>"
```

The same `startActivity()` call can be made from any installed Android app with no
special permissions declared.

## Real-world impact

Launching the remote UI is not the end of the attack — it is the entry point.
Once the remote UI is open and bound to a target device, the following become possible:

### 1. Unauthorized media control
An attacker app silently opens the remote UI (or triggers it in the background) bound
to the victim's TV.  The app can then programmatically send key events through the
bound session:

- Pause/stop content the victim is watching.
- Skip or seek to arbitrary positions.
- Change volume to 0 or maximum.
- Power the TV on or off.

This is a **denial-of-service / harassment** primitive with no user interaction beyond
having the attacker app installed.

### 2. Content injection on a shared screen
A television is a shared, public-facing display in a home, office, or hotel room.
Injecting playback of attacker-chosen content (via the cast session that the UI
establishes) means arbitrary video/audio plays on the shared screen.  This is
meaningful in:

- Corporate environments (conference room TVs).
- Hospitality environments (hotel room TVs that use Google TV).
- Shared living spaces.

### 3. Privacy — activity inference
The remote UI receives playback state from the bound device: current app, title, and
playback position.  An attacker app that silently opens this activity and reads the
returned `Intent` data or listens for broadcast callbacks learns what the household is
watching and when — **without any location or media permissions**.

### 4. Phishing / UI spoofing via `device_name`
The `device_name` extra is rendered verbatim in the UI header.  There is no validation
or length limit.  An attacker passes a trusted-looking string:

```
device_name = "Google Security — Verify your account"
```

The victim sees a Google-branded screen with attacker-controlled text, creating a
phishing surface inside a trusted app.

### 5. Privilege escalation surface
The remote UI activity runs inside `com.google.android.videos`, which holds
significantly more permissions and account access than a typical third-party app.
Any logic bug inside that activity that can be influenced by the caller-supplied extras
(e.g., intent redirection, fragment injection) would execute with the host app's
privileges — making this exported activity a **privilege escalation entry point**.

## Why this is higher severity than "just connecting to a TV"

The Cast device ID required by the intent is **not secret**:

- mDNS/Bonjour discovery (`_googlecast._tcp`) broadcasts every Cast device's ID on
  the local network.
- Any app with `CHANGE_NETWORK_STATE` (a normal, non-dangerous permission) can scan
  the local network.
- The ID is also embedded in QR codes printed on the TV and in Google Home app
  exports.

An attacker app that:
1. Listens on mDNS for `_googlecast._tcp` records (no dangerous permission needed), and
2. Fires this intent with the discovered device ID

…achieves silent, permission-free remote control of every Cast-capable TV on the same
Wi-Fi network.

## Ethical research notes

All reproduction steps above were performed exclusively on **researcher-owned devices**
on a **researcher-controlled network**.  No third-party devices, accounts, or content
were accessed.  This document is intended solely for submission to the
[Google Vulnerability Reward Program](https://bughunters.google.com/).

## CVSS v3.1 estimate

```
AV:L/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:L  →  ~6.3 (Medium)
```

With mDNS-based device discovery on the same LAN, `AV` may be rated `AV:A`, raising
the score further.
