"""Theme registry.

One lookup table maps a ``STUB_THEME`` value to a builder.  Every theme is a
technical service with a JSON API; the ordinary-website themes that 2.0 shipped
(studio, coffee, law, contractor) were removed, and asking for one fails with a
message that says so rather than silently building something else.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .profile import Profile, resolve
from .rng import SeededRandom, seed_from
from .themes import technical
from .themes.base import Site, ThemeSpec
from .themes.catalog import BY_KEY as TECH_BY_KEY, TECHNICAL_THEMES

REMOVED_THEMES = frozenset({"studio", "coffee", "law", "contractor", "classic"})


def _make_registry() -> Dict[str, ThemeSpec]:
    registry: Dict[str, ThemeSpec] = {}
    for theme in TECHNICAL_THEMES:
        registry[theme.key] = ThemeSpec(
            key=theme.key, label=theme.label, kind="technical",
            description=theme.description,
            build=(lambda t: (lambda profile: technical.build(profile, t)))(theme),
            variants=list(technical.VARIANTS),
            aliases=list(theme.aliases),
        )
    return registry


REGISTRY: Dict[str, ThemeSpec] = _make_registry()

TECHNICAL_KEYS = sorted(REGISTRY)
META_THEMES = ["random", "technical"]


def known_themes() -> List[str]:
    return sorted(REGISTRY) + META_THEMES


def choose_theme(request: str, rng: SeededRandom) -> str:
    """Resolve a possibly-meta theme name to a concrete key."""
    request = (request or "random").strip().lower()
    if request in REGISTRY:
        return request
    for key, spec in REGISTRY.items():
        if request in spec.aliases:
            return key
    if request in REMOVED_THEMES:
        raise ValueError(
            f"theme {request!r} was removed: only API service themes remain; "
            f"known: {', '.join(known_themes())}"
        )
    picker = rng.derive("theme-choice")
    if request == "technical":
        return picker.choice(TECHNICAL_KEYS)
    if request == "random":
        # ``random`` used to roll technical-or-ordinary first and pick a theme
        # second. The first roll is kept and discarded so a node installed with
        # ``random`` that landed on a technical theme keeps that same theme.
        picker.below(100)
        return picker.choice(TECHNICAL_KEYS)
    raise ValueError(
        f"unknown theme {request!r}; known: {', '.join(known_themes())}"
    )


def _tagline(profile_seed: SeededRandom, spec: ThemeSpec) -> str:
    from . import data
    rng = profile_seed.derive("tagline")
    shape = rng.choice(data.TAGLINE_SHAPES)
    return shape.format(
        noun=TECH_BY_KEY[spec.key].noun,
        adjective=rng.choice(["predictable", "boring", "well-documented",
                              "straightforward", "dependable"]),
        audience=rng.choice(data.AUDIENCES),
    )


def prepare(domain: str, theme_request: str,
            seed: Optional[str] = None) -> Tuple[ThemeSpec, Profile]:
    """Deterministically resolve theme, variant and profile for an install."""
    root_seed = seed or seed_from(domain)
    root_rng = SeededRandom(root_seed)

    key = choose_theme(theme_request, root_rng)
    spec = REGISTRY[key]
    variant = spec.pick_variant(root_rng.derive(f"variant:{key}"))

    profile = resolve(
        domain=domain,
        theme_key=spec.key,
        theme_label=spec.label,
        kind=spec.kind,
        variant_key=variant,
        variant_label=variant.replace("-", " ").title(),
        seed=seed_from(root_seed, spec.key, variant),
        description=spec.description,
    )
    profile.tagline = _tagline(profile.rng, spec)
    profile.description = (
        f"{TECH_BY_KEY[spec.key].description} "
        f"Operated by {profile.brand.company} from {profile.region.city}."
    )
    return spec, profile


def build_site(spec: ThemeSpec, profile: Profile) -> Site:
    site = spec.build(profile)
    profile.pages = [page.url for page in site.pages]
    profile.endpoints = [ep.path for ep in site.endpoints]
    return site
