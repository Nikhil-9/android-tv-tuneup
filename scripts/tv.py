#!/usr/bin/env python3
"""Helper CLI for the android-tv-tuneup skill. Standard library only.

Every command prints JSON or plain text that Claude reads back. Nothing here changes
the TV except `apply` (dry run unless --yes), `rollback`, `keys`, and `play`.

  python tv.py discover                       find Android/Google TVs on the local network
  python tv.py connect 192.168.1.9            adb connect + authorization status
  python tv.py info -s HOST:5555              model, RAM, HDR, codecs, eARC, launcher, DNS...
  python tv.py backup -s HOST:5555 -o DIR     snapshot packages, settings, props
  python tv.py audit -s HOST:5555 -o FILE     usage-ranked package audit with suggested actions
  python tv.py apply -s HOST:5555 --plan P    preview a plan (add --yes to execute; writes rollback)
  python tv.py rollback -s HOST:5555 --file R undo an applied plan
  python tv.py ui -s HOST:5555                visible text, focused row, focused window
  python tv.py keys -s HOST:5555 "DOWN DOWN CENTER"
  python tv.py shot -s HOST:5555 -o x.png     screenshot (DRM video and some apps capture as empty)
  python tv.py playing -s HOST:5555           what is playing: decoder, resolution, audio format
  python tv.py watching -s HOST:5555          is someone watching right now?
  python tv.py play -s HOST:5555 FILE         push a local video and open it in VLC
"""
import argparse
import concurrent.futures
import datetime
import ipaddress
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "packages.json"
NOISE = re.compile(r"Init wrapper sys mutex|open mma dev failed|Failed to write while dumping")


# ---------------------------------------------------------------- adb plumbing
def find_adb():
    if os.environ.get("ADB"):
        return os.environ["ADB"]
    exe = "adb.exe" if platform.system() == "Windows" else "adb"
    found = shutil.which("adb")
    if found:
        return found
    home = Path.home()
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android/Sdk/platform-tools" / exe,
        home / "Library/Android/sdk/platform-tools" / exe,
        home / "Android/Sdk/platform-tools" / exe,
        home / "platform-tools" / exe,
        HERE.parent / "platform-tools" / exe,
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    sys.exit("adb not found. Install Android platform-tools (https://developer.android.com/tools/releases/platform-tools) "
             "or set the ADB environment variable to its path.")


ADB = None


def adb(*args, serial=None, timeout=60, check=False):
    global ADB
    ADB = ADB or find_adb()
    cmd = [ADB] + (["-s", serial] if serial else []) + list(args)
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        if check:
            raise RuntimeError(f"adb {' '.join(args)} timed out after {timeout}s")
        return f"TIMEOUT: adb {' '.join(args)} gave no answer in {timeout}s (TV off, asleep or unreachable?)"
    out = "\n".join(l for l in (p.stdout + p.stderr).splitlines() if not NOISE.search(l))
    if check and p.returncode != 0:
        raise RuntimeError(out.strip() or f"adb {' '.join(args)} failed")
    return out.strip()


def sh(serial, command, timeout=60):
    return adb("shell", command, serial=serial, timeout=timeout)


def emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------- discover / connect
TV_PORTS = {5555: "adb", 8008: "cast-http", 8009: "cast", 6466: "atv-remote", 6467: "atv-remote-pair"}


def local_subnet():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ipaddress.ip_network(ip + "/24", strict=False), ip


def port_open(host, port, timeout=0.6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def cmd_discover(a):
    net, me = (ipaddress.ip_network(a.subnet), None) if a.subnet else local_subnet()
    hosts = [str(h) for h in net.hosts() if str(h) != me]
    found = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=256) as ex:
        futs = {ex.submit(port_open, h, p): (h, p) for h in hosts for p in TV_PORTS}
        for f in concurrent.futures.as_completed(futs):
            h, p = futs[f]
            if f.result():
                found.setdefault(h, []).append(TV_PORTS[p])
    result = []
    for h, services in sorted(found.items(), key=lambda kv: ipaddress.ip_address(kv[0])):
        entry = {"host": h, "services": sorted(services)}
        if "cast-http" in services:
            try:
                with urllib.request.urlopen(f"http://{h}:8008/setup/eureka_info?params=name,build_info", timeout=3) as r:
                    info = json.loads(r.read().decode())
                entry["name"] = info.get("name")
                entry["cast_build"] = info.get("cast_build_revision")
            except Exception:
                pass
        entry["likely_android_tv"] = bool({"atv-remote", "adb"} & set(services)) or "cast" in services
        result.append(entry)
    emit({"subnet": str(net), "devices": result})


