"""Brand generation.

The original installer drew from four hard-coded pools of eight names, which
gives 32 possible brands across an entire fleet.  For a 30-node deployment
that is a near-certain collision by the birthday bound, and a collision is a
direct correlation between two nodes.  Composition instead of enumeration puts
the name space in the tens of thousands.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import data
from .rng import SeededRandom


@dataclass(frozen=True)
class Brand:
    name: str          # "FrameLayer"
    company: str       # "FrameLayer Technologies BV"
    product: str       # "FrameLayer Media API"
    monogram: str      # "FL" or "F"
    slug: str          # "framelayer"


def _compose(rng: SeededRandom) -> tuple:
    """Return ``(name, monogram_len_hint)``."""
    shape = rng.weighted([
        ("fused", 40),      # FrameLayer
        ("standalone", 25),  # Marlowe
        ("spaced", 20),     # Frame Layer
        ("clipped", 15),    # Framely / Layerly
    ])
    if shape == "fused":
        return rng.choice(data.TECH_PREFIX) + rng.choice(data.TECH_SUFFIX).lower().capitalize(), 2
    if shape == "standalone":
        return rng.choice(data.TECH_STANDALONE), 1
    if shape == "spaced":
        return f"{rng.choice(data.TECH_PREFIX)} {rng.choice(data.TECH_SUFFIX)}", 2
    # Only stems ending in a consonant take a clipped suffix; "Aperture"+"ede"
    # is the kind of name a human would never register.
    stem = rng.choice([s for s in data.TECH_PREFIX if s[-1] not in "aeiou"])
    return stem + rng.choice(["ly", "ia", "io", "ora", "ix", "ux"]), 1


def _monogram(name: str, hint: int) -> str:
    words = [w for w in name.replace("-", " ").split() if w]
    if len(words) > 1:
        return "".join(w[0] for w in words[:2]).upper()
    if hint >= 2:
        # Split a fused CamelCase name back into its two capitals.
        caps = [c for c in name if c.isupper()]
        if len(caps) >= 2:
            return "".join(caps[:2])
    return name[0].upper()


def build_brand(rng: SeededRandom, product_label: str) -> Brand:
    """Create a coherent brand identity.

    ``product_label`` is the theme's human label ("Media API"), so the product
    name always agrees with what the site actually claims to be.
    """
    stream = rng.derive("brand")
    name, hint = _compose(stream)

    if stream.chance(55):
        company = f"{name} {stream.choice(data.COMPANY_SUFFIX)}"
    else:
        company = name
    company += stream.choice(data.LEGAL_SUFFIX)

    if stream.chance(70):
        product = f"{name} {product_label}"
    else:
        product = product_label

    slug = "".join(ch for ch in name.lower() if ch.isalnum())
    return Brand(
        name=name,
        company=company.strip(),
        product=product,
        monogram=_monogram(name, hint),
        slug=slug,
    )
