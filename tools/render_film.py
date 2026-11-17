#!/usr/bin/env python3
"""Render docs/demo.mp4: cards, the recorded attack, page stills, burned-in captions.

Captions are drawn with Pillow and overlaid with enable windows, because this ffmpeg build has no libass.
Requires demo/page_full.png, demo/attack.cast, demo/narration2.wav and demo/subs.json.
"""
import json
import pathlib
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
FFMPEG = "ffmpeg"
FFPROBE = "ffprobe"
W, H = 1280, 720
BG = (10, 10, 11)
PAPER = (244, 241, 234)
MUTED = (154, 149, 140)
AMBER = (224, 163, 62)
RED = (226, 86, 74)
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_B = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"{' '.join(cmd)}\n{p.stderr[-900:]}")
    return p.stdout


def dur(path):
    return float(run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                      "-of", "default=nw=1:nk=1", str(path)]).strip())


def card_one(path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((72, 64), "SECOND GUARD   ·   REACTIVE OMNI BUILDATHON", font=font(MONO, 15), fill=MUTED)
    d.text((72, 170), "Two venues trade", font=font(SERIF, 62), fill=PAPER)
    d.text((72, 246), "the same pair.", font=font(SERIF, 62), fill=PAPER)
    d.text((72, 356), "The gap between them is the attack surface.", font=font(SERIF, 40), fill=AMBER)
    d.line((72, 470, W - 72, 470), fill=(48, 48, 50), width=1)
    d.text((72, 500), "Base Sepolia 84532      Unichain Sepolia 1301", font=font(MONO, 18), fill=PAPER)
    d.text((72, 534), "watched from Reactive Lasna 5318007", font=font(MONO, 18), fill=MUTED)
    d.text((72, 580), "real testnets  ·  real transactions  ·  no simulation", font=font(MONO, 15), fill=MUTED)
    img.save(path)


def card_two(path):
    res = json.loads((ROOT / "guard_result.json").read_text())
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((72, 64), "PROOF   ·   ON CHAIN", font=font(MONO, 15), fill=MUTED)
    seconds = round(res["base"]["blocks"] * 0.2, 1)
    d.text((72, 130), f"One event. Two chains. {seconds} seconds.", font=font(SERIF, 46), fill=PAPER)
    rows = [
        ("attack", res["attack"]["tx"], "block " + str(res["attack"]["block"]), PAPER),
        ("base", res["base"]["tx"], "paused", RED),
        ("uni", res["uni"]["tx"], "paused", RED),
    ]
    bps = res["divergenceBps"]
    src = res["sourceBlock"]
    y = 214
    for label, tx, note, colour in rows:
        d.text((72, y), label.ljust(8), font=font(MONO_B, 17), fill=MUTED)
        d.text((190, y), tx[:44] + "...", font=font(MONO, 17), fill=PAPER)
        d.text((190, y + 26), tx[44:], font=font(MONO, 17), fill=PAPER)
        d.text((190, y + 52), note, font=font(MONO, 15), fill=colour)
        y += 88
    d.line((72, 486, W - 72, 486), fill=(48, 48, 50), width=1)
    d.text((72, 508), f"{bps} bps divergence   ·   source block {src} echoed on both chains",
           font=font(MONO, 16), fill=AMBER)
    d.text((72, 536), "guard 0x85408366c1AE50491755a75378e98F2B27469818  ·  Lasna",
           font=font(MONO, 15), fill=MUTED)
    d.text((72, 564), "github.com/farhanqaz/second-guard  ·  farhanqaz.github.io/second-guard",
           font=font(MONO, 14), fill=MUTED)
    img.save(path)


def crop(src, box, out):
    Image.open(src).crop(box).resize((W, H), Image.LANCZOS).save(out)


def clip(img, seconds, out):
    run([FFMPEG, "-y", "-loop", "1", "-i", str(img), "-t", str(seconds),
         "-vf", f"scale={W}:{H},format=yuv420p", "-r", "30", str(out)])


def wrap(text, maxchars):
    words, lines, cur = text.split(), [], ""
    for w in words:
        cand = (cur + " " + w).strip()
        if len(cand) <= maxchars:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines[:3]


def caption_png(text, path):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    f = font(MONO, 22)
    lines = wrap(text, 72)
    pad_x, pad_y, lh = 18, 12, 30
    widths = [d.textlength(l, font=f) for l in lines]
    bw = int(max(widths)) + pad_x * 2
    bh = lh * len(lines) + pad_y * 2
    x0 = (W - bw) // 2
    y0 = H - bh - 34
    d.rectangle([x0, y0, x0 + bw, y0 + bh], fill=(21, 19, 15, 232))
    for i, line in enumerate(lines):
        d.text((x0 + pad_x, y0 + pad_y + i * lh), line, font=f, fill=PAPER)
    img.save(path)


def main():
    card_one(DEMO / "card1.png")
    card_two(DEMO / "card2.png")
    crop(DEMO / "page_top.png", (0, 0, 1280, 720), DEMO / "still_venues.png")
    crop(DEMO / "page_mid.png", (0, 0, 1280, 720), DEMO / "still_feed.png")

    run(["python3", str(ROOT / "tools" / "cast2mp4.py"),
         str(DEMO / "attack.cast"), str(DEMO / "cast.mp4"), "--title", "second-guard / tools/attack.py"])

    clip(DEMO / "card1.png", 9, DEMO / "s1.mp4")
    clip(DEMO / "still_venues.png", 7, DEMO / "s2.mp4")
    clip(DEMO / "still_feed.png", 7, DEMO / "s3.mp4")
    clip(DEMO / "card2.png", 12, DEMO / "s5.mp4")

    parts = [DEMO / "s1.mp4", DEMO / "cast.mp4", DEMO / "s2.mp4", DEMO / "s3.mp4", DEMO / "s5.mp4"]
    lst = DEMO / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(DEMO / "silent.mp4")])
    video = dur(DEMO / "silent.mp4")
    audio = dur(DEMO / "narration2.wav")

    cues = json.loads((DEMO / "subs.json").read_text())
    filters = []
    for i, cue in enumerate(cues, start=1):
        txt = DEMO / f"cue{i:02d}.txt"
        txt.write_text("\n".join(wrap(cue["text"], 56)))
        # gte*lte instead of between(a,b): commas inside an expression would split the filter chain
        filters.append(
            "drawtext=fontfile=" + MONO + ":textfile=" + str(txt) +
            ":fontsize=23:fontcolor=0xEFE9DC:box=1:boxcolor=0x15130F@0.92:boxborderw=16" +
            ":x=(w-text_w)/2:y=h-text_h-36" +
            f":enable='between(t\\,{cue['start']}\\,{cue['end']})'"
        )
    run([FFMPEG, "-y", "-i", str(DEMO / "silent.mp4"),
         "-vf", ",".join(filters), "-r", "30", "-pix_fmt", "yuv420p",
         "-c:v", "libx264", "-crf", "19", "-preset", "medium",
         "-t", str(video), str(DEMO / "captioned.mp4")])

    run([FFMPEG, "-y", "-i", str(DEMO / "captioned.mp4"), "-i", str(DEMO / "narration2.wav"),
         "-filter_complex", f"[1:a]apad=whole_dur={video + 1}[a]", "-map", "0:v", "-map", "[a]",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart",
         "-t", f"{video + 1}", str(ROOT / "docs" / "demo.mp4")])

    print(json.dumps({"video_s": round(video, 2), "audio_s": round(audio, 2), "cues": len(cues),
                      "out_s": round(dur(ROOT / "docs" / "demo.mp4"), 2)}, indent=1))


if __name__ == "__main__":
    main()
