#!/usr/bin/env python3
import collections
import hashlib
import os
from datetime import datetime, timedelta, timezone

import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USER = os.environ.get("G_USER", "gulldan")
DAYS = int(os.environ.get("DAYS", "30"))

HEAD = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
since = (
    (datetime.now(timezone.utc) - timedelta(days=DAYS))
    .isoformat()
    .replace("+00:00", "Z")
)

# 1) Ищем свежие коммиты автора
q = f"author:{USER} committer-date:>{since}"
r = requests.get(
    "https://api.github.com/search/commits",
    headers={**HEAD, "Accept": "application/vnd.github.cloak-preview+json"},
    params={"q": q, "sort": "committer-date", "order": "desc", "per_page": 50},
)
r.raise_for_status()
items = r.json().get("items", [])

lang_map = collections.Counter()


def ext2lang(path):
    p = path.lower()
    base = os.path.basename(p)
    # специальные имена файлов без расширений
    special_names = {
        "dockerfile": "Docker",
        "makefile": "Makefile",
        "cmakelists.txt": "CMake",
        "jenkinsfile": "Jenkins",
        "gemfile": "Ruby",
        "rakefile": "Ruby",
        "podfile": "CocoaPods",
        "vagrantfile": "Vagrant",
        "procfile": "Procfile",
        "brewfile": "Homebrew",
    }
    if base in special_names:
        return special_names[base]
    if base.startswith("dockerfile"):
        return "Docker"
    if base.endswith(".gradle") or base.endswith(".gradle.kts"):
        return "Gradle"
    # маппа расширений → языки
    mapping = {
        ".py": "Python",
        ".ipynb": "Python",
        ".go": "Go",
        ".rs": "Rust",
        ".ts": "TypeScript",
        ".tsx": "TypeScript",
        ".js": "JavaScript",
        ".jsx": "JavaScript",
        ".vue": "Vue",
        ".svelte": "Svelte",
        ".astro": "Astro",
        ".java": "Java",
        ".kt": "Kotlin",
        ".kts": "Kotlin",
        ".scala": "Scala",
        ".cs": "C#",
        ".swift": "Swift",
        ".m": "Objective-C",
        ".mm": "Objective-C++",
        ".php": "PHP",
        ".rb": "Ruby",
        ".dart": "Dart",
        ".ex": "Elixir",
        ".exs": "Elixir",
        ".erl": "Erlang",
        ".ml": "OCaml",
        ".hs": "Haskell",
        ".lua": "Lua",
        ".r": "R",
        ".jl": "Julia",
        ".sql": "SQL",
        ".proto": "Protocol Buffers",
        ".graphql": "GraphQL",
        ".gql": "GraphQL",
        ".sol": "Solidity",
        ".tf": "Terraform",
        ".tfvars": "Terraform",
        ".hcl": "HCL",
        ".cmake": "CMake",
        ".mk": "Makefile",
        ".bat": "Batch",
        ".cmd": "Batch",
        ".ps1": "PowerShell",
        ".psm1": "PowerShell",
        ".fish": "Shell",
        ".zsh": "Shell",
        ".sh": "Shell",
        ".bash": "Shell",
        ".scss": "SCSS",
        ".less": "Less",
        ".css": "CSS",
        ".html": "HTML",
        ".htm": "HTML",
        ".xml": "XML",
        ".yml": "YAML",
        ".yaml": "YAML",
        ".toml": "TOML",
        ".json": "JSON",
        ".md": "Markdown",
        ".rst": "reStructuredText",
        ".tex": "LaTeX",
    }
    for ext, lang in mapping.items():
        if p.endswith(ext):
            return lang
    return None


for it in items:
    repo_full = it["repository"]["full_name"]
    sha = it["sha"]
    rr = requests.get(
        f"https://api.github.com/repos/{repo_full}/commits/{sha}", headers=HEAD
    )
    if rr.status_code != 200:
        continue
    files = rr.json().get("files", [])
    for f in files:
        lang = ext2lang(f.get("filename", ""))
        if not lang:
            continue
        changes = f.get("additions", 0) + f.get("deletions", 0)
        lang_map[lang] += max(1, changes)

total = sum(lang_map.values()) or 1
parts_all = [(k, v / total * 100.0) for k, v in lang_map.most_common()]
TOP_N = 8
if len(parts_all) > TOP_N:
    top = parts_all[:TOP_N]
    other_pct = sum(p for _, p in parts_all[TOP_N:])
    if other_pct > 0:
        parts = top + [("Other", other_pct)]
    else:
        parts = top
else:
    parts = parts_all

# Генерируем горизонтальный барчарт для читабельности
w = 720
left, right, top, bottom = 140, 24, 36, 20
row_h = 20
row_gap = 10
chart_h = len(parts) * (row_h + row_gap) - row_gap if parts else row_h
h = top + chart_h + bottom
chart_w = w - left - right


def color_for(name):
    # стабильный оттенок по названию языка
    hue = int.from_bytes(hashlib.sha1(name.encode("utf-8")).digest()[:2], "big") % 360
    return f"hsl({hue},60%,50%)"


def pct_label(p):
    return f"{p:.0f}%" if p >= 5 else f"{p:.1f}%"


svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
    "<style>"
    ".t{font:12px -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;dominant-baseline:middle;fill:#24292f}"
    ".s{font:11px -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;fill:#6b7280}"
    "</style>",
    f'<rect x="0" y="0" width="{w}" height="{h}" fill="#ffffff" />',
    f'<text x="{left}" y="{top - 16}" class="t">Active languages (last {DAYS} days)</text>',
]

# сетка по 0/25/50/75/100
for i in range(0, 101, 25):
    gx = left + chart_w * i / 100.0
    svg.append(
        f'<line x1="{gx:.1f}" y1="{top}" x2="{gx:.1f}" y2="{h - bottom}" stroke="#e5e7eb" />'
    )
    svg.append(
        f'<text x="{gx:.1f}" y="{top - 4}" class="s" text-anchor="middle">{i}%</text>'
    )

y = top
for name, pct in parts:
    width_px = chart_w * max(0.0, min(100.0, pct)) / 100.0
    bar_y = y + (row_h - 14) / 2
    fill = color_for(name)
    # подпись слева
    svg.append(
        f'<text x="{left - 8}" y="{y + row_h / 2:.1f}" class="t" text-anchor="end">{name}</text>'
    )
    # бар
    svg.append(
        f'<rect x="{left}" y="{bar_y:.1f}" width="{width_px:.1f}" height="14" rx="3" ry="3" fill="{fill}" stroke="#ddd" />'
    )
    # процент — внутри бара, если достаточно места, иначе справа
    label = pct_label(pct)
    if width_px >= 36:
        svg.append(
            f'<text x="{left + width_px - 4:.1f}" y="{y + row_h / 2:.1f}" class="t" text-anchor="end" fill="#fff">{label}</text>'
        )
    else:
        svg.append(
            f'<text x="{left + width_px + 6:.1f}" y="{y + row_h / 2:.1f}" class="t" text-anchor="start">{label}</text>'
        )
    y += row_h + row_gap

svg.append("</svg>")
open("active_langs.svg", "w").write("\n".join(svg))
print("Wrote active_langs.svg")
