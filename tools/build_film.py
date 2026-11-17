#!/usr/bin/env python3
"""Build the demo film: two cards, the recorded attack, two page stills, one proof card.

Requires demo/page_full.png, demo/attack.cast and demo/narration.mp3 to exist first.
"""
import json
import pathlib
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
DEMO = ROOT / "demo"
FFMPEG = "ffmpeg"
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
        raise SystemExit(f"{' '.join(cmd)}\n{p.stderr[-800:]}")
    return p.stdout


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
    d.text((72, 640), "real testnets  ·  real transactions  ·  no simulation", font=font(MONO, 15), fill=MUTED)
    img.save(path)


def card_two(path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((72, 64), "PROOF   ·   ON CHAIN", font=font(MONO, 15), fill=MUTED)
    d.text((72, 130), "One event. Two chains. 1.2 seconds.", font=font(SERIF, 46), fill=PAPER)
    rows = [
        ("attack", "0x4a5db08d2810c4e7085c6c3948e63ee646e0288bdaaadb76282d1756e6ac083d", "block 59906925", PAPER),
        ("base", "0x0bf250fe0f739e5867a08214801c578d9cf6460e37e144bacce677f2c5d30c48", "paused", RED),
        ("uni", "0x25600b883c7bc8e7add5d96e030d7ccf62dfa2b581cd0595eb6726bcb0fb3c3a", "paused", RED),
    ]
    y = 250
    for label, tx, note, colour in rows:
        d.text((72, y), label.ljust(8), font=font(MONO_B, 17), fill=MUTED)
        d.text((190, y), tx[:44] + "...", font=font(MONO, 17), fill=PAPER)
        d.text((190, y + 26), tx[44:], font=font(MONO, 17), fill=PAPER)
        d.text((190, y + 52), note, font=font(MONO, 15), fill=colour)
        y += 100
    d.line((72, 560, W - 72, 560), fill=(48, 48, 50), width=1)
    d.text((72, 586), "2753 bps divergence   ·   source block 59906925 echoed on both chains",
           font=font(MONO, 16), fill=AMBER)
    d.text((72, 616), "guard 0x85408366c1AE50491755a75378e98F2B27469818  ·  Lasna",
           font=font(MONO, 15), fill=MUTED)
    d.text((72, 660), "github.com/farhanqaz/second-guard  ·  farhanqaz.github.io/second-guard",
           font=font(MONO, 14), fill=MUTED)
    img.save(path)


def crop(src, box, out):
    im = Image.open(src)
    im.crop(box).resize((W, H), Image.LANCZOS).save(out)


def clip_from_image(img, seconds, out):
    run([FFMPEG, "-y", "-loop", "1", "-i", str(img), "-t", str(seconds),
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x0a0a0b",
         "-r", "30", "-pix_fmt", "yuv420p", str(out)])


def main():
    card_one(DEMO / "card1.png")
    card_two(DEMO / "card2.png")
    crop(DEMO / "page_full.png", (0, 470, 1280, 1190), DEMO / "still_venues.png")
    crop(DEMO / "page_full.png", (0, 1050, 1280, 1770), DEMO / "still_feed.png")

    run(["python3", "/home/dell/.hermes/skills/hackathon-project-selection/scripts/cast2mp4.py",
         str(DEMO / "attack.cast"), str(DEMO / "cast.mp4"), "--title", "second-guard / tools/attack.py"])

    clip_from_image(DEMO / "card1.png", 9, DEMO / "s1.mp4")
    clip_from_image(DEMO / "still_venues.png", 7, DEMO / "s2.mp4")
    clip_from_image(DEMO / "still_feed.png", 7, DEMO / "s3.mp4")
    clip_from_image(DEMO / "card2.png", 12, DEMO / "s5.mp4")

    parts = [DEMO / "s1.mp4", DEMO / "cast.mp4", DEMO / "s2.mp4", DEMO / "s3.mp4", DEMO / "s5.mp4"]
    lst = DEMO / "concat.txt"
    lst.write_text("".join(f"file '{p}'\n" for p in parts))
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(DEMO / "silent.mp4")])

    dur = float(run([FFMPEG.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries", "format=duration",
                     "-of", "default=nw=1:nk=1", str(DEMO / "silent.mp4")]).strip())
    audio = float(run([FFMPEG.replace("ffmpeg", "ffprobe"), "-v", "error", "-show_entries", "format=duration",
                       "-of", "default=nw=1:nk=1", str(DEMO / "narration.mp3")]).strip())
    print(json.dumps({"video": round(dur, 2), "audio": round(audio, 2)}))

    run([FFMPEG, "-y", "-i", str(DEMO / "silent.mp4"), "-i", str(DEMO / "narration.mp3"),
         "-filter_complex", f"[1:a]apad=pad_dur=3,atrim=0:{max(dur, audio) + 0.5}[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
         "-fps_mode", "cfr", "-r", "30", "-movflags", "+faststart", "-t", str(max(dur, audio) + 0.5),
         str(ROOT / "docs" / "demo.mp4")])
    print("wrote docs/demo.mp4")


if __name__ == "__main__":
    main()
