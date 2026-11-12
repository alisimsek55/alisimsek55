"""Generate the animated terminal-style profile card (assets/terminal.svg).

The left side is an ASCII rendering of assets/cat.jpg, the right side a
neofetch-style info panel. Lines "type" in one after another (SMIL), so it
animates inside a GitHub README <img>. GitHub stats are read from the API.

Usage: python scripts/terminal_card.py [--offline]
"""
from __future__ import annotations

import argparse
import html
import json
import os
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
USER = "alisimsek55"

# ---- ASCII art ------------------------------------------------------------
COLS = 92
CROP = (0, 330, 900, 1330)  # head + chest of the cat
RAMP = " .:-=+*#%@"  # light -> dense; dark fur becomes dense characters
FONT = 7.0  # px
CHAR_W = FONT * 0.6
LINE_H = FONT * 1.08

# palette: "midnight aurora" (fur fades cyan -> violet top to bottom)
BG = "#0b1020"
FRAME = "#151d33"
FUR_TOP = (125, 207, 255)
FUR_BOT = (187, 154, 247)
WALL = "#1f2a44"
SEP = "#3b4a6b"
EYE = "#ffb347"
KEY = "#e0af68"
TEXT = "#c0caf5"
HEAD = "#9ece6a"
ACCENT = "#7dcfff"
PROMPT = "#9ece6a"


def mix(c1, c2, t):
    return "#" + "".join(f"{round(a + (b - a) * t):02x}" for a, b in zip(c1, c2))


BG_RGB = (11, 16, 32)

def ascii_art() -> list[list[tuple[str, str]]]:
    img = Image.open(ROOT / "assets" / "cat.jpg").convert("RGB").crop(CROP)
    rows = round(COLS * (img.height / img.width) * (CHAR_W / LINE_H))
    small = img.resize((COLS, rows), Image.LANCZOS)
    gray = ImageOps.grayscale(small).filter(ImageFilter.SHARPEN)
    g = np.asarray(gray, dtype=np.float32) / 255.0
    rgb = np.asarray(small, dtype=np.float32) / 255.0
    hsv = np.asarray(small.convert("HSV"), dtype=np.float32) / 255.0

    # The cat is almost uniformly black, so a global ramp turns it into a blob.
    # Rank-equalize the fur separately: its subtle shading then spans the
    # dense half of the ramp, while wall and sofa use the sparse half.
    d = np.zeros_like(g)
    fur = g < 0.30
    vals = g[fur]
    ranks = np.argsort(np.argsort(vals)) / max(1, vals.size - 1)  # 0 = darkest
    d[fur] = 1.0 - 0.55 * ranks  # 1.0 .. 0.45
    rest = ~fur
    d[rest] = np.clip((0.85 - g[rest]) / 0.55, 0, 1) * 0.42  # wall ~0, sofa mid

    out = []
    for y in range(rows):
        t = y / (rows - 1)
        fur_c = tuple(a + (b - a) * t for a, b in zip(FUR_TOP, FUR_BOT))
        fur_full = mix(fur_c, fur_c, 0)
        fur_dim = mix(fur_c, BG_RGB, 0.35)
        line = []
        for x in range(COLS):
            h, s, v = hsv[y, x]
            r, gg, b = rgb[y, x]
            # yellow iris: warm hue, saturated, bright-ish
            if 0.10 < h < 0.22 and s > 0.45 and v > 0.35 and r > b + 0.2:
                line.append(("@", EYE))
                continue
            ch = RAMP[min(len(RAMP) - 1, int(d[y, x] * len(RAMP)))]
            if d[y, x] > 0.8:
                color = fur_full
            elif d[y, x] > 0.44:
                color = fur_dim
            else:
                color = WALL
            line.append((ch, color))
        out.append(line)
    return out


# ---- info panel -----------------------------------------------------------
def github_stats(offline: bool) -> dict:
    if offline:
        return {"repos": "?", "followers": "?", "following": "?"}
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "terminal-card"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    def get(url):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r)

    user = get(f"https://api.github.com/users/{USER}")
    return {
        "repos": user["public_repos"],
        "followers": user["followers"],
        "following": user["following"],
    }


def info_lines(stats: dict) -> list[list[tuple[str, str]]]:
    def kv(key, value):
        return [(f"{key}:", KEY), (" " + "." * max(2, 12 - len(key)) + " ", SEP), (value, TEXT)]

    def section(title):
        return [(f"# {title} ", HEAD), ("-" * (40 - len(title)), SEP)]

    return [
        [("$ ", PROMPT), ("neofetch --ascii cat.jpg", TEXT)],
        [],
        [("ali", ACCENT), ("@", TEXT), (USER, ACCENT)],
        [("-" * 15, SEP)],
        kv("OS", "Windows 11"),
        kv("Host", "OSTIM Technical University"),
        kv("Kernel", "Software Engineering student"),
        kv("Location", "Ankara, Turkiye"),
        kv("Email", "230205037@ostimteknik.edu.tr"),
        [],
        kv("Languages", "TypeScript, Solidity, Python"),
        kv("Web", "Next.js, React, Ponder, PostgreSQL"),
        kv("Contracts", "Foundry, OpenZeppelin, Uniswap v3"),
        kv("Vision", "OpenCV, MediaPipe, PyTorch"),
        kv("UAV", "PX4 SITL, Gazebo, ROS 2"),
        [],
        section("Status"),
        [],
        kv("Open to", "software engineering internships"),
        [],
        section("GitHub Stats"),
        [],
        kv("Repos", str(stats["repos"])),
        kv("Followers", f"{stats['followers']} | Following: {stats['following']}"),
    ]


