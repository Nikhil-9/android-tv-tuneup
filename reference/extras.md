# Extras: app settings and common owner questions

## App settings worth changing (in-app, not adb - say so in the hand-off so they can revert)
- **YouTube** (Settings inside the app): Previews **Off** (no autoplay sound/video while browsing),
  Device recommendations **Off** (fewer background fetches). With YouTube Premium, pick "1080p Premium"
  where offered. Verify real 4K/HDR with `tv.py playing` while a 4K video plays (decoder name shows AV1/VP9,
  resolution 3840x2160) rather than trusting the quality menu; "Stats for nerds" shows the same.
- **Netflix**: 4K/HDR/Atmos need the Premium plan; on MediaTek/Hisense TVs also see the Atmos flag in
  audio.md. Netflix and Hotstar block screenshots (empty `shot`) - read their menus with the camera or `ui`.
- **Prime Video**: often streams SDR even for HDR titles depending on device certification; confirm with
  `tv.py playing`.
- Playing a title on someone's account changes their Continue Watching - ask first, prefer the owner's own
  files (Jellyfin/Plex/USB) for tests.

## Voice assistants and smart speakers
- Disabling Google Assistant (`katniss` + `tv.assistant`) kills the remote's mic button - an explicit owner
  choice.
- **Alexa / Echo**: most Android TVs have no Alexa integration (check for a vendor "Alexa"/"VIDAA voice" app;
  "AIoT"-style vendor services usually aren't Alexa). Options to offer:
  1. Echo as a **Bluetooth speaker**: "Alexa, pair Bluetooth", then TV Settings > Remotes & Accessories.
  2. An **IR blaster** (Broadlink/SwitchBot hub) + Alexa skill: power, volume, inputs by voice.
  3. **Home Assistant** (Android TV integration over adb): "open Netflix"-style control; bigger project.
  4. A **Fire TV Stick** on a spare HDMI: native Alexa + HDMI-CEC power/volume, but a second ad-heavy UI.
- A soundbar's built-in assistant controls the soundbar only (see audio.md).

## Remotes and input
- **Air mouse / pointer**: Android TV supports any HID mouse. Check the stock remote first:
  `getevent -p` - a remote with only KEY_* codes (no `REL_X`/`REL_Y`) is not an air mouse. 2.4 GHz air-mouse
  remotes (G10S/G20S class, USB dongle) and Bluetooth mice work without setup. Brand pointer remotes (e.g. LG
  Magic Remote) only work with their own TVs. The pointer helps in browsers; streaming apps stay D-pad-first.
  Voice buttons on such remotes need Google Assistant enabled.
- The vendor **Menu** key is often grabbed by the system (opens TV settings) and never reaches apps.

## Web browsing
- Android TV has no proper browser by default. **TV Bro** (`com.phlox.tvwebbrowser`, open source, Play Store)
  is D-pad friendly and has a cursor mode for the plain remote. Install via `market://details?id=...`
  (owner approves the install).
- Don't build "app wrappers" for sites that host unlicensed streams - decline politely.

## Recording or sharing the result
- `screenrecord` works over adb but is slow on TV SoCs: ~8 fps at 1080p, ~15 fps at 1280x720 - record at
  `--size 1280x720`. Protected video (Netflix, Prime, Hotstar) records black.
- Wi-Fi adb drops during long sequences: push a small shell script and run it on the TV with
  `nohup sh /sdcard/x.sh &`, then pull the files - the recording survives a dropped link.
- Before posting anything publicly, check frames for personal data: TV Settings shows the Google account
  email and Wi-Fi network name; crop or choose a neutral app. Delete recordings from /sdcard afterwards.
