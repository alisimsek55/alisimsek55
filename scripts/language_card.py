#!/usr/bin/env python3
"""Generate a GitHub-style "Languages" card (light + dark SVG) for a user's public repos.

Standard library only. Reads languages.config.json, asks the GitHub REST API for the
language byte counts of every public, non-fork, non-archived repo the user owns, and
writes:

    <output_dir>/languages-light.svg
    <output_dir>/languages-dark.svg
    <output_dir>/languages.json     (the numbers behind the card)

The "updated" date only moves when the numbers change, so scheduled runs that find
nothing new produce no diff and no commit.

Usage:
    python scripts/language_card.py [--config languages.config.json]

Set GITHUB_TOKEN for a higher API rate limit (optional; ~10 requests per run).
"""

from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

API = "https://api.github.com"
LINGUIST_YML = "https://raw.githubusercontent.com/github-linguist/linguist/main/lib/linguist/languages.yml"

# Official colours from github-linguist/linguist lib/linguist/languages.yml.
LINGUIST_COLORS = {
    "Assembly": "#6E4C13", "Astro": "#ff5a03", "Batchfile": "#C1F12E", "C": "#555555",
    "C#": "#7355dd", "C++": "#f34b7d", "CMake": "#DA3434", "CSS": "#663399",
    "Cuda": "#3A4E3A", "Dart": "#00B4AB", "Dockerfile": "#384d54", "GLSL": "#5686a5",
    "Go": "#00ADD8", "HTML": "#e34c26", "Java": "#b07219", "JavaScript": "#f1e05a",
    "Jupyter Notebook": "#DA5B0B", "Kotlin": "#A97BFF", "Lua": "#000080",
    "MATLAB": "#e16737", "Makefile": "#427819", "Objective-C": "#438eff", "PHP": "#4F5D95",
    "PowerShell": "#012456", "Python": "#3572A5", "R": "#198CE7", "Ruby": "#701516",
    "Rust": "#dea584", "SCSS": "#c6538c", "Shell": "#89e051", "Solidity": "#AA6746",
    "Svelte": "#ff3e00", "Swift": "#F05138", "TeX": "#3D6117", "TypeScript": "#3178c6",
    "Vue": "#41b883",
}
OTHER_COLOR = "#8b949e"

THEMES = {
    "light": {"fg": "#1f2328", "muted": "#59636e"},
    "dark": {"fg": "#f0f6fc", "muted": "#9198a1"},
}

FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"


def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def http_get(url: str, accept: str = "application/vnd.github+json") -> bytes | None:
    """GET a URL; returns None on 404, raises on other errors."""
    headers = {"Accept": accept, "User-Agent": "profile-language-card"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(API):
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except urllib.error.HTTPError as err:
        if err.code == 404:
            return None
        raise SystemExit(f"GET {url} failed: HTTP {err.code} {err.reason}")


def api_json(path: str):
    body = http_get(f"{API}{path}")
    return None if body is None else json.loads(body)


def list_repos(user: str) -> list[dict]:
    repos, page = [], 1
    while True:
        batch = api_json(f"/users/{user}/repos?type=owner&per_page=100&page={page}") or []
        repos.extend(batch)
        if len(batch) < 100:
            return repos
        page += 1


def gitattributes_marks_generated(user: str, repo: str, path: str) -> bool:
    """True if the repo's root .gitattributes already excludes `path` from Linguist."""
    raw = http_get(f"{API}/repos/{user}/{repo}/contents/.gitattributes", "application/vnd.github.raw")
    if raw is None:
        return False
    for line in raw.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) < 2 or parts[0].startswith("#"):
            continue
        pattern = parts[0].lstrip("/")
        attrs = parts[1:]
        excluded = any(a in ("linguist-generated", "linguist-generated=true",
                             "linguist-vendored", "linguist-vendored=true",
                             "linguist-documentation", "-linguist-detectable") for a in attrs)
        if excluded and (fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(path, pattern + "/*")
                         or fnmatch.fnmatch(path, "*/" + pattern)):
            return True
    return False


