"""Theme abstractions shared by classic and technical themes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from ..profile import Profile
from ..rng import SeededRandom


@dataclass
class Param:
    name: str
    kind: str
    required: bool
    description: str


@dataclass
class Endpoint:
    """One JSON endpoint.

    ``path`` is the public URL.  ``payload`` is the exact object served; it is
    written to disk as a file, never computed at request time, so the running
    node has no application runtime at all.
    """

    path: str
    summary: str
    payload: dict
    params: List[Param] = field(default_factory=list)
    cache: str = "public, max-age=60"
    doc_slug: str = ""

    @property
    def label(self) -> str:
        return self.path


@dataclass
class Page:
    """One HTML page."""

    url: str            # public URL, e.g. "/docs"
    file: str           # path under webroot, e.g. "docs/index.html"
    title: str
    html: str
    in_sitemap: bool = True
    changefreq: str = "monthly"
    priority: str = "0.5"


@dataclass
class Site:
    """Everything one installation serves."""

    profile: Profile
    pages: List[Page] = field(default_factory=list)
    endpoints: List[Endpoint] = field(default_factory=list)
    files: Dict[str, str] = field(default_factory=dict)   # extra text files
    binaries: Dict[str, bytes] = field(default_factory=dict)
    health_paths: List[str] = field(default_factory=list)

    def add_page(self, page: Page) -> None:
        self.pages.append(page)

    def add_endpoint(self, endpoint: Endpoint) -> None:
        self.endpoints.append(endpoint)

    @property
    def api_paths(self) -> List[str]:
        return [e.path for e in self.endpoints]


@dataclass
class ThemeSpec:
    """Registry entry.

    ``build`` receives a Profile and returns a fully populated Site.  Adding a
    theme means adding one ThemeSpec — no installer, Caddyfile or validator
    change is required, which is the whole point of the registry.
    """

    key: str
    label: str
    kind: str                      # "technical" | "classic"
    description: str
    build: Callable[[Profile], Site]
    variants: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)

    def pick_variant(self, rng: SeededRandom) -> str:
        if not self.variants:
            return "default"
        return rng.derive("variant").choice(self.variants)


def slugify(value: str) -> str:
    out = []
    for ch in value.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")
