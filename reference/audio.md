# Audio & soundbar module

## 1. What's connected
- `dumpsys hdmi_control`: CEC device list (`display_name: HW-Q700B`, `device_type: 5` = audio system),
  `port_id` with `arc: true`, `mSystemAudioActivated`. `mArcEstablished: false` can be normal when the
  link is **eARC** (handled outside CEC).
- eARC status is vendor-specific: e.g. MediaTek/Hisense `getprop sys.vt.connect_status` = `eARC`,
  `vendor.hisense.earc_status`. Grep `getprop | grep -i earc`.
- Formats the TV can send: `dumpsys media.audio_policy | grep -E 'AC3|E_AC3|JOC|DTS|TRUEHD|MAT'` under the
  HDMI_ARC device. `E_AC3_JOC` = Dolby Atmos over DD+ (streaming Atmos).

## 2. Best TV-side settings
- Audio output: the ARC/eARC device; TV speakers off.
- Digital audio out: **Pass Through / Bitstream / Auto(passthrough)** - lets the soundbar decode
  DD+/Atmos/DTS itself. Avoid **PCM** (downmixes to stereo) unless the soundbar can't decode.
  Menu names vary: Settings > Sound/Display & Sound > Audio output / Advanced / Digital audio out.
- Android "Surround sound" (`settings get global encoded_surround_output`): 0 = Auto (fine), 2 = Always.
- Digital audio delay 0; fix lip-sync on the soundbar if needed.
- **Netflix Atmos flag (MediaTek/Hisense TVs):** if `settings get global avr_capability_ddp_atmos` is 0 while
  the soundbar supports Atmos, Netflix offers only 5.1. Setting it to 1 (recipe in packages.json) flips
  `nrdp_audio_platform_capabilities` atmos.enabled to true; verify after a reboot. Netflix Atmos needs
  the Premium plan.

## 3. Verify
Play an Atmos title, then `tv.py playing -s S`: `audio_hal_formats` should include
`AUDIO_FORMAT_E_AC3_JOC` (or TRUEHD/MAT) and `atmos_passthrough: true`. Ask the owner to read the
soundbar's display ("DOLBY ATMOS").

## 4. Soundbar advice (owner does this on the soundbar remote/app)
- Mode: Standard/"Direct" for Atmos films (height channels play what the mix intends); Adaptive/Surround
  upmix for stereo sources like YouTube (YouTube is never Atmos). Voice enhance for dialogue; night mode.
- Up-firing speakers need a clear path to the ceiling - not inside a cabinet.
- Brand features tied to same-brand TVs (Samsung SpaceFit/Q-Symphony/wireless Atmos, LG WOW, Sony
  Acoustic Center Sync) won't work with other TV brands - say so.
- Voice assistants on the soundbar (e.g. "Works with Alexa" via the brand's app/skill) control the
  soundbar only, not the TV.
