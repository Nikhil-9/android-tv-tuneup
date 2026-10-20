#!/usr/bin/env python3
"""Use a phone running the free 'IP Webcam' Android app as Claude's eyes on the TV.

Good for: seeing the real screen (DRM video and video layers can't be screenshotted),
checking which pattern bars are visible, highlight clipping, uniformity, gross tint.
Not good for: absolute colour/white point (uncalibrated sensor, JPEG processing) or the
darkest near-black steps (sensor noise) - use the viewer's eyes or a colorimeter there.

  python camera.py find                         scan the local /24 for IP Webcam (port 8080)
  python camera.py lock HOST [--exposure-ms 20]  fixed ISO 100, daylight WB, manual shutter
  python camera.py shot HOST -o shot.jpg         grab a frame
  python camera.py ramp HOST                     RGB balance along the grey-ramp pattern (needs Pillow+numpy)
  python camera.py release HOST                  back to auto exposure/white balance when done
"""
import argparse
import concurrent.futures
import ipaddress
import json
import socket
import sys
import urllib.request


def get(url, timeout=8):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def cmd_find(a):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("10.255.255.255", 1))
    net = ipaddress.ip_network(s.getsockname()[0] + "/24", strict=False)
    s.close()

    def probe(h):
        try:
            data = json.loads(get(f"http://{h}:{a.port}/status.json", timeout=1.5))
            return h, data.get("deviceInfo", {})
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=128) as ex:
        hits = [r for r in ex.map(probe, [str(h) for h in net.hosts()]) if r]
    print(json.dumps([{"host": f"{h}:{a.port}", "battery": i.get("batteryPercent"), "charging": i.get("batteryCharging")}
                      for h, i in hits], indent=2))
    if not hits:
        print("No IP Webcam found. Ask the owner to open IP Webcam, scroll to the bottom and tap 'Start server', "
              "with the phone on the same Wi-Fi.", file=sys.stderr)


def base(host):
    return f"http://{host}" if ":" in host else f"http://{host}:8080"


def cmd_lock(a):
    b = base(a.host)
    exp_ns = int(a.exposure_ms * 1_000_000)
    frame_ns = max(33_333_333, exp_ns + 5_000_000)
    for k, v in [("whitebalance", "daylight"), ("antibanding", "off"), ("manual_sensor", "on"), ("iso", a.iso),
                 ("frame_duration", frame_ns), ("exposure_ns", exp_ns)]:
        get(f"{b}/settings/{k}?set={v}")
    cur = json.loads(get(f"{b}/status.json"))["curvals"]
    print(json.dumps({k: cur.get(k) for k in ("whitebalance", "manual_sensor", "iso", "exposure_ns", "frame_duration")}, indent=2))


def cmd_release(a):
    """Hand the phone camera back: automatic exposure and white balance."""
    b = base(a.host)
    for k, v in [("manual_sensor", "off"), ("whitebalance", "auto"), ("antibanding", "auto")]:
        get(f"{b}/settings/{k}?set={v}")
    cur = json.loads(get(f"{b}/status.json"))["curvals"]
    print(json.dumps({k: cur.get(k) for k in ("manual_sensor", "whitebalance")}, indent=2))
    print("Tell the owner they can now tap 'Stop' in IP Webcam (or uninstall it).", file=sys.stderr)


def cmd_shot(a):
    data = get(f"{base(a.host)}/{'photo.jpg' if a.full else 'shot.jpg'}", timeout=20)
    open(a.out, "wb").write(data)
    print(a.out, len(data), "bytes")


def cmd_ramp(a):
    try:
        import io
        import numpy as np
        from PIL import Image
    except ImportError:
        sys.exit("Needs numpy and Pillow")
    im = np.asarray(Image.open(io.BytesIO(get(f"{base(a.host)}/photo.jpg", timeout=20))).convert("RGB")).astype(float)
    lum = im.mean(axis=2)
    h, w = lum.shape
    rows = lum[:, int(w * 0.55):int(w * 0.85)].mean(axis=1)
    band = np.where(rows > rows.max() * 0.6)[0]
    y0, y1 = band.min(), band.max()
    strip = im[y0 + (y1 - y0) // 3: y1 - (y1 - y0) // 3].mean(axis=0)
    cols = np.where(strip.mean(axis=1) > 8)[0]
    x0, x1 = cols.min(), cols.max()
    out = []
    for p in range(10, 100, 10):
        x = int(x0 + (x1 - x0) * p / 100)
        r, g, b_ = strip[max(0, x - 15):x + 15].mean(axis=0)
        out.append({"position_pct": p, "R": round(r, 1), "G": round(g, 1), "B": round(b_, 1),
                    "R/G": round(r / g, 3) if g else None, "B/G": round(b_ / g, 3) if g else None})
    print(json.dumps({"note": "Compare R/G and B/G between dark and bright positions; a drift >3% suggests a grey-scale "
                              "tint. Absolute values are not meaningful (camera daylight WB != D65).", "samples": out}, indent=2))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("find"); p.add_argument("--port", type=int, default=8080); p.set_defaults(fn=cmd_find)
    p = sub.add_parser("lock"); p.add_argument("host"); p.add_argument("--exposure-ms", type=float, default=20)
    p.add_argument("--iso", type=int, default=100); p.set_defaults(fn=cmd_lock)
    p = sub.add_parser("shot"); p.add_argument("host"); p.add_argument("-o", "--out", default="shot.jpg")
    p.add_argument("--full", action="store_true", help="full-resolution photo instead of a video frame"); p.set_defaults(fn=cmd_shot)
    p = sub.add_parser("ramp"); p.add_argument("host"); p.set_defaults(fn=cmd_ramp)
    p = sub.add_parser("release"); p.add_argument("host"); p.set_defaults(fn=cmd_release)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
