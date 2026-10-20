# Debloat & privacy module

Goal: fewer background processes, no ads on the home screen, fewer trackers, snappier UI - without
breaking inputs, remote, casting, or the apps the owner uses.

## 1. Audit
`tv.py audit -s S -o tv-tuneup-<model>/audit.json` sorts every package into:
`remove` (known junk), `disable` (known telemetry/background), `ask-remove` (installed but unused 30 days),
`ask` (feature trade-off: voice, mirroring, DLNA, updates), `launcher-swap`, `review` (unknown vendor
package), `keep`. Rules come from `scripts/data/packages.json`; `never_touch_patterns` are always kept.

For `review` packages, decide with evidence, not names:
- `dumpsys package <pkg>`: what starts it (BOOT_COMPLETED, CONNECTIVITY), INTERNET + PACKAGE_USAGE_STATS
  (usage tracking), shared system UID (risky to disable), activities (is it a user-facing feature?).
- `dumpsys meminfo` - is it resident? Usage stats - was it ever opened?
- When unsure, leave it. Disable (not uninstall) anything you're not certain about.

## 2. Plan the owner approves (one message, grouped)
- **Removing** (unused apps + known junk), **Disabling** (telemetry/background services),
  **Your call** (voice assistant, mirroring, DLNA, vendor updates, launcher swap), **Settings**.
- Always state: everything is reversible; third-party apps that are fully uninstalled come back from the
  Play Store, system apps come back with one command.

## 3. Apply order
1. Keyboard: if the default IME is a third-party keyboard (Kika, etc.), put Gboard
   (`com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME`) in `ime` - the plan
   switches it before removing the old one.
2. Remove Play Auto Installs (`android.autoinstalls.config.*`) - otherwise removed partner apps come back.
3. Disable telemetry/background services; set screensaver off *before* disabling an ambient screensaver.
4. Settings: ad-block DNS (`dns.adguard-dns.com`; alternatives NextDNS/ControlD profiles), animations 0.5.
   Verify DNS: `dumpsys connectivity | grep PrivateDns` shows `ValidatedPrivateDnsAddresses`, and
   `ping -c1 doubleclick.net` resolves to 0.0.0.0/127.0.0.1.
   Note: DNS blocking can break ad-supported free tiers and some web players - mention it. Seen in a real
   run: Dailymotion's player never starts because its event servers (`*.dm-event.net`) are blocked. Find the
   culprit with the WebView/Chrome DevTools network panel (failed requests = `ERR_CONNECTION_REFUSED`); the
   fix is the owner's call (allow-list it in a NextDNS/ControlD profile, or accept it).
5. Launcher swap (only with approval) - see below.

## 4. Launcher swap (removes home-screen ads and frees ~100+ MB RAM)
Options (Play Store, no ads): **Projectivy Launcher** (`com.spocky.projengmenu`) or **FLauncher**
(`me.efesser.flauncher`, open source). Measured on a 1.8 GB Hisense/Vu TV: Projectivy ~71-81 MB PSS vs
FLauncher (Flutter) ~102-124 MB vs Google TV home ~135 MB - prefer Projectivy on low-RAM TVs, and measure
(cold start, 60 s idle, 3 samples of `dumpsys meminfo <pkg>`) rather than assume. Projectivy onboarding:
answer No to usage/crash reporting and notification access; media and TV-listing permissions can be denied
("Deny and don't ask again"); leave its accessibility service off unless the owner wants its automations. Install by opening
`market://details?id=<pkg>` with `am start -a android.intent.action.VIEW -d ... -p com.android.vending`,
screenshot, and press CENTER on **Install**; poll `pm list packages <pkg>`.
Then, in one step: disable the stock launcher **and** its fallback home
(Google TV: `com.google.android.apps.tv.launcherx` + `com.google.android.tungsten.setupwraith`;
Android TV: `com.google.android.tvlauncher` [+ `com.google.android.leanbacklauncher` if present]),
press HOME, confirm the new launcher is the resumed activity, screenshot.
- FLauncher ships with **Firebase crash reporting + analytics ON** - open its settings (top-right gear)
  and turn both off.
- Settings stay reachable via the launcher's gear and the remote's settings key.
- Rollback re-enables the stock launcher.
- **Leftover non-TV tiles** (vendor stubs like "Disclaimer Customization" or a "Device Assistant" cleaner)
  show up in third-party launchers because they declare a Leanback launcher entry. Hide them in the launcher
  (FLauncher/Projectivy: long-press > hide) instead of disabling vendor system packages you can't verify.
- **Moving/video backgrounds** (owners often ask): Projectivy's video wallpapers and its wallpaper plugins
  (e.g. Overflight) are **premium-only**; Android TV has no live-wallpaper support. Free options: the
  **Aerial Views** screensaver (Play Store; shows only when idle, zero cost while watching), or the open-source
  **Glow Home** launcher (looping video background, ~25-30 MB PSS, from github.com/Nikhil-9/tellycat - it
  also hosts **TellyCat**, an optional animated pet for the home screen). A playing video background costs a
  hardware decoder and ~20 MB while the home screen is visible - measure on low-RAM TVs.

## 4b. Free storage (when the owner asks, or /data is above ~80%)
Removing preinstalled apps for user 0 only frees their **updates and data** - the APKs stay in read-only
firmware. What actually frees space (measure each with `df -h /data`; real run: ~390 MB):
- **Reset Play updates of disabled system apps**: `cmd package uninstall-system-updates <pkg>`
  (Google TV home ~60 MB, Assistant ~50 MB, Ambient mode ~40 MB). This **re-enables** the package -
  immediately `pm disable-user` it again and press HOME to confirm the launcher (see gotchas).
- **Speech services voice data** (`com.google.android.tts`, ~100 MB): `pm clear` it only if the owner doesn't
  use voice/TTS (it re-downloads on demand).
- **Test leftovers**: VLC (~90 MB) and pushed pattern videos (~265 MB) - `tv.py cleanup` handles both.
- **Caches**: `pm trim-caches 999G` (part of `tv.py cleanup`).
Explain that "free storage" on a 8 GB TV is mostly the firmware partitions; promising gigabytes is wrong.

## 5. Verify
Reboot; `tv.py info` (launcher, IME, DNS persisted); launch each kept app
(`monkey -p <pkg> 1`, then check the resumed activity); press the Input key and screenshot the inputs
panel; Cast port 8009 still open. Report before/after with
`tv.py report --before tv-tuneup-<model>/backup -s S` (RAM, /data storage, installed/disabled packages,
which processes no longer run and how much each used). MemAvailable is noisy - run `tv.py cleanup --stop ...`
first so the same apps are closed.

## Things not to do
- Don't disable TV input services, HDMI/CEC, Bluetooth, remote pairing (`*autopair*`), audio/Dolby services,
  Play Services, Play Store, WebView, system UI, TV settings, or anything sharing the system UID unless
  verified on that exact model.
- Don't run "cleaner/booster" apps or force background process limits; they cause app reloads and lag.
