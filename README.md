# android-tv-tuneup — a Claude skill

Let Claude clean up, speed up and calibrate any **Android TV / Google TV** from your laptop over Wi-Fi.
No root, nothing flashed, and every change can be undone.

What Claude does with it:

- **Debloat & privacy**: audits which apps you actually use, then removes or disables unused apps, partner
  bloat, telemetry services and the auto-reinstaller. It can swap the ad-filled home screen for an ad-free
  launcher, set ad-blocking DNS, switch away from shady preinstalled keyboards and speed up animations.
- **Audio & soundbar**: checks eARC/ARC, sets passthrough so the soundbar gets real Dolby Atmos/DTS,
  enables Netflix Atmos on MediaTek TVs, and gives soundbar mode advice.
- **Picture calibration**: switches to the accurate picture mode and turns off unnecessary processing. It
  generates exact 4K SDR/HDR10 test patterns, walks you through "read the number" black and white level
  tuning, and sets up HDR and Dolby Vision modes. It also checks that 4K, HDR, Dolby Vision and Atmos are
  really what's playing.
- **Phone camera assist** (optional): with the free *IP Webcam* app, your Android phone becomes Claude's
  view of the screen.

Claude asks what you want first and shows you the plan for each phase before changing anything. It keeps
a backup, a change log and a rollback file.

## Install

```bash
git clone <this repo> ~/.claude/skills/android-tv-tuneup
```
On Windows, use the path `%USERPROFILE%\.claude\skills\android-tv-tuneup`. Then ask Claude Code something
like *"debloat my Google TV"* or *"set up my TV and soundbar for the best picture and sound"*.

## Requirements
- Claude Code on Windows, macOS or Linux, on the same Wi-Fi as the TV.
- Python 3.8+ and `adb` (Android platform-tools). Claude can fetch platform-tools if you agree.
- For test patterns and camera analysis only: `numpy`, `Pillow`, and `ffmpeg` with libx265.
- On the TV, once: enable Developer options, turn on USB (or Wireless) debugging, and tap **Allow** when asked.

## Safety
- Packages are disabled or uninstalled for the user only, never deleted from the system image, so a
  factory reset always restores stock.
- Never touched: system UI, TV inputs, HDMI/CEC, Bluetooth and remote pairing, audio/Dolby services,
  Play Services and Play Store, WebView.
- Each plan is shown as a dry run first. `tv.py rollback` undoes an applied plan.
- Bloat rules are verified per model. The `verified` field in `scripts/data/packages.json` lists the TVs
  each rule was confirmed on, and unknown vendor packages are only flagged for review. Pull requests that
  add verified rules for more TVs are welcome.

## Files
```
SKILL.md                    the workflow Claude follows
reference/connect.md        enabling debugging, pairing, finding the TV
reference/debloat.md        audit, plan, launcher swap, DNS
reference/audio.md          eARC, passthrough, Atmos, soundbars
reference/picture.md        modes, pattern calibration, HDR & Dolby Vision, camera
reference/gotchas.md        pitfalls from real runs
scripts/tv.py               discover/info/backup/audit/apply/rollback/ui/keys/playing
scripts/gen_patterns.py     exact 10-bit SDR + HDR10 test patterns
scripts/camera.py           IP Webcam helper (find, lock exposure/WB, shots, ramp tint)
scripts/data/packages.json  package rules and settings recipes
```

## Disclaimer
Use at your own risk. Changing system apps is supported by Android's own tools and is reversible, but TV
firmware varies. Nothing here bypasses DRM, accounts or region locks.
