# -*- coding: utf-8 -*-
"""Team avatars (v1, color-filled tiles) for the 明远阁 group.

256x256 PNG, rounded corners, bold glyph, per-role color.
Run: python make_avatars.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

OUT = r"D:\明远阁\avatars"
os.makedirs(OUT, exist_ok=True)

FONT = r"C:\Windows\Fonts\msyhbd.ttc"
S = 256

# name -> (char, bg, ring)
TEAM = {
    "MarketAnalyst": ("市", (30, 111, 224), (10, 61, 145)),         # 蓝
    "FundamentalResearcher": ("基", (14, 159, 110), (7, 92, 64)),   # 绿
    "NewsMonitor": ("舆", (234, 140, 12), (140, 78, 0)),            # 橙
    "RiskManager": ("风", (220, 38, 38), (126, 15, 15)),            # 红
    "StrategyDeveloper": ("策", (124, 58, 237), (65, 24, 143)),     # 紫
    "MacroAnalyst": ("宏", (8, 145, 178), (4, 82, 101)),            # 青
    "MarketMonitor": ("监", (51, 65, 85), (20, 28, 38)),            # 靛灰
    "Chief": ("总", (17, 24, 39), (0, 0, 0)),                       # 近黑
}


def rounded_mask(size, radius):
    m = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(m)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return m


for key, (ch, bg, ring) in TEAM.items():
    img = Image.new("RGB", (S, S), bg)
    d = ImageDraw.Draw(img)
    # soft vertical shading for depth
    for y in range(S):
        k = 1.0 - 0.22 * (y / S)
        d.line([(0, y), (S, y)], fill=tuple(int(c * k) for c in bg))
    # inner ring
    d.rounded_rectangle((8, 8, S - 9, S - 9), radius=56, outline=ring, width=6)
    # glyph
    font = ImageFont.truetype(FONT, 138)
    bbox = d.textbbox((0, 0), ch, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (S - w) / 2 - bbox[0]
    y = (S - h) / 2 - bbox[1] - 4
    # shadow then glyph
    d.text((x + 3, y + 4), ch, font=font, fill=tuple(int(c * 0.45) for c in ring))
    d.text((x, y), ch, font=font, fill=(255, 255, 255))

    # rounded corners + transparent background
    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(img, (0, 0), rounded_mask(S, 56))
    path = os.path.join(OUT, key + ".png")
    out.save(path, "PNG", optimize=True)
    print(path, os.path.getsize(path), "bytes")