# ---- SVG ------------------------------------------------------------------
def runs_to_tspans(runs: list[tuple[str, str]]) -> str:
    merged: list[list[str]] = []
    for text, color in runs:
        if merged and merged[-1][1] == color:
            merged[-1][0] += text
        else:
            merged.append([text, color])
    return "".join(
        f'<tspan fill="{c}">{html.escape(t).replace(" ", "&#160;")}</tspan>' for t, c in merged
    )


def build_svg(art, info) -> str:
    pad = 24
    top = 44
    art_w = COLS * CHAR_W
    art_h = len(art) * LINE_H
    info_x = pad + art_w + 28
    info_font = 12.0
    info_cw = info_font * 0.6
    info_lh = 17.0
    info_w = max(sum(len(t) for t, _ in line) for line in info) * info_cw
    width = round(info_x + info_w + pad)
    info_h = len(info) * info_lh
    height = round(top + max(art_h, info_h) + pad)
    info_top = top + max(0, (art_h - info_h) / 2)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Consolas, \'Courier New\', monospace">',
        f"<title>{USER} - terminal card</title>",
        f'<rect width="{width}" height="{height}" rx="10" fill="{BG}" stroke="{FRAME}" stroke-width="2"/>',
        f'<rect width="{width}" height="28" rx="10" fill="{FRAME}"/>',
        f'<rect y="18" width="{width}" height="10" fill="{FRAME}"/>',
    ]
    for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"]):
        parts.append(f'<circle cx="{18 + i * 18}" cy="14" r="5.5" fill="{c}"/>')
    parts.append(
        f'<text x="{width / 2}" y="18" fill="{SEP}" font-size="11" text-anchor="middle">ali@{USER}: ~</text>'
    )

    # ASCII art: rows appear top to bottom
    art_dur = 2.2
    eyes = []
    for i, line in enumerate(art):
        for x, (ch, c) in enumerate(line):
            if c == EYE:
                eyes.append((x, i))
                line[x] = (" ", WALL)
    parts.append(f'<g font-size="{FONT}">')
    for i, line in enumerate(art):
        y = top + (i + 1) * LINE_H
        begin = art_dur * i / len(art)
        parts.append(
            f'<text x="{pad}" y="{y:.2f}" textLength="{art_w:.1f}" lengthAdjust="spacingAndGlyphs" '
            f'opacity="0">{runs_to_tspans(line)}'
            f'<animate attributeName="opacity" from="0" to="1" begin="{begin:.2f}s" dur="0.05s" fill="freeze"/></text>'
        )
    parts.append("</g>")
    blink = (
        '<animate attributeName="opacity" values="0;1;1;0.05;1;1" keyTimes="0;0.02;0.9;0.93;0.96;1" '
        f'dur="5s" begin="{art_dur:.2f}s" repeatCount="indefinite"/>'
    )
    parts.append(f'<g font-size="{FONT * 1.15:.1f}" fill="{EYE}" filter="url(#glow)" opacity="0">')
    for x, i in eyes:
        parts.append(f'<text x="{pad + x * CHAR_W:.2f}" y="{top + (i + 1) * LINE_H:.2f}">@</text>')
    parts.append(blink + "</g>")

    # info: each line typed in with an expanding clip
    parts.append(f'<g font-size="{info_font}">')
    t = 0.4
    defs = []
    for i, line in enumerate(info):
        if not line:
            continue
        n = sum(len(s) for s, _ in line)
        y = info_top + (i + 1) * info_lh
        w = n * info_cw + 4
        dur = max(0.15, n * 0.01)
        cid = f"c{i}"
        defs.append(
            f'<clipPath id="{cid}"><rect x="{info_x - 2:.1f}" y="{y - info_lh + 3:.1f}" width="0" height="{info_lh}">'
            f'<animate attributeName="width" from="0" to="{w:.1f}" begin="{t:.2f}s" dur="{dur:.2f}s" fill="freeze"/>'
            f"</rect></clipPath>"
        )
        parts.append(
            f'<text x="{info_x:.1f}" y="{y:.1f}" textLength="{n * info_cw:.1f}" lengthAdjust="spacingAndGlyphs" '
            f'clip-path="url(#{cid})">{runs_to_tspans(line)}</text>'
        )
        t += dur + 0.05
    # blinking cursor after the last line
    last = max(i for i, line in enumerate(info) if line)
    cy = info_top + (last + 2) * info_lh
    parts.append(
        f'<rect x="{info_x:.1f}" y="{cy - info_lh + 4:.1f}" width="{info_cw:.1f}" height="{info_lh - 3}" fill="{ACCENT}" opacity="0">'
        f'<animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.01;0.5;0.51" dur="1s" begin="{t:.2f}s" repeatCount="indefinite"/></rect>'
    )
    parts.append("</g>")
    glow = (
        '<filter id="glow" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="1.6" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )
    parts.insert(1, "<defs>" + glow + "".join(defs) + "</defs>")
    parts.append("</svg>")
    return "\n".join(parts)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip the GitHub API")
    args = ap.parse_args()
    svg = build_svg(ascii_art(), info_lines(github_stats(args.offline)))
    out = ROOT / "assets" / "terminal.svg"
    out.write_text(svg, encoding="utf-8")
    print(f"wrote {out} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
