"""Theme registry.

One lookup table maps a ``STUB_THEME`` value to a builder.  ``random`` mixes
classic and technical deliberately: a fleet on which every node is an API
portal is itself a pattern, and heterogeneity across nodes matters more than
the plausibility of any single node.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .profile import Profile, resolve
from .rng import SeededRandom, seed_from
from .themes import classic, technical
from .themes.base import Site, ThemeSpec
from .themes.catalog import BY_KEY as TECH_BY_KEY, TECHNICAL_THEMES

CLASSIC_DESCRIPTIONS = {
    "studio": "Independent design studio.",
    "coffee": "Neighbourhood coffee shop.",
    "law": "Small commercial legal practice.",
    "contractor": "Building and renovation contractor.",
}

CLASSIC_LABELS = {
    "studio": "Design Studio",
    "coffee": "Coffee Shop",
    "law": "Law Firm",
    "contractor": "Contractor",
}


def _make_registry() -> Dict[str, ThemeSpec]:
    registry: Dict[str, ThemeSpec] = {}
    for key, label in CLASSIC_LABELS.items():
        registry[key] = ThemeSpec(
            key=key, label=label, kind="classic",
            description=CLASSIC_DESCRIPTIONS[key],
            build=(lambda k: (lambda profile: classic.build(profile, k)))(key),
            variants=["default"],
        )
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

CLASSIC_KEYS = [k for k, s in REGISTRY.items() if s.kind == "classic"]
TECHNICAL_KEYS = [k for k, s in REGISTRY.items() if s.kind == "technical"]
META_THEMES = ["random", "technical", "classic"]


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
    picker = rng.derive("theme-choice")
    if request == "classic":
        return picker.choice(sorted(CLASSIC_KEYS))
    if request == "technical":
        return picker.choice(sorted(TECHNICAL_KEYS))
    if request == "random":
        # Weighted, not uniform: technical themes are the point of this
        # release, but an all-technical fleet is its own signature.
        kind = picker.weighted([("technical", 65), ("classic", 35)])
        pool = TECHNICAL_KEYS if kind == "technical" else CLASSIC_KEYS
        return picker.choice(sorted(pool))
    raise ValueError(
        f"unknown theme {request!r}; known: {', '.join(known_themes())}"
    )


def _tagline(profile_seed: SeededRandom, spec: ThemeSpec) -> str:
    from . import data
    rng = profile_seed.derive("tagline")
    shape = rng.choice(data.TAGLINE_SHAPES)
    noun = TECH_BY_KEY[spec.key].noun if spec.key in TECH_BY_KEY else spec.label
    return shape.format(
        noun=noun,
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
    if spec.kind == "technical":
        profile.description = (
            f"{TECH_BY_KEY[spec.key].description} "
            f"Operated by {profile.brand.company} from {profile.region.city}."
        )
    else:
        profile.description = spec.description
    return spec, profile


def build_site(spec: ThemeSpec, profile: Profile) -> Site:
    site = spec.build(profile)
    profile.pages = [page.url for page in site.pages]
    profile.endpoints = [ep.path for ep in site.endpoints]
    return site