def cmd_connect(a):
    target = a.host if ":" in a.host else a.host + ":5555"
    out = adb("connect", target, timeout=20)
    state = adb("-s", target, "get-state", timeout=10)
    hint = {
        "device": "Connected and authorized.",
        "unauthorized": "The TV is showing 'Allow USB debugging?'. Ask the owner to tick 'Always allow' and press Allow.",
        "offline": "Port answered but adb is offline. Re-run connect; if it persists, toggle USB debugging off/on on the TV.",
    }.get(state.strip(), "Not reachable on 5555. Ask the owner to enable Developer options + USB debugging "
                         "(or Wireless debugging and pair). See reference/connect.md.")
    host = target.rsplit(":", 1)[0]
    if state.strip() not in ("device", "unauthorized", "offline") and not any(port_open(host, p, 1.5) for p in (8008, 8009, 6466)):
        hint = "The TV doesn't answer at all - it is probably off or in standby (Wi-Fi sleeps). Ask the owner to turn it on."
    emit({"serial": target, "connect": out, "state": state.strip(), "hint": hint})


# ---------------------------------------------------------------- info
def prop(serial, *names):
    out = sh(serial, "; ".join(f"getprop {n}" for n in names))
    return dict(zip(names, (out.splitlines() + [""] * len(names))[: len(names)]))


def cmd_info(a):
    s = a.serial
    p = prop(s, "ro.product.manufacturer", "ro.product.brand", "ro.product.model", "ro.product.device",
             "ro.build.version.release", "ro.build.version.sdk", "ro.build.fingerprint", "ro.boot.hardware")
    mem = sh(s, "grep -E 'MemTotal|MemAvailable' /proc/meminfo")
    df = sh(s, "df -h /data | tail -1")
    display = sh(s, "dumpsys display | grep -m1 -oE 'supportedModes \\[[^]]*\\]|HdrCapabilities\\{[^}]*\\}'")
    hdr = re.search(r"mSupportedHdrTypes=\[([^\]]*)\]", sh(s, "dumpsys display | grep -m1 mSupportedHdrTypes"))
    hdr_map = {"1": "DolbyVision", "2": "HDR10", "3": "HLG", "4": "HDR10+"}
    codecs = sh(s, "cat /vendor/etc/media_codecs*.xml /system/etc/media_codecs*.xml 2>/dev/null | "
                   "grep -oE 'MediaCodec name=\"[^\"]+\" type=\"video/[^\"]+\"' | sort -u")
    vtypes = sorted(set(re.findall(r'type="(video/[^"]+)"', codecs)))
    hdmi = sh(s, "dumpsys hdmi_control | grep -E '^ *CEC: logical_address|mArcEstablished|mEarc' | sed 's/^ *//' | sort -u")
    audio_dev = sh(s, "dumpsys audio | grep -m1 -E 'Devices: '")
    homes = sorted(set(re.findall(r"packageName=(\S+)", sh(s, "cmd package query-activities -a android.intent.action.MAIN "
                                                              "-c android.intent.category.HOME"))))
    resumed = sh(s, "dumpsys activity activities | grep -m1 mResumedActivity")
    settings = {k: sh(s, f"settings get {ns} {k}") for ns, k in [
        ("global", "private_dns_mode"), ("global", "private_dns_specifier"), ("global", "window_animation_scale"),
        ("secure", "default_input_method"), ("secure", "screensaver_enabled"), ("global", "avr_capability_ddp_atmos"),
        ("global", "encoded_surround_output")]}
    vendor = sh(s, "getprop | grep -iE 'earc|light_sensor|lcdm|local_dimming|memc|panel|product.model\\]' | head -20")
    emit({
        "props": p,
        "memory": mem.splitlines(),
        "data_partition": df,
        "display": display.splitlines(),
        "hdr_types": [hdr_map.get(x.strip(), x.strip()) for x in hdr.group(1).split(",")] if hdr else [],
        "video_codec_types": vtypes,
        "hdmi_cec_earc": hdmi.splitlines(),
        "audio_output": audio_dev,
        "home_apps": homes,
        "foreground": resumed,
        "settings": settings,
        "vendor_props": vendor.splitlines(),
    })


