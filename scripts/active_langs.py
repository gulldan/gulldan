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


def parse_linguist_yaml(payload):
    # легкий парсер languages.yml из github/linguist — вынимаем extensions/filenames без внешних зависимостей
    ext_map, filename_map = {}, {}
    current_lang = None
    current_section = None

    def add_value(section, raw_value):
        value = raw_value.split("#", 1)[0].strip().strip('"').strip("'")
        if not value:
            return
        if section == "extensions":
            ext_map[value.lower()] = current_lang
        elif section == "filenames":
            filename_map[value.lower()] = current_lang

    for raw_line in payload.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" "):
            current_lang = stripped.split(":", 1)[0]
            current_section = None
            continue
        if ":" in stripped and not stripped.startswith("-"):
            key, after = stripped.split(":", 1)
            key = key.strip()
            after = after.strip()
            if key in ("extensions", "filenames"):
                current_section = key
                if after.startswith("[") and after.endswith("]"):
                    for entry in after[1:-1].split(","):
                        add_value(key, entry)
                    current_section = None
            else:
                current_section = None
            continue
        if stripped.startswith("-") and current_lang and current_section:
            add_value(current_section, stripped[1:].strip())
    return ext_map, filename_map


def load_linguist_maps():
    url = "https://raw.githubusercontent.com/github/linguist/master/lib/linguist/languages.yml"
    try:
        resp = requests.get(url, headers=HEAD, timeout=10)
        resp.raise_for_status()
    except Exception:
        return {}, {}
    return parse_linguist_yaml(resp.text)


LINGUIST_EXT_MAP, LINGUIST_FILENAME_MAP = load_linguist_maps()

# запасные значения для популярных языков на случай, если загрузка linguist недоступна
FALLBACK_SPECIAL_NAMES = {
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
    "build": "Starlark",
    "build.bazel": "Starlark",
    "workspace": "Starlark",
    "workspace.bazel": "Starlark",
    "tiltfile": "Starlark",
    "justfile": "Just",
    "meson.build": "Meson",
    "meson_options.txt": "Meson",
    "go.mod": "Go",
    "go.sum": "Go",
    "go.work": "Go",
}

