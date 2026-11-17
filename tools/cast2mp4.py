"""Render a cast written by rec.py into a real mp4.

    python3 cast2mp4.py run.cast run.mp4 --title "repo/demo — node run.mjs" \
        --audio narration.mp3 --min-duration 68

Requires Pillow, ffmpeg, and a monospace TTF (DejaVu Sans Mono by default).

Timing model: each recorded event becomes one frame held until the next event, so the video is as slow as
the run actually was. Two things that bite:

* `-vsync` was removed in ffmpeg 9 — use `-fps_mode cfr -r 5`. With the concat demuxer's per-file
  durations and VFR output, long holds produce a file whose later frames cannot be seeked to; forcing CFR
  fixes seeking and the player's duration.
* Generate the narration first and pass its ffprobe duration as --min-duration, otherwise the audio is cut
  off by the short final frame.
"""

import argparse
import json
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
BG = (11, 12, 14)
FG = (216, 220, 226)
DIM = (120, 128, 138)
ACCENT = (74, 222, 128)
BAR = (18, 20, 23)
W, H = 1280, 720
FS, LH, COLS, ROWS, PAD_X, PAD_TOP, BAR_H = 17, 23, 110, 28, 42, 62, 38


def load(path):
    with open(path) as f:
        json.loads(f.readline())  # header, unused
        return [json.loads(line) for line in f if line.strip()]


def wrap(text, cols=COLS):
    out = []
    for raw in text.split("\n"):
        while len(raw) > cols:
            out.append(raw[:cols])
            raw = raw[cols:]
        out.append(raw)
    return out


def render(lines, title, t_now, t_total):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype(FONT, FS)
    bold = ImageFont.truetype(BOLD, FS)
    small = ImageFont.truetype(FONT, 13)

    d.rectangle([0, 0, W, BAR_H], fill=BAR)
    for i, c in enumerate([(240, 95, 90), (250, 200, 90), (80, 200, 120)]):
        d.ellipse([16 + i * 16, 14, 26 + i * 16, 24], fill=c)
    d.text((W // 2, BAR_H // 2), title, font=small, fill=DIM, anchor="mm")
    d.rectangle([0, BAR_H, int(W * min(1.0, t_now / max(t_total, 0.001))), BAR_H + 2], fill=ACCENT)

    visible = lines[-ROWS:]
    y = PAD_TOP
    for i, line in enumerate(visible):
        is_head = line.strip()[:2] in {"1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9."}
        f = bold if is_head else font
        color = ACCENT if line.startswith("---") else ((255, 255, 255) if is_head else FG)
        d.text((PAD_X, y), line, font=f, fill=color)
        if i == len(visible) - 1:  # cursor
            d.rectangle([PAD_X + d.textlength(line, font=f) + 2, y - 1,
                         PAD_X + d.textlength(line, font=f) + 12, y + LH - 5], fill=ACCENT)
        y += LH
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cast")
    ap.add_argument("out")
    ap.add_argument("--title", default="demo")
    ap.add_argument("--audio")
    ap.add_argument("--min-duration", type=float, default=0.0)
    args = ap.parse_args()

    events = load(args.cast)
    total = max(events[-1][0] + 2.5 if events else 3.0, args.min_duration)
    tmp = tempfile.mkdtemp(prefix="cast2mp4-")
    frames, lines = [], []

    for i, (t, kind, data) in enumerate(events):
        if kind != "o":
            continue
        lines.extend(wrap(data))
        nxt = events[i + 1][0] if i + 1 < len(events) else total
        path = os.path.join(tmp, f"f{len(frames):05d}.png")
        render(lines, args.title, t, total).save(path)
        frames.append((path, max(0.05, nxt - t), t))

    if frames:
        pad = max(0.0, total - (frames[-1][2] + frames[-1][1]))
        frames.append((frames[-1][0], max(1.5, pad + 1.5), total))

    concat = os.path.join(tmp, "list.txt")
    with open(concat, "w") as f:
        f.write("ffconcat version 1.0\n")
        for path, hold, _ in frames:
            f.write(f"file '{path}'\nduration {hold:.3f}\n")
        f.write(f"file '{frames[-1][0]}'\n")

    silent = os.path.join(tmp, "silent.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", concat,
         "-fps_mode", "cfr", "-r", "5", "-pix_fmt", "yuv420p", "-c:v", "libx264",
         "-preset", "medium", "-crf", "20", silent],
        capture_output=True, text=True)
    if r.returncode != 0:
        print("ffmpeg failed:\n", r.stderr[-3000:], "\nlist kept at", concat)
        raise SystemExit(1)

    if args.audio:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", args.audio,
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", args.out], check=True)
    else:
        shutil.move(silent, args.out)

    dur = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "default=nw=1:nk=1", args.out], capture_output=True, text=True).stdout.strip()
    print(f"{args.out}: {float(dur):.1f}s, {len(frames)} frames, {os.path.getsize(args.out) / 1e6:.1f} MB")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