# ---------------------------------------------------------------- backup
def cmd_backup(a):
    s, out = a.serial, Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    jobs = {
        "packages_all.txt": "pm list packages -f -i -U",
        "packages_system.txt": "pm list packages -s",
        "packages_user.txt": "pm list packages -3",
        "packages_disabled.txt": "pm list packages -d",
        "settings_global.txt": "settings list global",
        "settings_secure.txt": "settings list secure",
        "settings_system.txt": "settings list system",
        "getprop.txt": "getprop",
        "home_activities.txt": "cmd package query-activities -a android.intent.action.MAIN -c android.intent.category.HOME",
        "ime.txt": "ime list -a -s; echo; settings get secure default_input_method",
        "hdmi_control.txt": "dumpsys hdmi_control",
        "display.txt": "dumpsys display",
        "meminfo.txt": "cat /proc/meminfo; df -h /data; dumpsys meminfo | sed -n '/Total PSS by process/,/Total PSS by OOM/p'",
    }
    written = {}
    for name, cmd in jobs.items():
        text = sh(s, cmd, timeout=120)
        (out / name).write_text(text + "\n", encoding="utf-8")
        written[name] = len(text.splitlines())
    manifest = {"serial": s, "taken": datetime.datetime.now().isoformat(timespec="seconds"), "files": written}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    emit(manifest)


# ---------------------------------------------------------------- audit
def load_db():
    return json.loads(DATA.read_text(encoding="utf-8"))


def match_rule(pkg, db):
    for rule in db["packages"]:
        pat = rule["match"]
        if (pat.endswith("*") and pkg.startswith(pat[:-1])) or pat == pkg:
            return rule
    return None


def protected(pkg, db):
    return any(re.search(p, pkg) for p in db["never_touch_patterns"])


def usage_stats(serial):
    """Launch count / foreground time over the monthly usage window."""
    text = sh(serial, "dumpsys usagestats", timeout=120)
    start = text.find("In-memory monthly stats")
    block = text[start:] if start >= 0 else text
    stats = {}
    for m in re.finditer(r'package=(\S+) totalTimeUsed="([^"]+)" lastTimeUsed="([^"]+)".*?appLaunchCount=(\d+)', block):
        pkg = m.group(1)
        if pkg not in stats:
            stats[pkg] = {"time_used": m.group(2), "last_used": m.group(3), "launches": int(m.group(4))}
    return stats


def cmd_audit(a):
    s, db = a.serial, load_db()
    lines = sh(s, "pm list packages -f -i").splitlines()
    disabled = set(l.split(":", 1)[1] for l in sh(s, "pm list packages -d").splitlines() if ":" in l)
    third = set(l.split(":", 1)[1] for l in sh(s, "pm list packages -3").splitlines() if ":" in l)
    usage = usage_stats(s)
    rows = []
    for l in lines:
        m = re.match(r"package:(.+)=(\S+)\s+installer=(\S+)", l)
        if not m:
            continue
        path, pkg, installer = m.groups()
        u = usage.get(pkg, {"launches": 0, "time_used": "00:00", "last_used": "never"})
        rule = match_rule(pkg, db)
        if protected(pkg, db):
            action, why = "keep", "core system component (never_touch)"
        elif pkg in disabled:
            action, why = "already-disabled", (rule["label"] + " - " if rule else "") + "already disabled for user 0"
        elif rule and not (u["launches"] > 0 and rule["action"] in ("remove", "ask-remove")):
            action, why = rule["action"], rule["why"]
        elif u["launches"] > 0:
            action, why = "keep", f"the owner uses it ({u['launches']} launches this month)"
        elif pkg in third:
            action, why = ("ask-remove", "installed app never launched in the last month") if u["launches"] == 0 \
                else ("keep", "installed app the owner uses")
        else:
            action, why = "review", "vendor/system package not in the database - inspect before touching"
        rows.append({"package": pkg, "label_hint": rule.get("label") if rule else "", "path": path,
                     "system": pkg not in third, "disabled": pkg in disabled, "launches": u["launches"],
                     "time_used": u["time_used"], "last_used": u["last_used"], "action": action, "why": why,
                     "risk": rule.get("risk", "") if rule else ""})
    order = {"remove": 0, "disable": 1, "ask-remove": 2, "ask": 3, "launcher-swap": 4, "review": 5,
             "already-disabled": 6, "keep": 7}
    rows.sort(key=lambda r: (order.get(r["action"], 9), -r["launches"], r["package"]))
    if a.out:
        Path(a.out).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    summary = {}
    for r in rows:
        summary.setdefault(r["action"], 0)
        summary[r["action"]] += 1
    used = [f'{r["package"]} ({r["launches"]} launches)' for r in sorted(rows, key=lambda r: -r["launches"]) if r["launches"] > 0]
    emit({"summary": summary, "used_apps": used[:25],
          "candidates": [r for r in rows if r["action"] not in ("keep", "review", "already-disabled")],
          "already_disabled": [r["package"] for r in rows if r["action"] == "already-disabled"],
          "review": [r["package"] for r in rows if r["action"] == "review"]})