def file_size(user: str, repo: str, path: str) -> int | None:
    meta = api_json(f"/repos/{user}/{repo}/contents/{urllib.parse.quote(path)}")
    return None if not isinstance(meta, dict) else int(meta.get("size", 0))


def linguist_colors_remote() -> dict[str, str]:
    """Fallback for languages missing from LINGUIST_COLORS (parsed without a YAML library)."""
    try:
        text = http_get(LINGUIST_YML, "text/plain").decode("utf-8")
    except Exception as exc:  # network trouble must not break the card
        log(f"warning: could not fetch linguist colours ({exc})")
        return {}
    colors, current = {}, None
    for line in text.splitlines():
        if line and not line.startswith((" ", "#", "-")) and line.endswith(":"):
            current = line[:-1].strip("'\"")
        elif current and line.startswith("  color:"):
            colors[current] = line.split(":", 1)[1].strip().strip("'\"")
    return colors


def round_to_100(values: list[float], decimals: int = 1) -> list[float]:
    """Largest-remainder rounding so the displayed percentages add up to exactly 100."""
    scale = 10 ** decimals
    total_units = 100 * scale
    raw = [v * scale for v in values]
    floors = [int(r) for r in raw]
    short = total_units - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - floors[i], reverse=True)
    for i in order[:short]:
        floors[i] += 1
    return [f / scale for f in floors]


def collect(cfg: dict) -> dict:
    user = cfg["user"]
    include = set(cfg.get("include_repos") or [])
    exclude = set(cfg.get("exclude_repos") or []) | {user}
    excluded_langs = set(cfg.get("exclude_languages") or [])

    repos = []
    for r in list_repos(user):
        name = r["name"]
        if r.get("private") or r.get("fork") or r.get("archived"):
            continue
        if name in exclude or (include and name not in include):
            continue
        repos.append(name)
    repos.sort(key=str.lower)

    totals: dict[str, int] = {}
    for name in repos:
        langs = api_json(f"/repos/{user}/{name}/languages") or {}
        for lang, size in langs.items():
            if lang not in excluded_langs:
                totals[lang] = totals.get(lang, 0) + int(size)

    adjustments = []
    for item in cfg.get("subtract_files") or []:
        repo, path, lang = item["repo"], item["path"], item["language"]
        if repo not in repos or lang not in totals:
            continue
        if gitattributes_marks_generated(user, repo, path):
            log(f"skip subtract {repo}/{path}: already excluded via .gitattributes")
            continue
        size = file_size(user, repo, path)
        if size is None:
            log(f"warning: {repo}/{path} not found, nothing subtracted")
            continue
        totals[lang] = max(0, totals[lang] - size)
        adjustments.append({"repo": repo, "path": path, "language": lang, "bytes": size})

    totals = {k: v for k, v in totals.items() if v > 0}
    return {"user": user, "repos": repos, "bytes": dict(sorted(totals.items(), key=lambda kv: -kv[1])),
            "subtracted": adjustments}


def summarize(data: dict, cfg: dict) -> list[dict]:
    total = sum(data["bytes"].values())
    if not total:
        return []
    ranked = [(lang, b / total * 100) for lang, b in data["bytes"].items()]
    max_langs = int(cfg.get("max_languages", 6))
    min_pct = float(cfg.get("min_percent", 1.0))
    shown = [(l, p) for l, p in ranked if p >= min_pct][:max_langs]
    rest = ranked[len(shown):]
    if len(rest) == 1:          # a lone leftover keeps its own name
        shown, rest = shown + rest, []
    rows = [{"name": l, "raw": p} for l, p in shown]
    if rest:
        rows.append({"name": "Other", "raw": sum(p for _, p in rest), "other": [l for l, _ in rest]})
    for row, pct in zip(rows, round_to_100([r["raw"] for r in rows])):
        row["percent"] = pct
        del row["raw"]
    return rows


