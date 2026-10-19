#!/usr/bin/env python3
"""Generate numbered SDR (BT.709) and HDR10 (PQ) calibration pattern videos.

Pixel values go straight into the Y plane of 10-bit 4:2:0 frames (neutral chroma), so every
patch has an exact, known code value - no RGB->YUV rounding. Each pattern is numbered so the
viewer only reads a number off the screen. Needs numpy, Pillow and ffmpeg with libx265.

  python gen_patterns.py OUT_DIR                 # all six patterns, 3 minutes each
  python gen_patterns.py OUT_DIR --minutes 30    # long versions (stream-copied, fast)
  python gen_patterns.py OUT_DIR --only sdr_black,hdr_white
"""
import argparse
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Needs numpy and Pillow:  python -m pip install numpy pillow")

W, H, FPS = 3840, 2160, 24
FONT_CANDIDATES = [
    "C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def font(size):
    for f in FONT_CANDIDATES:
        if Path(f).is_file():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)  # Pillow >= 10.1


def sdr(v8):
    """8-bit video level (16 = black, 235 = white) -> 10-bit code."""
    return int(round(v8 * 4))


def pq(nits):
    """Absolute luminance (cd/m2) -> 10-bit limited-range PQ code (SMPTE ST 2084)."""
    m1, m2 = 2610 / 16384, 2523 / 4096 * 128
    c1, c2, c3 = 3424 / 4096, 2413 / 4096 * 32, 2392 / 4096 * 32
    y = max(nits, 0) / 10000
    n = ((c1 + c2 * y**m1) / (1 + c3 * y**m1)) ** m2
    return int(round(64 + n * 876))