# ---------------------------------------------------------------- apply / rollback
def pkg_state(serial, pkg):
    out = sh(serial, f"pm list packages --user 0 {pkg}")
    if f"package:{pkg}" not in out.split():
        return "absent-for-user"
    return "disabled" if f"package:{pkg}" in sh(serial, "pm list packages -d").split() else "enabled"


def cmd_apply(a):
    s, db = a.serial, load_db()
    plan = json.loads(Path(a.plan).read_text(encoding="utf-8"))
    steps, blocked = [], []
    for kind in ("disable", "uninstall"):
        for pkg in plan.get(kind, []):
            if protected(pkg, db) and not a.force:
                blocked.append(pkg)
                continue
            steps.append((kind, pkg))
    for st in plan.get("settings", []):
        steps.append(("setting", st))
    if plan.get("ime"):
        steps.insert(0, ("ime", plan["ime"]))  # switch keyboard before removing the old one
    preview = [f"{k}: {v if isinstance(v, str) else v['namespace'] + ' ' + v['key'] + '=' + str(v['value'])}" for k, v in steps]
    if not a.yes:
        emit({"dry_run": True, "would_apply": preview, "blocked_never_touch": blocked,
              "next": "Show this list to the owner. After a clear yes, re-run with --yes."})
        return
    log_dir = Path(a.log or ".")
    log_dir.mkdir(parents=True, exist_ok=True)
    rollback, results = {"serial": s, "packages": [], "settings": [], "ime": None}, []
    for kind, v in steps:
        if kind == "ime":
            rollback["ime"] = sh(s, "settings get secure default_input_method")
            res = sh(s, f"ime enable {v}; ime set {v}")
        elif kind == "setting":
            old = sh(s, f"settings get {v['namespace']} {v['key']}")
            rollback["settings"].append({**v, "old": old})
            res = sh(s, f"settings put {v['namespace']} {v['key']} {v['value']}")
            res = res or f"{v['key']}: {old} -> {v['value']}"
        else:
            before = pkg_state(s, v)
            rollback["packages"].append({"package": v, "was": before, "action": kind})
            if kind == "disable":
                sh(s, f"am force-stop {v}")
                res = sh(s, f"pm disable-user --user 0 {v}")
            else:
                res = sh(s, f"pm uninstall -k --user 0 {v}")
        results.append({"step": kind, "target": v if isinstance(v, str) else v["key"], "result": res})
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    rb = log_dir / f"rollback-{stamp}.json"
    rb.write_text(json.dumps(rollback, indent=2), encoding="utf-8")
    with open(log_dir / "changes.log", "a", encoding="utf-8") as f:
        for r in results:
            f.write(f"{stamp} {r['step']} {r['target']}: {r['result']}\n")
    emit({"applied": results, "blocked_never_touch": blocked, "rollback_file": str(rb)})