FALLBACK_EXTENSION_MAP = {
    ".d.ts": "TypeScript",
    ".cts": "TypeScript",
    ".mts": "TypeScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".cjs": "JavaScript",
    ".mjs": "JavaScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".coffee": "CoffeeScript",
    ".litcoffee": "CoffeeScript",
    ".coffee.md": "CoffeeScript",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".astro": "Astro",
    ".pug": "Pug",
    ".jade": "Pug",
    ".ejs": "EJS",
    ".hbs": "Handlebars",
    ".handlebars": "Handlebars",
    ".mustache": "Mustache",
    ".twig": "Twig",
    ".njk": "Nunjucks",
    ".liquid": "Liquid",
    ".slim": "Slim",
    ".haml": "Haml",
    ".erb": "ERB",
    ".mdx": "MDX",
    ".md": "Markdown",
    ".markdown": "Markdown",
    ".rst": "reStructuredText",
    ".adoc": "AsciiDoc",
    ".asciidoc": "AsciiDoc",
    ".rmd": "R Markdown",
    ".ipynb": "Python",
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Python",
    ".pxd": "Python",
    ".pxi": "Python",
    ".rpy": "Python",
    ".c": "C",
    ".h": "C",
    ".c++": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".cc": "C++",
    ".cp": "C++",
    ".hpp": "C++",
    ".hxx": "C++",
    ".hh": "C++",
    ".h++": "C++",
    ".inl": "C++",
    ".ipp": "C++",
    ".go": "Go",
    ".rs": "Rust",
    ".d": "D",
    ".zig": "Zig",
    ".nim": "Nim",
    ".nims": "Nim",
    ".cr": "Crystal",
    ".java": "Java",
    ".groovy": "Groovy",
    ".gvy": "Groovy",
    ".gsh": "Groovy",
    ".gy": "Groovy",
    ".php": "PHP",
    ".phtml": "PHP",
    ".php3": "PHP",
    ".php4": "PHP",
    ".php5": "PHP",
    ".php7": "PHP",
    ".phps": "PHP",
    ".phpt": "PHP",
    ".pht": "PHP",
    ".ctp": "PHP",
    ".rb": "Ruby",
    ".gemspec": "Ruby",
    ".rake": "Ruby",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".cs": "C#",
    ".fs": "F#",
    ".fsi": "F#",
    ".fsx": "F#",
    ".vb": "Visual Basic",
    ".bas": "Visual Basic",
    ".vbs": "VBScript",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".dart": "Dart",
    ".clj": "Clojure",
    ".cljs": "Clojure",
    ".cljc": "Clojure",
    ".edn": "Clojure",
    ".lisp": "Common Lisp",
    ".lsp": "Common Lisp",
    ".cl": "Common Lisp",
    ".el": "Emacs Lisp",
    ".scm": "Scheme",
    ".ss": "Scheme",
    ".rkt": "Racket",
    ".ml": "OCaml",
    ".mli": "OCaml",
    ".mll": "OCaml",
    ".mly": "OCaml",
    ".re": "ReasonML",
    ".rei": "ReasonML",
    ".hs": "Haskell",
    ".lhs": "Haskell",
    ".purs": "PureScript",
    ".elm": "Elm",
    ".hx": "Haxe",
    ".hxml": "Haxe",
    ".erl": "Erlang",
    ".hrl": "Erlang",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".lua": "Lua",
    ".gd": "GDScript",
    ".r": "R",
    ".jl": "Julia",
    ".sql": "SQL",
    ".psql": "SQL",
    ".pgsql": "SQL",
    ".proto": "Protocol Buffers",
    ".thrift": "Thrift",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".sol": "Solidity",
    ".prisma": "Prisma",
    ".hcl": "HCL",
    ".tf": "Terraform",
    ".tfvars": "Terraform",
    ".nomad": "HCL",
    ".cmake": "CMake",
    ".mk": "Makefile",
    ".ninja": "Ninja",
    ".gradle": "Gradle",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".styl": "Stylus",
    ".pcss": "CSS",
    ".postcss": "CSS",
    ".css": "CSS",
    ".html": "HTML",
    ".htm": "HTML",
    ".xhtml": "HTML",
    ".xml": "XML",
    ".xsd": "XML",
    ".xsl": "XSLT",
    ".xslt": "XSLT",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "INI",
    ".properties": "Properties",
    ".json": "JSON",
    ".json5": "JSON5",
    ".csv": "CSV",
    ".tsv": "TSV",
    ".tex": "LaTeX",
    ".sty": "LaTeX",
    ".cls": "LaTeX",
    ".bib": "BibTeX",
    ".pas": "Pascal",
    ".pp": "Pascal",
    ".dpr": "Pascal",
    ".ada": "Ada",
    ".adb": "Ada",
    ".ads": "Ada",
    ".asm": "Assembly",
    ".s": "Assembly",
    ".nasm": "Assembly",
    ".wat": "WebAssembly",
    ".wasm": "WebAssembly",
    ".v": "Verilog",
    ".vh": "Verilog",
    ".sv": "SystemVerilog",
    ".svh": "SystemVerilog",
    ".vhd": "VHDL",
    ".vhdl": "VHDL",
    ".mof": "MOF",
    ".bat": "Batch",
    ".cmd": "Batch",
    ".ps1": "PowerShell",
    ".psm1": "PowerShell",
    ".psd1": "PowerShell",
    ".fish": "Shell",
    ".zsh": "Shell",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ksh": "Shell",
    ".bats": "Shell",
    ".awk": "Awk",
    ".sed": "Sed",
    ".tcl": "Tcl",
    ".tk": "Tcl",
    ".robot": "Robot Framework",
    ".feature": "Gherkin",
    ".bzl": "Starlark",
    ".bazel": "Starlark",
    ".nix": "Nix",
    ".gradle.kts": "Kotlin",
    ".podspec": "Ruby",
}

SPECIAL_NAMES = {}
SPECIAL_NAMES.update(LINGUIST_FILENAME_MAP)
SPECIAL_NAMES.update(FALLBACK_SPECIAL_NAMES)

EXTENSION_MAP = {}
EXTENSION_MAP.update(LINGUIST_EXT_MAP)
EXTENSION_MAP.update(FALLBACK_EXTENSION_MAP)
EXT_MATCH_ORDER = sorted(EXTENSION_MAP, key=len, reverse=True)


def ext2lang(path):
    p = path.lower()
    base = os.path.basename(p)
    if base in SPECIAL_NAMES:
        return SPECIAL_NAMES[base]
    if base.startswith("dockerfile"):
        return "Docker"
    if base.endswith(".gradle") or base.endswith(".gradle.kts"):
        return "Gradle"
    for ext in EXT_MATCH_ORDER:
        if p.endswith(ext):
            return EXTENSION_MAP[ext]
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
