# Gotchas from real runs

Connection
- Android 11 TVs often have no "Wireless debugging", yet USB debugging alone opens 5555 on Wi-Fi.
- `unauthorized` = Allow prompt waiting on the TV. `offline` after standby = reconnect.
- Opening Miracast/screen-sharing drops the TV off Wi-Fi ~20 s.
- Shells: on Windows Git Bash rewrites `/sdcard/...` arguments to `C:/Program Files/Git/sdcard` - the Python
  helpers avoid this; if using raw adb in Git Bash set `MSYS_NO_PATHCONV=1`.

Packages
- `pm uninstall -k --user 0` fully removes third-party (`/data/app`) apps - they only return from the Play
  Store. System apps return with `cmd package install-existing`.
- Remove Play Auto Installs or partner apps reinstall themselves.
- Switch the IME before removing a keyboard.
- `cmd package uninstall-system-updates <pkg>` frees the Play update stored in /data but **re-enables a
  disabled package** - immediately `pm disable-user` it again and press HOME to confirm the launcher.
- Uninstalling preinstalled apps for user 0 frees only their updates/data; the APK stays in the read-only
  firmware partitions, so storage gains are modest. Set expectations before promising space.
- Disabling `launcherx` alone makes `setupwraith` the home screen - disable both.
- `monkey -p <pkg> 1` may not launch Leanback-only apps (e.g. Prime Video). Use their main activity:
  `cmd package resolve-activity --brief <pkg>` or `dumpsys package <pkg> | grep -A1 MAIN`.

Settings that don't stick
- Some firmwares (seen on Hisense/Vu Android 11) reset `window_animation_scale` to 1.0 on boot while
  DNS, IME and other settings persist. Always re-check with `tv.py info` after the verification reboot and
  tell the owner if a setting reverts; re-applying may be needed after each restart.

Screen & UI driving
- uiautomator: Leanback slider *titles* report `focused="true"` even when not selected; only a node with
  `focusable="true"` is really focused (`tv.py ui` handles this).
- Flutter/web launchers (FLauncher, Projectivy) expose no text - use `shot`.
- Video layers are protected: screenshots of playing video are black; DRM previews make `screencap`
  return 0 bytes. Settings menus still read fine with `uiautomator`.
- Web/DRM apps (Prime Video, many launchers) expose no uiautomator text - navigate with screenshots, or
  verify by result (`tv.py playing` shows the decoder and session state).
- Settings overlays can stay on top of a player; BACK on the player exits playback. Check the focused
  window before BACK.
- Leanback slider rows don't report focus in uiautomator - read values back after adjusting.
- Option lists reset focus to the first item each time they open; step and verify, don't count blindly.
- A 3-minute pattern ends and VLC exits mid-question - use the 30-minute versions.

Picture/audio
- Picture settings are per mode (and per HDR/DV signal); a mode may lock options (e.g. Colour Space).
- Changing mode list order differs by signal type; Game may be hidden when no game source.
- `avr_capability_ddp_atmos` (MediaTek/Hisense) gates Netflix Atmos even when eARC passes E-AC3-JOC.
- Streaming apps may send SDR despite HDR badges; always confirm with `tv.py playing`.

People
- It's someone's living room: check `tv.py watching` before opening menus; don't play titles on their
  accounts without saying so (it changes Continue Watching); stop playback and leave the home screen.
