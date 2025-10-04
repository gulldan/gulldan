#!/usr/bin/env python3
import collections
import os
from datetime import datetime, timedelta, timezone

import requests

TOKEN = os.environ["GITHUB_TOKEN"]
USER = os.environ.get("G_USER", "gulldan")
DAYS = int(os.environ.get("DAYS", "30"))

HEAD = {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"}
since = (datetime.now(timezone.utc) - timedelta(days=DAYS)).isoformat().replace("+00:00", "Z")

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
parts = [(k, v / total * 100.0) for k, v in lang_map.most_common()]

# Готовим простой SVG бар
w, h, x, y = 720, 120, 20, 40
bar_w = (w - 2 * x) / max(1, len(parts))
svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">',
    "<style>.t{font:12px sans-serif;dominant-baseline:middle}</style>",
    f'<text x="{x}" y="20" class="t">Active languages (last {DAYS} days)</text>',
]
cx = x
for name, pct in parts:
    bh = int(pct / 100.0 * (h - y - 20))
    svg.append(
        f'<rect x="{cx:.1f}" y="{h - 20 - bh}" width="{bar_w - 6:.1f}" height="{bh}" rx="3" ry="3" />'
    )
    svg.append(
        f'<text x="{cx + (bar_w - 6) / 2:.1f}" y="{h - 10}" class="t" text-anchor="middle">{name} {pct:.0f}%</text>'
    )
    cx += bar_w
svg.append("</svg>")
open("active_langs.svg", "w").write("\n".join(svg))
print("Wrote active_langs.svg")