def render_svg(rows: list[dict], colors: dict[str, str], theme: str, title: str, footer: str,
               show_title: bool = True) -> str:
    t = THEMES[theme]
    width = 480
    bar_y, bar_h, gap = 30, 8, 2
    col_w, row_h, legend_y = 240, 22, 58
    if not show_title:  # no heading: pull the bar and legend up by the heading's height
        bar_y, legend_y = 2, 30
    n_rows = (len(rows) + 1) // 2
    footer_y = legend_y + n_rows * row_h + 6
    height = footer_y + 8

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">',
        f'<title id="t">{escape(title)}</title>',
        '<desc id="d">' + escape(", ".join(f"{r['name']} {r['percent']:.1f}%" for r in rows)) + "</desc>",
        f'<style>text{{font-family:{FONT};}}</style>',
        f'<defs><clipPath id="bar"><rect x="0" y="{bar_y}" width="{width}" height="{bar_h}" rx="{bar_h / 2}"/></clipPath></defs>',
    ]
    if show_title:
        parts.append(f'<text x="0" y="17" font-size="16" font-weight="600" fill="{t["fg"]}">{escape(title)}</text>')
    parts.append('<g clip-path="url(#bar)">')
    usable = width - gap * (len(rows) - 1)
    x = 0.0
    for i, r in enumerate(rows):
        w = usable * r["percent"] / 100
        if i == len(rows) - 1:
            w = width - x  # absorb float drift so the bar ends exactly at the edge
        parts.append(f'<rect x="{x:.2f}" y="{bar_y}" width="{max(w, 0):.2f}" height="{bar_h}" fill="{colors[r["name"]]}"/>')
        x += w + gap
    parts.append("</g>")

    for i, r in enumerate(rows):
        cx = (i % 2) * col_w
        cy = legend_y + (i // 2) * row_h
        name = r["name"] if len(r["name"]) <= 24 else r["name"][:23] + "…"
        parts.append(f'<circle cx="{cx + 4}" cy="{cy - 4}" r="4" fill="{colors[r["name"]]}"/>')
        parts.append(
            f'<text x="{cx + 14}" y="{cy}" font-size="12">'
            f'<tspan font-weight="600" fill="{t["fg"]}">{escape(name)}</tspan>'
            f'<tspan dx="6" fill="{t["muted"]}">{r["percent"]:.1f}%</tspan></text>'
        )
    parts.append(f'<text x="0" y="{footer_y}" font-size="11" fill="{t["muted"]}">{escape(footer)}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default="languages.config.json")
    args = ap.parse_args()

    cfg_path = Path(args.config)
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    root = cfg_path.resolve().parent
    out_dir = root / cfg.get("output_dir", "assets")
    out_dir.mkdir(parents=True, exist_ok=True)

    data = collect(cfg)
    rows = summarize(data, cfg)
    if not rows:
        log("no language data found; leaving existing files untouched")
        return 1
    data["card"] = rows

    json_path = out_dir / "languages.json"
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    updated = today
    if json_path.exists():
        old = json.loads(json_path.read_text(encoding="utf-8"))
        if {k: v for k, v in old.items() if k != "updated"} == data:
            updated = old.get("updated", today)
    data["updated"] = updated

    colors = dict(LINGUIST_COLORS)
    colors.update(cfg.get("colors") or {})
    missing = [r["name"] for r in rows if r["name"] not in colors and r["name"] != "Other"]
    if missing:
        colors.update({k: v for k, v in linguist_colors_remote().items() if k not in colors})
    for r in rows:
        colors.setdefault(r["name"], OTHER_COLOR)
    colors["Other"] = OTHER_COLOR

    n = len(data["repos"])
    footer = f"Across {n} public repo{'s' if n != 1 else ''} · by bytes of code · updated {updated}"
    for theme in THEMES:
        svg = render_svg(rows, colors, theme, cfg.get("title", "Languages"), footer,
                         bool(cfg.get("show_title", True)))
        (out_dir / f"languages-{theme}.svg").write_text(svg, encoding="utf-8", newline="\n")
    json_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")

    for r in rows:
        log(f"{r['name']:<16}{r['percent']:>6.1f}%")
    log(f"repos: {', '.join(data['repos'])}; total {sum(data['bytes'].values())} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