def cmd_rollback(a):
    s = a.serial
    data = json.loads(Path(a.file).read_text(encoding="utf-8"))
    out = []
    for p in reversed(data.get("packages", [])):
        pkg = p["package"]
        if p["action"] == "uninstall":
            out.append(sh(s, f"cmd package install-existing {pkg}") or f"{pkg}: install-existing")
        if p["was"] == "enabled":
            out.append(sh(s, f"pm enable {pkg}"))
    for st in data.get("settings", []):
        cmd = f"settings delete {st['namespace']} {st['key']}" if st["old"] in ("null", "") \
            else f"settings put {st['namespace']} {st['key']} {st['old']}"
        out.append(sh(s, cmd) or cmd)
    if data.get("ime"):
        out.append(sh(s, f"ime set {data['ime']}"))
    emit({"rolled_back": out,
          "note": "Third-party apps that were fully uninstalled must be reinstalled from the Play Store."})


# ---------------------------------------------------------------- UI helpers
KEYMAP = {"UP": "DPAD_UP", "DOWN": "DPAD_DOWN", "LEFT": "DPAD_LEFT", "RIGHT": "DPAD_RIGHT", "CENTER": "DPAD_CENTER",
          "OK": "DPAD_CENTER"}


def cmd_keys(a):
    parts = []
    for k in a.sequence.split():
        code = KEYMAP.get(k.upper(), k.upper())
        parts.append(f"input keyevent KEYCODE_{code}; sleep {a.gap}")
    sh(a.serial, "; ".join(parts), timeout=120)
    print("sent:", a.sequence)


def focus_window(serial):
    m = re.search(r"mCurrentFocus=Window\{\S+ \S+ ([^}]+)\}", sh(serial, "dumpsys window | grep -m1 mCurrentFocus"))
    return m.group(1) if m else ""


def cmd_ui(a):
    xml = sh(a.serial, "uiautomator dump /sdcard/ui.xml >/dev/null 2>&1; cat /sdcard/ui.xml")
    nodes = re.findall(r"<node [^>]*>", xml)
    texts, focused_idx, loose_idx = [], -1, -1
    for i, n in enumerate(nodes):
        # Leanback slider titles claim focused="true" (marquee); only a focusable node is really focused
        if 'focused="true"' in n:
            loose_idx = i
            if 'focusable="true"' in n:
                focused_idx = i
    focused_idx = focused_idx if focused_idx >= 0 else loose_idx
    for i, n in enumerate(nodes):
        t = re.search(r' text="([^"]*)"', n)
        chk = re.search(r'checkable="true"[^>]*checked="(true|false)"', n)
        if (t and t.group(1)) or chk:
            texts.append((i, (t.group(1) if t else "") + (f" [{'on' if chk.group(1) == 'true' else 'off'}]" if chk else "")))
    focused = next((txt for i, txt in texts if i >= focused_idx), "") if focused_idx >= 0 else ""
    emit({"window": focus_window(a.serial), "focused_text": focused, "texts": [t for _, t in texts],
          "note": "If texts is empty the app draws its own UI (web/DRM). Use `shot` or the phone camera instead."})


def cmd_shot(a):
    sh(a.serial, "screencap -p /sdcard/_tvshot.png")
    adb("pull", "/sdcard/_tvshot.png", a.out, serial=a.serial)
    size = Path(a.out).stat().st_size if Path(a.out).exists() else 0
    emit({"file": a.out, "bytes": size,
          "note": "0 bytes = a protected (DRM) video or preview is on screen; video layers always capture black."
          if size == 0 else ""})


