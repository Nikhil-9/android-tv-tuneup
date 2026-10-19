# Connecting to the TV

## 1. Laptop side
- `adb` must be installed. `tv.py` finds it on PATH, in the Android SDK folder, or via the `ADB` env var.
- If missing, ask the owner before downloading **Android SDK Platform-Tools** from the official page
  (developer.android.com/tools/releases/platform-tools, ~7 MB zip). Unzip into the workspace and set
  `ADB=<path>/platform-tools/adb(.exe)`.
- Laptop and TV must be on the same network. Guest Wi-Fi / "AP isolation" blocks this.

## 2. TV side (the owner does this once, with the remote)
| TV | Path to Developer options |
|---|---|
| Google TV (Chromecast GTV, Sony, TCL, Hisense, Vu, Philips GTV) | Settings > System > About > press **Android TV OS build** 7 times |
| Older Android TV | Settings > Device Preferences > About > press **Build** 7 times |
| Nvidia Shield | Settings > Device Preferences > About > Build (7 times) |
| Xiaomi Mi TV / PatchWall | Settings > Device Preferences > About > Build (7 times) |

Then: **Developer options > USB debugging = On**. On Android 11+ there may also be **Wireless debugging**:
- If only USB debugging exists (common on Android 11 TVs), most TVs still open port 5555 on Wi-Fi - try
  `tv.py connect HOST` first.
- If 5555 is closed but Wireless debugging exists: owner opens it > "Pair device with pairing code"; run
  `adb pair HOST:PAIRPORT CODE`, then `adb connect HOST:PORT` with the port shown on that screen.
- Some TVs need a reboot after enabling USB debugging before 5555 opens.

## 3. Authorize
`unauthorized` means the TV is showing **"Allow USB debugging?"** - the owner ticks **Always allow from this
computer** and presses **Allow**. This is a security check only a person with the remote can pass; never try
to bypass it.

## 4. Finding the TV
`tv.py discover` scans the laptop's /24 for ports 5555 (adb), 8008/8009 (Cast) and 6466/6467 (Android TV
remote). Cast `eureka_info` gives the TV's friendly name. Phones with randomised MACs appear too - the TV is
the host with the remote/cast ports.

## 5. If the connection drops
- TV in standby / turned off drops Wi-Fi: wait for the owner to turn it on, then `tv.py connect` again.
- Opening Miracast/screen-mirroring switches Wi-Fi to Wi-Fi Direct for ~20 s; reconnect after.
- `offline` that persists: toggle USB debugging off/on, or `adb disconnect` then connect.
