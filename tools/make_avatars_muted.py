# -*- coding: utf-8 -*-
"""Elegant v2 avatars: dark slate base, hairline accent ring, light-weight glyph.

Rendered at 4x then downsampled for clean anti-aliased edges.
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\明远阁\avatars"
os.makedirs(OUT, exist_ok=True)

FONT_LIGHT = r"C:\Windows\Fonts\msyh.ttc"   # 微软雅黑 regular
S = 256
SS = 4          # supersample factor
N = S * SS

# name -> (glyph, accent color)
TEAM = {
    "MarketAnalyst":        ("市", (91, 141, 239)),
    "FundamentalResearcher":("基", (72, 189, 143)),
    "NewsMonitor":          ("舆", (233, 165, 74)),
    "RiskManager":          ("风", (231, 106, 106)),
    "StrategyDeveloper":    ("策", (149, 122, 240)),
    "MacroAnalyst":         ("宏", (86, 176, 206)),
    "MarketMonitor":        ("监", (140, 152, 174)),
    "Chief":                ("总", (206, 174, 120)),
}

BASE_TOP = (34, 39, 48)
BASE_BOT = (18, 21, 26)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


for key, (ch, accent) in TEAM.items():
    img = Image.new("RGB", (N, N), BASE_TOP)
    d = ImageDraw.Draw(img)

    # vertical base gradient
    for y in range(N):
        d.line([(0, y), (N, y)], fill=mix(BASE_TOP, BASE_BOT, y / N))

    # very subtle radial tint toward the accent color, top-left
    glow = Image.new("RGB", (N, N), (0, 0, 0))
    gd = ImageDraw.Draw(glow)
    steps = 90
    for i in range(steps, 0, -1):
        t = i / steps
        r = int(N * 0.78 * t)
        col = mix((0, 0, 0), accent, 0.055 * (1 - t))
        gd.ellipse((N * 0.30 - r, N * 0.22 - r, N * 0.30 + r, N * 0.22 + r), fill=col)
    img = Image.blend(img, glow, 0.9)
    d = ImageDraw.Draw(img)

    # hairline accent ring, inset, radius smaller than the tile so it never clips
    inset = 14 * SS
    d.rounded_rectangle(
        (inset, inset, N - inset - 1, N - inset - 1),
        radius=44 * SS,
        outline=accent,
        width=2 * SS,
    )

    # glyph, light weight, centered optically
    font = ImageFont.truetype(FONT_LIGHT, int(S * 0.48) * SS)
    bbox = d.textbbox((0, 0), ch, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (N - w) / 2 - bbox[0]
    y = (N - h) / 2 - bbox[1] - S * 0.01 * SS
    d.text((x, y), ch, font=font, fill=(238, 240, 243))

    img = img.resize((S, S), Image.LANCZOS)

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), rounded_mask(S, 62))
    path = os.path.join(OUT, key + ".png")
    out.save(path, "PNG", optimize=True)
    print(key, os.path.getsize(path), "bytes")