# ---------------------------------------------------------------- playback inspection
def cmd_playing(a):
    s = a.serial
    metrics = sh(s, "dumpsys media.metrics | grep mediacodec | tail -4")
    codecs = []
    for line in metrics.splitlines():
        d = dict(re.findall(r"mediacodec\.(codec|mime|width|height|secure)=([^,)]+)", line))
        if d:
            codecs.append(d)
    # resource_manager also lists DRM sessions as "Name: Google[...]"; keep real codec names only
    decoders = [n for n in re.findall(r"Name: (\S+)", sh(s, "dumpsys media.resource_manager"))
                if "." in n and "[" not in n]
    # per output thread: HAL format + whether it has active tracks (idle direct outputs stay open)
    af = sh(s, "dumpsys media.audio_flinger")
    audio, active_audio = set(), set()
    for block in re.split(r"\n(?=-? ?Output thread )", af):
        fmt = re.search(r"HAL format: \S+ \((AUDIO_FORMAT_[A-Z0-9_]+)\)", block)
        if not fmt:
            continue
        audio.add(fmt.group(1))
        act = re.search(r"(\d+) Tracks of which (\d+) are active", block)
        if (act and int(act.group(2)) > 0) or "Standby: no" in block:
            active_audio.add(fmt.group(1))
    audio = sorted(audio)
    sessions = re.findall(r"package=(\S+)[\s\S]*?state=PlaybackState \{state=(\d)", sh(s, "dumpsys media_session"))
    state_names = {"0": "none", "1": "stopped", "2": "paused", "3": "playing", "6": "buffering"}
    dv = any("DOLBY_VISION" in d.upper() for d in decoders)
    emit({"foreground": focus_window(s), "active_video_decoders": decoders,
          "recent_codecs_history": codecs, "audio_outputs_open": audio, "audio_outputs_active": sorted(active_audio),
          "sessions": [{"package": p, "state": state_names.get(st, st)} for p, st in sessions],
          "dolby_vision_decoder_active": dv,
          "atmos_passthrough_active": any("JOC" in f or "TRUEHD" in f or "MAT" in f for f in active_audio),
          "note": "recent_codecs_history includes earlier playback; trust active_* fields for what is playing now."})


def cmd_watching(a):
    s = a.serial
    sessions = re.findall(r"state=PlaybackState \{state=(\d)", sh(s, "dumpsys media_session"))
    fg = focus_window(s)
    playing = "3" in sessions
    emit({"someone_watching": playing, "foreground": fg,
          "advice": "Something is playing - ask before opening menus or switching apps." if playing
          else "Nothing playing. Safe to work on screen."})


def cmd_play(a):
    s = a.serial
    src = Path(a.file)
    dest = f"/sdcard/Movies/tv-tuneup/{src.name}"
    sh(s, "mkdir -p /sdcard/Movies/tv-tuneup")
    if not a.no_push:
        adb("push", str(src), dest, serial=s, timeout=900)
    if "org.videolan.vlc" not in sh(s, "pm list packages org.videolan.vlc"):
        emit({"error": "VLC is not installed on the TV. Get the owner's OK, then install it from the Play Store "
                       "(market://details?id=org.videolan.vlc) and finish its first-run screens."})
        return
    sh(s, "pm grant org.videolan.vlc android.permission.READ_EXTERNAL_STORAGE 2>/dev/null")
    sh(s, f"am start -a android.intent.action.VIEW -n org.videolan.vlc/org.videolan.vlc.gui.video.VideoPlayerActivity "
          f"-d file://{dest} -t video/mp4")
    time.sleep(6)
    emit({"playing": dest, "foreground": focus_window(s)})


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, serial=True):
        p = sub.add_parser(name)
        if serial:
            p.add_argument("-s", "--serial", required=True, help="HOST:5555 as shown by `adb devices`")
        p.set_defaults(fn=fn)
        return p

    p = add("discover", cmd_discover, serial=False)
    p.add_argument("--subnet", help="e.g. 192.168.1.0/24 (default: this machine's /24)")
    p = add("connect", cmd_connect, serial=False)
    p.add_argument("host")
    add("info", cmd_info)
    p = add("backup", cmd_backup)
    p.add_argument("-o", "--out", required=True)
    p = add("audit", cmd_audit)
    p.add_argument("-o", "--out")
    p = add("apply", cmd_apply)
    p.add_argument("--plan", required=True, help='JSON: {"uninstall":[], "disable":[], "settings":[{"namespace","key","value"}], "ime":""}')
    p.add_argument("--log", help="folder for changes.log and rollback files")
    p.add_argument("--yes", action="store_true", help="actually apply (default is a dry run)")
    p.add_argument("--force", action="store_true", help="allow never_touch packages (only on explicit owner request)")
    p = add("rollback", cmd_rollback)
    p.add_argument("--file", required=True)
    add("ui", cmd_ui)
    p = add("keys", cmd_keys)
    p.add_argument("sequence")
    p.add_argument("--gap", type=float, default=0.35)
    p = add("shot", cmd_shot)
    p.add_argument("-o", "--out", required=True)
    add("playing", cmd_playing)
    add("watching", cmd_watching)
    p = add("play", cmd_play)
    p.add_argument("file")
    p.add_argument("--no-push", action="store_true", help="file already on the TV")

    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
