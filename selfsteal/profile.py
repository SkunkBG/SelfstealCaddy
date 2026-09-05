"""The installation profile.

Everything the generators need is resolved once, here, from a single seed.
Nothing downstream may consult the clock, the hostname, the network or
``os.urandom``: if it did, two runs on the same node would produce two
different sites, and a re-run would change the node's public identity.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import data
from .branding import Brand, build_brand
from .render import DocumentStyle, NameMangler
from .rng import SeededRandom, seed_from

SCHEMA_VERSION = 2


@dataclass(frozen=True)
class Palette:
    bg: str
    surface: str
    ink: str
    muted: str
    border: str
    accent: str
    dark: bool


@dataclass(frozen=True)
class Typography:
    sans: str
    mono: str
    serif: str
    radius: str
    scale: float
    heading: str  # "sans" | "serif" | "mono"


@dataclass(frozen=True)
class Region:
    city: str
    zone: str
    pop: str
    country: str


@dataclass
class Profile:
    """Fully resolved, deterministic description of one generated service."""

    schema: int
    seed: str
    domain: str
    theme: str
    theme_label: str
    kind: str            # "technical" | "classic"
    variant: str
    variant_label: str

    brand: Brand
    description: str
    tagline: str

    api_version: str
    region: Region
    city: str
    year: int
    release: str
    build_id: str
    uptime: str

    palette: Palette
    typography: Typography

    # Runtime-only helpers, excluded from the serialised profile.
    rng: SeededRandom = field(repr=False, compare=False, default=None)
    css: NameMangler = field(repr=False, compare=False, default=None)
    doc: DocumentStyle = field(repr=False, compare=False, default=None)

    pages: List[str] = field(default_factory=list)
    endpoints: List[str] = field(default_factory=list)

    # ---- derived -------------------------------------------------------

    @property
    def contact_email(self) -> str:
        return f"support@{self.domain}"

    @property
    def security_email(self) -> str:
        return f"security@{self.domain}"

    @property
    def api_base(self) -> str:
        return f"https://{self.domain}/api/{self.api_version}"

    @property
    def seed_id(self) -> str:
        """Non-reversible fingerprint of the seed.

        Enough to confirm that two nodes were built from different seeds, or
        that a re-run reused the same one, without printing or persisting the
        secret that makes the node's appearance unpredictable.
        """
        return hashlib.sha256(self.seed.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "schema": self.schema,
            "seed": self.seed,
            "domain": self.domain,
            "theme": self.theme,
            "theme_label": self.theme_label,
            "kind": self.kind,
            "variant": self.variant,
            "variant_label": self.variant_label,
            "brand": asdict(self.brand),
            "description": self.description,
            "tagline": self.tagline,
            "api_version": self.api_version,
            "region": asdict(self.region),
            "city": self.city,
            "year": self.year,
            "release": self.release,
            "build_id": self.build_id,
            "uptime": self.uptime,
            "palette": asdict(self.palette),
            "typography": asdict(self.typography),
            "pages": sorted(self.pages),
            "endpoints": sorted(self.endpoints),
        }
        return payload

    def to_public_dict(self) -> Dict[str, Any]:
        """``to_dict`` without the seed, for anything written to the webroot."""
        payload = self.to_dict()
        payload.pop("seed", None)
        payload["seed_id"] = self.seed_id
        return payload

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=False) + "\n"

    def to_public_json(self) -> str:
        return json.dumps(self.to_public_dict(), indent=2, sort_keys=False) + "\n"


def _pick_release(rng: SeededRandom, year: int) -> Tuple[str, str, str]:
    """A plausible release date, build id and uptime figure.

    Derived from the seed rather than ``date.today()`` so the generated site
    does not carry the installation timestamp, and so re-running the installer
    a month later does not silently rewrite every page.
    """
    stream = rng.derive("release")
    day = _dt.date(year, 1, 1) + _dt.timedelta(days=stream.between(0, 330))
    build = "".join(stream.choice(list("0123456789abcdef")) for _ in range(7))
    uptime = f"{stream.between(99, 99)}.{stream.between(90, 99)}%"
    return day.isoformat(), build, uptime


def resolve(
    domain: str,
    theme_key: str,
    theme_label: str,
    kind: str,
    variant_key: str,
    variant_label: str,
    *,
    seed: Optional[str] = None,
    description: str = "",
    tagline: str = "",
) -> Profile:
    """Build a Profile.  Pure function of its arguments."""
    resolved_seed = seed or seed_from(domain, theme_key)
    rng = SeededRandom(resolved_seed)

    brand = build_brand(rng, theme_label)

    ident = rng.derive("identity")
    city, zone, pop, country = ident.choice(data.REGIONS)
    region = Region(city=city, zone=zone, pop=pop, country=country)
    classic_city = ident.choice(data.CLASSIC_CITIES)
    year = ident.between(2011, 2021)
    api_version = ident.weighted([("v1", 70), ("v2", 25), ("v3", 5)])
    release, build_id, uptime = _pick_release(rng, min(year + 12, 2025))

    look = rng.derive("look")
    bg, surface, ink, muted, border, accent = look.choice(data.TECH_PALETTES)
    palette = Palette(
        bg=bg, surface=surface, ink=ink, muted=muted, border=border,
        accent=accent, dark=int(bg.lstrip("#")[:2], 16) < 0x80,
    )
    typography = Typography(
        sans=look.choice(data.SANS_STACKS),
        mono=look.choice(data.MONO_STACKS),
        serif=look.choice(data.SERIF_STACKS),
        radius=look.choice(["0", "2px", "3px", "4px", "6px", "8px"]),
        scale=look.choice([0.94, 0.97, 1.0, 1.03, 1.06]),
        heading=look.weighted([("sans", 70), ("serif", 20), ("mono", 10)]),
    )

    return Profile(
        schema=SCHEMA_VERSION,
        seed=resolved_seed,
        domain=domain,
        theme=theme_key,
        theme_label=theme_label,
        kind=kind,
        variant=variant_key,
        variant_label=variant_label,
        brand=brand,
        description=description,
        tagline=tagline,
        api_version=api_version,
        region=region,
        city=classic_city,
        year=year,
        release=release,
        build_id=build_id,
        uptime=uptime,
        palette=palette,
        typography=typography,
        rng=rng,
        css=NameMangler(rng),
        doc=DocumentStyle(rng),
    )
