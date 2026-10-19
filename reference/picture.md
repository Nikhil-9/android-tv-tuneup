# Picture calibration module

Principle: accuracy first, then adjust for the room. Remove processing the director never asked for; set
black/white levels with patterns; pick the right mode per signal type. Without a colorimeter you can set
brightness, contrast, sharpness, gamma choice and modes well; white balance/colour need a meter.

## 1. Know the hardware
- `tv.py info`: HDR types (DolbyVision/HDR10/HLG/HDR10+), codecs, display modes.
- Vendor props hint at panel features, e.g. MediaTek/Hisense `ro.vt.lcdm_support` (local dimming),
  `ro.vt.built_in_memc` (frame interpolation), `ro.vt.light_sensor_supported`, `ro.vt.hsr` (120 Hz).
  No local dimming + ~400 nits = HDR gains are limited; tone mapping matters more.
- Look up a professional review of the exact model or its ODM twin (e.g. RTINGS settings pages). Many
  brands rebadge Hisense/TCL/MediaTek platforms; menus and behaviour match. Treat white-balance numbers
  from reviews as unit-specific - don't copy them.

## 2. Read the current state
Open `am start -n com.android.tv.settings/.picture.PictureActivity` (path varies by brand; find with
`dumpsys package com.android.tv.settings | grep -i picture`) and read it with `tv.py ui`. Record every
value per mode in the workspace before changing anything. Picture settings are stored **per mode**, so
switching mode is itself a safe rollback.

## 3. Phase A - sensible baseline (no patterns)
SDR mode: the brand's accurate mode (Calibrated / Filmmaker / Movie / Cinema / Theater). Then:
- Colour temperature: the warm/"Low"/"Warm1"/"Expert" option closest to 6500K (D65).
- Colour space: Auto (Native oversaturates SDR). Some modes lock it - note that.
- Off: Active/dynamic contrast, motion interpolation (offer Film/low for judder-sensitive owners and a
  sports preset), noise reduction (Low only for poor sources), edge enhancement; Sharpness 0 (or the
  value with no halos).
- Gamma 2.2 for lit rooms, 2.4 (BT.1886) for dim/dark rooms. Backlight to taste per room.
- Keep FILMMAKER MODE auto-detection on.
- Sports preset: reuse the vendor's sport mode with warm colour temp, light NR, motion smoothing kept,
  Active contrast low, higher backlight. Owner switches via the remote's picture quick-menu.
HDR modes appear only while HDR plays; Dolby Vision modes only while DV plays (see 5).

## 4. Phase B - pattern calibration (owner reads numbers)
Generate once: `python -I scripts/gen_patterns.py tv-tuneup-<model>/patterns --minutes 30`.
Play with `tv.py play -s S FILE` (needs VLC on the TV - ask before installing). Ask with AskUserQuestion,
from the owner's normal seat and lighting. Close the settings overlay before asking (check `window`).
- **sdr_black** (bars 1-3 at/below black, 4 = black+1): adjust **Brightness** until 1-3 merge with the
  background and 4 is just visible. If you can't satisfy both, prefer keeping 4 visible.
- **sdr_white** (inner squares +4 levels): lower **Contrast** until inner squares stay visible up to at least
  #5 (reference white), ideally #7; stop when gains stop or whites look dull.
- **sdr_sharpness**: no bright halos along lines. **sdr_ramp**: smooth, neutral.
- **hdr_black** (in the HDR mode): bar 1 matches background, bar 2+ visible -> HDR Brightness fine.
- **hdr_white**: highest inner square = where tone mapping clips (aim >= ~800 nits on a 400-nit panel).
  Don't lower HDR contrast on dim panels just to stretch it.
A slight warm/pink impression after switching from a cool mode is normal eye adaptation; suggest 3-4 days
before trimming white balance.

## 5. HDR & Dolby Vision
- Verify what is really playing with `tv.py playing`: a `DOLBY_VISION` decoder = true DV; plain HEVC = HDR10
  base layer. DV profile 7 (disc/FEL) files usually play as HDR10 on TVs; profiles 5/8 play as DV.
- Choose DV **Dark** for dim rooms. DV **IQ** needs an ambient light sensor - check the hardware; without
  one, IQ cannot adapt.
- Streaming apps decide the format server-side (plan, region, device certification): a title may arrive as
  SDR even on full plans. Confirm with `tv.py playing` rather than trusting badges. Netflix 4K/HDR/Atmos need
  Premium; JioHotstar/others vary.
- DRM video blocks screenshots (0-byte `shot`) - use `tv.py ui` for menus and the camera for the picture.
- Use the owner's own files (e.g. Jellyfin/Plex/USB) for deterministic HDR/DV tests; `ffprobe` shows DV
  profile via side data (`dv_profile`).

## 6. Phone camera assist (optional)
Owner installs **IP Webcam** (Android), taps Start server, props the phone facing the TV in the dark.
`camera.py find` -> `camera.py lock HOST --exposure-ms 20` (fixed ISO/WB/shutter; longer ms for
near-black). Use it to see the real screen, cross-check clipping, check uniformity and gross tint
(`camera.py ramp`). Do not claim absolute colour accuracy or white point from it.

## 7. Phase C - meter (out of scope, advise only)
A colorimeter (e.g. Calibrite Display Plus HL / i1Display Pro) + HCFR/ArgyllCMS enables 2-point white
balance, gamma and CMS. Patterns can be generated with `gen_patterns.py` and driven with `tv.py`.
