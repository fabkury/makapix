#!/usr/bin/env python3
"""Generate web/public/og-default.png — the default social-share (Open Graph) card.

This 1200x630 PNG is what Discord / Slack / Bluesky / X / iMessage etc. show
when a Makapix link is shared (wired up in web/src/pages/_app.tsx).

It needs Pillow + the DejaVu fonts. The host has no Pillow, but the API/worker
containers do. Regenerate with:

    F=/usr/share/fonts/truetype/dejavu
    docker cp "$F/DejaVuSans-Bold.ttf"  makapix-dev-worker:/tmp/
    docker cp "$F/DejaVuSans.ttf"       makapix-dev-worker:/tmp/
    docker cp web/scripts/generate-og-default.py makapix-dev-worker:/tmp/
    docker exec makapix-dev-worker python /tmp/generate-og-default.py \
        --out /tmp/og-default.png --fonts /tmp
    docker cp makapix-dev-worker:/tmp/og-default.png web/public/og-default.png

Tweak the COLORS / TEXT below and re-run to restyle. (Swap in the real brand
logo here later if desired — see web/public/brand/.)
"""
from __future__ import annotations

import argparse
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1200, 630
MARGIN = 84

# Brand palette (from web/src/components/Layout.tsx glow colors).
BG_TOP = (16, 16, 24)
BG_BOTTOM = (7, 7, 9)
WHITE = (255, 255, 255)
GREY = (201, 201, 212)
CYAN = (0, 212, 255)
PINK = (255, 110, 180)
PURPLE = (180, 78, 255)
BLUE = (78, 159, 255)

KICKER = "OPEN  ·  NO ADS  ·  NO AI SCRAPING"
TITLE = "Makapix Club"
TAGLINE = "Pixel art that lives on real-world displays"
FOOTER = "makapix.club"

# Classic 11x8 "space invader" — an unmistakable pixel-art motif.
INVADER = [
    "00100000100",
    "00010001000",
    "00111111100",
    "01101110110",
    "11111111111",
    "10111111101",
    "10100000101",
    "00011011000",
]


def _font(fonts_dir: str, name: str, size: int) -> ImageFont.FreeTypeFont:
    path = os.path.join(fonts_dir, name)
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        # Last resort so the script never hard-fails; looks worse.
        return ImageFont.load_default()


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if _text_w(draw, trial, font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def _vertical_gradient(size, top, bottom):
    w, h = size
    base = Image.new("RGB", size, top)
    top_r, top_g, top_b = top
    bot_r, bot_g, bot_b = bottom
    px = base.load()
    for y in range(h):
        t = y / max(1, h - 1)
        row = (
            int(top_r + (bot_r - top_r) * t),
            int(top_g + (bot_g - top_g) * t),
            int(top_b + (bot_b - top_b) * t),
        )
        for x in range(w):
            px[x, y] = row
    return base


def _gradient_bar(w, h, left, right):
    bar = Image.new("RGB", (w, h), left)
    px = bar.load()
    for x in range(w):
        t = x / max(1, w - 1)
        col = (
            int(left[0] + (right[0] - left[0]) * t),
            int(left[1] + (right[1] - left[1]) * t),
            int(left[2] + (right[2] - left[2]) * t),
        )
        for y in range(h):
            px[x, y] = col
    return bar


def build(fonts_dir: str) -> Image.Image:
    img = _vertical_gradient((W, H), BG_TOP, BG_BOTTOM).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # ---- Right-hand "pixel display" with a neon glow ------------------------
    panel = 330
    px0 = W - MARGIN - panel
    py0 = (H - panel) // 2
    cols, rows = len(INVADER[0]), len(INVADER)
    cell = 22
    grid_w, grid_h = cols * cell, rows * cell
    gx0 = px0 + (panel - grid_w) // 2
    gy0 = py0 + (panel - grid_h) // 2

    # Glow layer: bright panel + invader, blurred, composited underneath.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.rounded_rectangle([px0, py0, px0 + panel, py0 + panel], radius=28,
                            fill=(0, 212, 255, 90))
    for r, line in enumerate(INVADER):
        for c, ch in enumerate(line):
            if ch == "1":
                x, y = gx0 + c * cell, gy0 + r * cell
                gdraw.rectangle([x, y, x + cell, y + cell], fill=(0, 212, 255, 180))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(20)))

    # Crisp bezel.
    draw.rounded_rectangle([px0, py0, px0 + panel, py0 + panel], radius=28,
                           fill=(18, 18, 24, 255), outline=(60, 60, 72, 255), width=2)
    # Invader pixels, colored per row cyan -> blue for a little depth.
    for r, line in enumerate(INVADER):
        t = r / max(1, rows - 1)
        col = (
            int(CYAN[0] + (BLUE[0] - CYAN[0]) * t),
            int(CYAN[1] + (BLUE[1] - CYAN[1]) * t),
            int(CYAN[2] + (BLUE[2] - CYAN[2]) * t),
            255,
        )
        for c, ch in enumerate(line):
            if ch == "1":
                x, y = gx0 + c * cell, gy0 + r * cell
                draw.rectangle([x + 1, y + 1, x + cell - 1, y + cell - 1], fill=col)

    # ---- Left-hand text -----------------------------------------------------
    kicker_font = _font(fonts_dir, "DejaVuSans-Bold.ttf", 22)
    draw.text((MARGIN, 92), KICKER, font=kicker_font, fill=CYAN)

    # Title, auto-shrunk to fit the column to the left of the display.
    max_text_w = px0 - MARGIN - 36
    title_size = 92
    while title_size > 40:
        title_font = _font(fonts_dir, "DejaVuSans-Bold.ttf", title_size)
        if _text_w(draw, TITLE, title_font) <= max_text_w:
            break
        title_size -= 2
    title_y = 150
    draw.text((MARGIN, title_y), TITLE, font=title_font, fill=WHITE)
    title_bottom = title_y + title_font.getbbox(TITLE)[3]

    # Neon accent underline (pink -> cyan), echoing the site's active-nav bar.
    bar = _gradient_bar(200, 8, PINK, CYAN)
    img.paste(bar, (MARGIN, title_bottom + 20))

    # Tagline, wrapped.
    tag_font = _font(fonts_dir, "DejaVuSans.ttf", 34)
    ty = title_bottom + 56
    for line in _wrap(draw, TAGLINE, tag_font, max_text_w):
        draw.text((MARGIN, ty), line, font=tag_font, fill=GREY)
        ty += int(tag_font.size * 1.32)

    # Footer URL.
    foot_font = _font(fonts_dir, "DejaVuSans-Bold.ttf", 34)
    draw.text((MARGIN, H - MARGIN - 34), FOOTER, font=foot_font, fill=CYAN)

    return img.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fonts", default="/usr/share/fonts/truetype/dejavu")
    args = ap.parse_args()
    img = build(args.fonts)
    img.save(args.out, "PNG", optimize=True)
    print(f"wrote {args.out} ({img.size[0]}x{img.size[1]})")


if __name__ == "__main__":
    main()
