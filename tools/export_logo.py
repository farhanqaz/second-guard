#!/usr/bin/env python3
"""Export the Second Guard logo set: icon, avatar, lockups, SVG.

The mark is the product's own instrument: two markers on one rule, one filled, one open,
with a tick that points at the gap being measured.

Usage: python3 tools/export_logo.py
"""
import pathlib

from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "branding"
FONT_BOLD = OUT / ".fonts" / "Bricolage-700.ttf"

CHARCOAL = (20, 18, 15)
PAPER = (242, 236, 224)
OXIDE = (224, 101, 77)
INK = (21, 19, 15)
RULE_ON_DARK = (150, 143, 130)
RULE_ON_LIGHT = (120, 112, 99)

S = 4  # supersample factor


def draw_mark(d, x, y, size, body, accent, rule):
    """Draw the mark inside a size x size box whose top left corner is (x, y).

    The rule stops at the edge of every marker, so nothing shows through the open ring. The short
    middle segment is the gap being measured, and the tick points at it.
    """
    u = size / 32.0
    # the design grid sits low, so shift the whole mark up to centre its ink, not its grid
    y = y - 3.2 * u
    cy = y + 19.2 * u
    rule_w = max(2, round(0.95 * u))
    r = 3.6 * u
    dot_x, ring_x = x + 9.8 * u, x + 22.4 * u
    ring_w = max(2, round(1.8 * u))

    for a, b in ((x + 2.2 * u, dot_x - r), (ring_x + r, x + 29.8 * u)):
        if b > a:
            d.line([(a, cy), (b, cy)], fill=rule, width=rule_w)

    d.ellipse([dot_x - r, cy - r, dot_x + r, cy + r], fill=body)
    d.ellipse([ring_x - r, cy - r, ring_x + r, cy + r], outline=accent, width=ring_w)
    # no tick: the break in the rule plus the two markers carries the idea at any size


def icon(path, size, bg=None, body=PAPER, accent=OXIDE, rule=RULE_ON_DARK, pad_ratio=0.10):
    canvas = Image.new("RGBA", (size * S, size * S), (0, 0, 0, 0) if bg is None else bg + (255,))
    d = ImageDraw.Draw(canvas)
    pad = int(size * pad_ratio) * S
    draw_mark(d, pad, pad, size * S - 2 * pad, body, accent, rule)
    canvas.resize((size, size), Image.LANCZOS).save(path)
    print(path.name, size)


def lockup(path, dark=True, height=400):
    """Wordmark lockup sized from the measured text, so nothing is ever cropped."""
    body = PAPER if dark else INK
    accent = OXIDE
    rule = RULE_ON_DARK if dark else RULE_ON_LIGHT

    probe = Image.new("RGBA", (10, 10))
    pd = ImageDraw.Draw(probe)
    size_px = int(height * 0.36 * S)
    f = ImageFont.truetype(str(FONT_BOLD), size_px)
    label, tail = "Second", "Guard"
    dot_r = int(height * 0.035 * S)
    dot_gap = int(height * 0.035 * S)
    tw = pd.textlength(label, font=f) + pd.textlength(tail, font=f) + dot_gap * 2 + dot_r * 2

    mark_size = int(height * 0.50) * S
    pad = int(height * 0.14) * S
    gap = int(height * 0.06) * S
    width = int((pad * 2 + mark_size + gap + tw) / S)

    canvas = Image.new("RGBA", (width * S, height * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(canvas)
    draw_mark(d, pad, (height * S - mark_size) // 2, mark_size, body, accent, rule)

    text_x = pad + mark_size + gap
    bbox = d.textbbox((0, 0), label, font=f)
    cap_top, cap_bottom = bbox[1], bbox[3]
    ty = (height * S - (cap_bottom - cap_top)) // 2 - cap_top

    bw = d.textlength(label, font=f)
    d.text((text_x, ty), label, font=f, fill=body)
    cx = text_x + bw + dot_gap + dot_r
    cy = ty + cap_top + (cap_bottom - cap_top) * 0.52
    d.ellipse([cx - dot_r, cy - dot_r, cx + dot_r, cy + dot_r], fill=accent)
    tx = cx + dot_r + dot_gap
    d.text((tx, ty), tail, font=f, fill=body)

    canvas.resize((width, height), Image.LANCZOS).save(path)
    print(path.name, width, height)


def square(path, size=1024, wordmark=False):
    """Square tile for a project logo field: the mark centred, big enough to read at 64px."""
    canvas = Image.new("RGBA", (size * S, size * S), CHARCOAL + (255,))
    d = ImageDraw.Draw(canvas)
    if not wordmark:
        inset = int(size * 0.26) * S
        box = size * S - 2 * inset
        draw_mark(d, inset, inset, box, PAPER, OXIDE, RULE_ON_DARK)
    else:
        box = int(size * 0.70) * S
        draw_mark(d, (size * S - box) // 2, int(size * 0.03) * S, box, PAPER, OXIDE, RULE_ON_DARK)
        f = ImageFont.truetype(str(FONT_BOLD), int(size * 0.095) * S)
        label = "SECOND GUARD"
        tw = d.textlength(label, font=f)
        d.text(((size * S - tw) // 2, int(size * 0.58) * S), label, font=f, fill=PAPER)
        f2 = ImageFont.truetype(str(FONT_BOLD), int(size * 0.036) * S)
        sub = "PARITY DESK"
        tw2 = d.textlength(sub, font=f2)
        d.text(((size * S - tw2) // 2, int(size * 0.69) * S), sub, font=f2, fill=RULE_ON_DARK)
    canvas.resize((size, size), Image.LANCZOS).save(path)
    print(path.name, size)


def svg(path, dark=True):
    body = "#f2ece0" if dark else "#15130f"
    accent = "#e0654d"
    rule = "#968f82" if dark else "#7b7264"
    path.write_text(f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <title>Second Guard</title>
  <desc>Two venues on one rule, one filled and one open, with the rule broken between them.</desc>
  <g stroke="{rule}" stroke-width="15" stroke-linecap="round">
    <line x1="35" y1="256" x2="99" y2="256"/>
    <line x1="416" y1="256" x2="477" y2="256"/>
  </g>
  <circle cx="157" cy="256" r="58" fill="{body}"/>
  <circle cx="358" cy="256" r="58" fill="none" stroke="{accent}" stroke-width="29"/>
</svg>
""")
    print(path.name)


def main():
    OUT.mkdir(exist_ok=True)
    icon(OUT / "second-guard-icon-512.png", 512)
    icon(OUT / "second-guard-icon-1024.png", 1024)
    icon(OUT / "second-guard-icon-light-512.png", 512, body=INK, rule=RULE_ON_LIGHT)
    icon(OUT / "second-guard-avatar-1024.png", 1024, bg=CHARCOAL, pad_ratio=0.18)
    lockup(OUT / "second-guard-lockup-dark.png", dark=True)
    lockup(OUT / "second-guard-lockup-light.png", dark=False)
    square(OUT / "second-guard-square-512.png", 512)
    square(OUT / "second-guard-square-1024.png", 1024)
    square(OUT / "second-guard-square-wordmark-1024.png", 1024, wordmark=True)
    svg(OUT / "second-guard-logo-dark.svg", dark=True)
    svg(OUT / "second-guard-logo-light.svg", dark=False)


if __name__ == "__main__":
    main()