class Frame:
    def __init__(self, bg):
        self.y = np.full((H, W), bg, dtype=np.uint16)

    def rect(self, x, y, w, h, v):
        self.y[y:y + h, x:x + w] = v

    def text(self, s, x, y, size, v):
        mask = Image.new("L", (W, H), 0)
        ImageDraw.Draw(mask).text((x, y), s, fill=255, font=font(size), anchor="mm")
        self.y[np.asarray(mask) > 127] = v

    def write_yuv(self, path):
        c = np.full((H // 2, W // 2), 512, dtype=np.uint16)
        with open(path, "wb") as f:
            for plane in (self.y, c, c):
                f.write(plane.astype("<u2").tobytes())


def patches(f, values, label_v, inner=None, title=None):
    n, pw, gap = len(values), 300, 60
    x0, top, ph = (W - (n * pw + (n - 1) * gap)) // 2, 760, 640
    for i, v in enumerate(values):
        x = x0 + i * (pw + gap)
        f.rect(x, top, pw, ph, v)
        if inner is not None:
            f.rect(x + pw // 4, top + ph // 4, pw // 2, ph // 2, inner[i])
        f.text(str(i + 1), x + pw // 2, top + ph + 140, 120, label_v)
    if title:
        f.text(title, W // 2, 330, 90, label_v)


def build():
    out = {}
    lv = [12, 14, 16, 17, 18, 19, 20, 22, 24, 26]          # bars 1-3 at/below black
    f = Frame(sdr(16))
    patches(f, [sdr(v) for v in lv], sdr(70), title="What is the LOWEST number whose bar you can see?")
    out["sdr_black"] = (f, "sdr", {str(i + 1): v for i, v in enumerate(lv)})

    lv = [222, 226, 230, 233, 235, 238, 242, 246, 250]      # inner square +4 levels
    f = Frame(sdr(180))
    patches(f, [sdr(v) for v in lv], sdr(40), inner=[sdr(v + 4) for v in lv],
            title="Highest number where you can still see the inner square?")
    out["sdr_white"] = (f, "sdr", {str(i + 1): [v, v + 4] for i, v in enumerate(lv)})

    f = Frame(sdr(128))
    for k in range(12):
        f.rect(700 + k * 200, 700, 4, 800, sdr(16))
        f.rect(500, 760 + k * 60, 2800, 3, sdr(16))
    f.text("Do you see thin bright outlines along the black lines? (yes / no)", W // 2, 360, 90, sdr(16))
    out["sdr_sharpness"] = (f, "sdr", {})

    f = Frame(sdr(16))
    f.y[600:1600, :] = np.linspace(sdr(16), sdr(235), W).round().astype(np.uint16)
    f.text("Grey ramp: should be smooth and neutral grey, no colour tint", W // 2, 330, 90, sdr(200))
    out["sdr_ramp"] = (f, "sdr", {})

    nits = [0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0]
    f = Frame(pq(0))
    patches(f, [pq(v) for v in nits], pq(15), title="HDR: LOWEST number whose bar you can see?")
    out["hdr_black"] = (f, "hdr", {str(i + 1): v for i, v in enumerate(nits)})

    nits = [100, 200, 300, 400, 500, 600, 800, 1000, 1500, 4000]   # inner square +12%
    f = Frame(pq(20))
    patches(f, [pq(v) for v in nits], pq(150), inner=[pq(v * 1.12) for v in nits],
            title="HDR: highest number where you can still see the inner square?")
    out["hdr_white"] = (f, "hdr", {str(i + 1): [v, round(v * 1.12)] for i, v in enumerate(nits)})
    return out


SDR = ["-x265-params", "colorprim=bt709:transfer=bt709:colormatrix=bt709:range=limited:aq-mode=0:keyint=48:qp=4:log-level=error",
       "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv"]
HDR = ["-x265-params", "colorprim=bt2020:transfer=smpte2084:colormatrix=bt2020nc:range=limited:hdr10=1:hdr10-opt=1:"
       "repeat-headers=1:master-display=G(13250,34500)B(7500,3000)R(34000,16000)WP(15635,16450)L(10000000,1):"
       "max-cll=1000,400:aq-mode=0:keyint=48:qp=4:log-level=error",
       "-color_primaries", "bt2020", "-color_trc", "smpte2084", "-colorspace", "bt2020nc", "-color_range", "tv"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--minutes", type=int, default=3)
    ap.add_argument("--only", help="comma list: sdr_black,sdr_white,sdr_sharpness,sdr_ramp,hdr_black,hdr_white")
    a = ap.parse_args()
    ff = shutil.which("ffmpeg")
    if not ff:
        sys.exit("ffmpeg not found (needs libx265). Install it, e.g. winget install ffmpeg / brew install ffmpeg / apt install ffmpeg")
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    want = set(a.only.split(",")) if a.only else None
    key = {}
    for i, (name, (frame, kind, mapping)) in enumerate(build().items(), 1):
        if want and name not in want:
            continue
        stem = f"{i:02d}_{name}"
        raw, seg = out / f"{stem}.yuv", out / f"{stem}.seg.mp4"
        frame.write_yuv(raw)
        # encode one 2-second GOP, then repeat it by stream copy (static image, no re-encode)
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-stream_loop", "-1", "-f", "rawvideo",
                        "-pix_fmt", "yuv420p10le", "-s", f"{W}x{H}", "-r", str(FPS), "-i", str(raw),
                        "-frames:v", str(FPS * 2), "-pix_fmt", "yuv420p10le", "-c:v", "libx265",
                        *(SDR if kind == "sdr" else HDR), "-tag:v", "hvc1", str(seg)], check=True)
        subprocess.run([ff, "-y", "-hide_banner", "-loglevel", "error", "-stream_loop", str(a.minutes * 30 - 1),
                        "-i", str(seg), "-c", "copy", "-tag:v", "hvc1", "-movflags", "+faststart",
                        str(out / f"{stem}.mp4")], check=True)
        raw.unlink()
        seg.unlink()
        key[stem] = {"type": kind, "patches": mapping}
        print("built", stem)
    (out / "pattern_key.json").write_text(json.dumps(key, indent=2))


if __name__ == "__main__":
    main()
