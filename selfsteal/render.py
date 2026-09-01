"""HTML rendering primitives.

The single largest correlation risk in the original project was not the visible
content but the invariant markup: every theme on every node shared one
``emit_head()`` with the same tags in the same order, the same class names and
the same byte-identical favicon.  Hashing any one of those clusters an entire
fleet in a single pass.

Everything in this module therefore varies per installation: class names, CSS
custom-property names, head-tag ordering, indentation, and whether the document
is pretty-printed at all.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional

from .rng import SeededRandom

_WORD_PARTS = [
    "wrap", "shell", "inner", "bar", "row", "col", "box", "unit", "block",
    "panel", "band", "slab", "tile", "item", "node", "line", "stack", "grid",
    "head", "foot", "main", "side", "list", "cell", "deck", "pane",
]


def esc(value: object) -> str:
    """Escape for HTML text and double-quoted attribute contexts."""
    return html.escape(str(value), quote=True)


class NameMangler:
    """Stable per-installation mapping from semantic key to CSS class name.

    Lazily assigned, so an unused key costs nothing and adding a key to one
    template does not renumber the classes of another.
    """

    def __init__(self, rng: SeededRandom) -> None:
        self._rng = rng.derive("classnames")
        self._style = self._rng.weighted([
            ("word", 35),      # .panel-row
            ("prefixed", 30),  # .sx-panel
            ("terse", 20),     # .a7
            ("semantic", 15),  # .panel  (unmangled, like a hand-written site)
        ])
        self._prefix = "".join(
            self._rng.choice(list("abcdefghijklmnopqrstuvwxyz")) for _ in range(2)
        )
        self._map: Dict[str, str] = {}
        self._used: set = set()

    def __call__(self, key: str) -> str:
        if key not in self._map:
            self._map[key] = self._mint(key)
        return self._map[key]

    def _mint(self, key: str) -> str:
        for _ in range(64):
            candidate = self._candidate(key)
            if candidate not in self._used:
                self._used.add(candidate)
                return candidate
        candidate = f"{self._prefix}{len(self._used)}"
        self._used.add(candidate)
        return candidate

    def _candidate(self, key: str) -> str:
        if self._style == "semantic":
            return key
        if self._style == "word":
            return f"{self._rng.choice(_WORD_PARTS)}-{self._rng.choice(_WORD_PARTS)}"
        if self._style == "prefixed":
            return f"{self._prefix}-{self._rng.choice(_WORD_PARTS)}"
        letters = "abcdefghijklmnopqrstuvwxyz"
        return self._rng.choice(list(letters)) + str(self._rng.between(0, 99))

    def attr(self, *keys: str) -> str:
        """Render ``class="..."`` for one or more semantic keys."""
        return 'class="' + " ".join(self(k) for k in keys) + '"'


@dataclass
class HeadMeta:
    title: str
    description: str
    canonical: str
    og_title: Optional[str] = None
    og_type: str = "website"
    extra: List[str] = field(default_factory=list)


class DocumentStyle:
    """Per-installation formatting decisions for emitted HTML."""

    def __init__(self, rng: SeededRandom) -> None:
        stream = rng.derive("docstyle")
        self.minify = stream.chance(35)
        self.indent = "" if self.minify else " " * stream.choice([2, 4])
        self.lang = "en"
        self.self_closing = stream.chance(20)  # <meta ... /> vs <meta ...>
        self.head_order = stream.shuffled([
            "description", "canonical", "stylesheet", "icons", "og", "theme",
        ])
        self.include_og = stream.chance(75)
        self.include_theme_color = stream.chance(60)
        self.include_generator = False  # never: it would announce the generator
        self.include_robots_meta = stream.chance(25)
        self.doctype_upper = stream.chance(70)

    def tag_close(self) -> str:
        return " />" if self.self_closing else ">"


def build_document(
    style: DocumentStyle,
    meta: HeadMeta,
    body: str,
    *,
    domain: str,
    theme_color: str,
    stylesheet: str = "/style.css",
) -> str:
    """Assemble a complete HTML document with per-install head ordering."""
    close = style.tag_close()
    parts: List[str] = []
    parts.append("<!DOCTYPE html>" if style.doctype_upper else "<!doctype html>")
    parts.append(f'<html lang="{style.lang}">')
    parts.append("<head>")
    # charset and viewport stay first: any other order is a real-world bug,
    # and looking buggy is not the kind of variation we want.
    parts.append(f'<meta charset="utf-8"{close}')
    parts.append(
        f'<meta name="viewport" content="width=device-width, initial-scale=1"{close}'
    )
    parts.append(f"<title>{esc(meta.title)}</title>")

    canonical = f"https://{domain}/{meta.canonical.lstrip('/')}"
    blocks = {
        "description": [
            f'<meta name="description" content="{esc(meta.description)}"{close}'
        ] if meta.description else [],
        "canonical": [f'<link rel="canonical" href="{esc(canonical)}"{close}'],
        "stylesheet": [f'<link rel="stylesheet" href="{stylesheet}"{close}'],
        "icons": [
            f'<link rel="icon" href="/favicon.svg" type="image/svg+xml"{close}',
            f'<link rel="icon" href="/favicon.ico" sizes="32x32"{close}',
        ],
        "og": [
            f'<meta property="og:type" content="{meta.og_type}"{close}',
            f'<meta property="og:title" content="{esc(meta.og_title or meta.title)}"{close}',
            f'<meta property="og:url" content="{esc(canonical)}"{close}',
        ] if style.include_og else [],
        "theme": [
            f'<meta name="theme-color" content="{theme_color}"{close}'
        ] if style.include_theme_color else [],
    }
    for key in style.head_order:
        parts.extend(blocks.get(key, []))
    if style.include_robots_meta:
        parts.append(f'<meta name="robots" content="index, follow"{close}')
    parts.extend(meta.extra)
    parts.append("</head>")
    parts.append("<body>")
    parts.append(body.strip())
    parts.append("</body>")
    parts.append("</html>")

    if style.minify:
        return "".join(parts) + "\n"
    return "\n".join(parts) + "\n"


def code_block(mangler: NameMangler, lines: Iterable[str]) -> str:
    text = "\n".join(esc(line) for line in lines)
    return f'<pre {mangler.attr("code")}><code>{text}</code></pre>'


def table(mangler: NameMangler, headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    return (
        f'<table {mangler.attr("table")}>'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    )
