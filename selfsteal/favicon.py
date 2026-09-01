"""Favicon generation.

The original installer embedded one base64 ``favicon.ico`` shared by every
installation.  A single ``sha256`` of that file clusters an entire fleet in one
scan, which is the strongest correlation the project had.  Both the SVG and the
ICO are therefore derived from the profile, and the ICO is drawn pixel by pixel
rather than copied.
"""

from __future__ import annotations

import struct
from typing import Callable, List, Tuple

from .profile import Profile

SIZE = 32


def _hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _contrast(rgb: Tuple[int, int, int]) -> Tuple[int, int, int]:
    """White or near-black, whichever reads on the given background."""
    luma = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    return (255, 255, 255) if luma < 150 else (23, 23, 26)


# --- glyphs -----------------------------------------------------------------
# Each returns True when pixel (x, y) belongs to the foreground shape.

def _glyph_bars(x: int, y: int) -> bool:
    return 6 <= x <= 25 and (8 <= y <= 12 or 15 <= y <= 19 or 22 <= y <= 26 and x <= 17)


def _glyph_ring(x: int, y: int) -> bool:
    dx, dy = x - 15.5, y - 15.5
    d2 = dx * dx + dy * dy
    return 36 <= d2 <= 100


def _glyph_dot(x: int, y: int) -> bool:
    dx, dy = x - 15.5, y - 15.5
    return dx * dx + dy * dy <= 42


def _glyph_diagonal(x: int, y: int) -> bool:
    return abs((x - y)) <= 3 and 5 <= x <= 26


def _glyph_chevron(x: int, y: int) -> bool:
    return abs(abs(y - 15.5) - (x - 8) * 0.8) <= 2.2 and 8 <= x <= 24


def _glyph_grid(x: int, y: int) -> bool:
    return (8 <= x <= 14 or 18 <= x <= 24) and (8 <= y <= 14 or 18 <= y <= 24)


def _glyph_layers(x: int, y: int) -> bool:
    return 7 <= x <= 24 and (9 <= y <= 12 or 14 <= y <= 17 or 19 <= y <= 22)


def _glyph_corner(x: int, y: int) -> bool:
    return (7 <= x <= 24 and 7 <= y <= 11) or (7 <= x <= 11 and 7 <= y <= 24)


GLYPHS: List[Tuple[str, Callable[[int, int], bool]]] = [
    ("bars", _glyph_bars), ("ring", _glyph_ring), ("dot", _glyph_dot),
    ("diagonal", _glyph_diagonal), ("chevron", _glyph_chevron),
    ("grid", _glyph_grid), ("layers", _glyph_layers), ("corner", _glyph_corner),
]


def _rounded(x: int, y: int, radius: int) -> bool:
    """Rounded-square mask over the full canvas."""
    if radius <= 0:
        return True
    for cx, cy in ((radius, radius), (SIZE - 1 - radius, radius),
                   (radius, SIZE - 1 - radius), (SIZE - 1 - radius, SIZE - 1 - radius)):
        if (x < radius and cx == radius or x > SIZE - 1 - radius and cx != radius) and \
           (y < radius and cy == radius or y > SIZE - 1 - radius and cy != radius):
            dx, dy = x - cx, y - cy
            return dx * dx + dy * dy <= radius * radius
    return True


def build_ico(profile: Profile) -> bytes:
    """A 32x32 32-bit ICO, drawn from the profile."""
    rng = profile.rng.derive("favicon")
    name, glyph = rng.choice(GLYPHS)
    radius = rng.choice([0, 3, 5, 7, 9])
    inverted = rng.chance(30)

    bg = _hex_to_rgb(profile.palette.accent)
    fg = _contrast(bg)
    if inverted:
        bg, fg = fg, bg

    transparent = (0, 0, 0, 0)
    rows: List[bytes] = []
    for y in range(SIZE - 1, -1, -1):          # BMP rows are bottom-up
        row = bytearray()
        for x in range(SIZE):
            if not _rounded(x, y, radius):
                r, g, b, a = transparent
            elif glyph(x, y):
                r, g, b = fg
                a = 255
            else:
                r, g, b = bg
                a = 255
            row += bytes((b, g, r, a))          # BGRA
        rows.append(bytes(row))
    xor_data = b"".join(rows)
    and_mask = b"\x00" * (4 * SIZE)             # fully opaque

    dib = struct.pack(
        "<IiiHHIIiiII",
        40, SIZE, SIZE * 2, 1, 32, 0, len(xor_data) + len(and_mask), 0, 0, 0, 0,
    )
    image = dib + xor_data + and_mask
    header = struct.pack("<HHH", 0, 1, 1)
    entry = struct.pack("<BBBBHHII", SIZE, SIZE, 0, 0, 1, 32, len(image), 22)
    return header + entry + image


def build_svg(profile: Profile) -> str:
    """Scalable mark. Monogram or geometry, chosen per install."""
    rng = profile.rng.derive("favicon-svg")
    accent = profile.palette.accent
    fg = "#ffffff" if _contrast(_hex_to_rgb(accent)) == (255, 255, 255) else "#17171a"
    radius = rng.choice([0, 6, 10, 14, 32])
    style = rng.weighted([("monogram", 55), ("geometry", 45)])

    plate = f'<rect width="64" height="64" rx="{radius}" fill="{accent}"/>'
    if style == "monogram":
        font = rng.choice([
            "system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif",
            "ui-monospace,Menlo,Consolas,monospace",
            "Georgia,'Times New Roman',serif",
        ])
        text = profile.brand.monogram
        size = 34 if len(text) == 1 else 25
        body = (
            f'<text x="32" y="{44 if len(text) == 1 else 41}" font-family="{font}" '
            f'font-size="{size}" font-weight="600" text-anchor="middle" '
            f'fill="{fg}">{text}</text>'
        )
    else:
        shape = rng.choice(["ring", "bars", "chevron", "grid"])
        if shape == "ring":
            body = (f'<circle cx="32" cy="32" r="15" fill="none" stroke="{fg}" '
                    f'stroke-width="6"/>')
        elif shape == "bars":
            body = "".join(
                f'<rect x="16" y="{y}" width="32" height="6" rx="1" fill="{fg}"/>'
                for y in (18, 29, 40)
            )
        elif shape == "chevron":
            body = (f'<path d="M22 16l16 16-16 16" stroke="{fg}" stroke-width="7" '
                    'fill="none" stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            body = "".join(
                f'<rect x="{x}" y="{y}" width="12" height="12" rx="2" fill="{fg}"/>'
                for x in (17, 35) for y in (17, 35)
            )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" '
        f'role="img" aria-label="{profile.brand.name}">{plate}{body}</svg>'
    )
