"""Stylesheet generation.

The original project shipped one static stylesheet per theme, so every node
running that theme served a byte-identical ``/style.css`` — a single ETag or
content hash clustered the whole fleet.  Here the sheet is assembled from the
profile: mangled class names, a per-install custom-property prefix, varying
spacing scale, radius, font stacks and rule ordering.
"""

from __future__ import annotations

from typing import List

from .profile import Profile


def _heading_font(profile: Profile) -> str:
    return {
        "sans": "var(--%s-sans)",
        "serif": "var(--%s-serif)",
        "mono": "var(--%s-mono)",
    }[profile.typography.heading]


def build_stylesheet(profile: Profile) -> str:
    rng = profile.rng.derive("css")
    c = profile.css
    p = profile.palette
    t = profile.typography
    prefix = "".join(rng.choice(list("abcdefghijklmnopqrstuvwxyz")) for _ in range(2))

    def var(name: str) -> str:
        return f"--{prefix}-{name}"

    scale = t.scale
    gutter = round(1.4 * scale, 2)
    section_pad = round(rng.choice([2.6, 3.0, 3.4, 3.8]) * scale, 2)
    maxw = rng.choice([980, 1040, 1080, 1140, 1200])
    heading_font = _heading_font(profile) % prefix

    rules: List[str] = []

    rules.append(
        f":root{{{var('bg')}:{p.bg};{var('surface')}:{p.surface};"
        f"{var('ink')}:{p.ink};{var('muted')}:{p.muted};{var('line')}:{p.border};"
        f"{var('accent')}:{p.accent};{var('radius')}:{t.radius};"
        f"{var('max')}:{maxw}px;{var('sans')}:{t.sans};{var('mono')}:{t.mono};"
        f"{var('serif')}:{t.serif}}}"
    )
    rules.append("*,*::before,*::after{box-sizing:border-box}")
    rules.append("body,h1,h2,h3,h4,p,ul,ol,dl,dd,figure{margin:0;padding:0}")
    rules.append(
        f"body{{font-family:var({var('sans')});background:var({var('bg')});"
        f"color:var({var('ink')});line-height:{round(1.5 + 0.06 * scale, 2)};"
        "-webkit-font-smoothing:antialiased;font-size:"
        f"{round(15.5 * scale, 1)}px}}"
    )
    rules.append(f"a{{color:var({var('accent')});text-decoration:none}}")
    rules.append("a:hover{text-decoration:underline}")
    rules.append("ul,ol{list-style:none}")

    rules.append(
        f".{c('wrap')}{{max-width:var({var('max')});margin:0 auto;"
        f"padding:0 {gutter}rem}}"
    )
    rules.append(
        f".{c('header')}{{border-bottom:1px solid var({var('line')});"
        f"padding:{round(0.9 * scale, 2)}rem 0;"
        f"background:var({var('bg')})}}"
    )
    rules.append(
        f".{c('bar')}{{display:flex;align-items:center;justify-content:space-between;"
        f"gap:{gutter}rem;flex-wrap:wrap}}"
    )
    rules.append(
        f".{c('brand')}{{font-family:{heading_font};font-weight:600;"
        f"font-size:{round(1.05 * scale, 2)}rem;color:var({var('ink')});"
        "display:inline-flex;align-items:center;gap:.5rem;letter-spacing:-.01em}"
    )
    rules.append(f".{c('brand')} svg{{width:20px;height:20px;flex:none}}")
    rules.append(
        f".{c('nav')} ul{{display:flex;gap:{round(1.3 * scale, 2)}rem;flex-wrap:wrap}}"
    )
    rules.append(
        f".{c('nav')} a{{color:var({var('muted')});font-size:.88rem}}"
        f".{c('nav')} a:hover{{color:var({var('ink')});text-decoration:none}}"
    )

    rules.append(f".{c('section')}{{padding:{section_pad}rem 0}}")
    rules.append(
        f".{c('lede')}{{padding:{round(section_pad * 1.1, 2)}rem 0 {section_pad}rem;"
        f"border-bottom:1px solid var({var('line')})}}"
    )
    rules.append(
        f".{c('h1')}{{font-family:{heading_font};font-weight:600;"
        f"font-size:clamp(1.7rem,3.6vw,{round(2.3 * scale, 2)}rem);"
        "line-height:1.15;letter-spacing:-.02em;max-width:22ch}"
    )
    rules.append(
        f".{c('h2')}{{font-family:{heading_font};font-weight:600;"
        f"font-size:{round(1.18 * scale, 2)}rem;letter-spacing:-.01em;"
        f"margin-bottom:{round(0.8 * scale, 2)}rem}}"
    )
    rules.append(
        f".{c('sub')}{{color:var({var('muted')});max-width:62ch;"
        f"margin-top:{round(0.7 * scale, 2)}rem;font-size:{round(1.0 * scale, 2)}rem}}"
    )
    rules.append(
        f".{c('eyebrow')}{{font-family:var({var('mono')});font-size:.72rem;"
        f"letter-spacing:.12em;text-transform:uppercase;color:var({var('muted')});"
        f"margin-bottom:{round(0.8 * scale, 2)}rem}}"
    )
    rules.append(
        f".{c('grid')}{{display:grid;gap:{round(0.9 * scale, 2)}rem;"
        "grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}"
    )
    rules.append(
        f".{c('card')}{{border:1px solid var({var('line')});"
        f"border-radius:var({var('radius')});padding:{round(1.05 * scale, 2)}rem;"
        f"background:var({var('surface')})}}"
    )
    rules.append(
        f".{c('card')} h3{{font-size:{round(0.95 * scale, 2)}rem;font-weight:600;"
        "margin-bottom:.35rem}"
    )
    rules.append(
        f".{c('card')} p{{color:var({var('muted')});font-size:.9rem;line-height:1.55}}"
    )
    rules.append(
        f".{c('code')}{{font-family:var({var('mono')});font-size:.82rem;"
        f"background:var({var('surface')});border:1px solid var({var('line')});"
        f"border-radius:var({var('radius')});padding:{round(0.85 * scale, 2)}rem "
        f"{round(1.0 * scale, 2)}rem;overflow-x:auto;line-height:1.6;"
        f"color:var({var('ink')})}}"
    )
    rules.append(f".{c('mono')}{{font-family:var({var('mono')});font-size:.85em}}")
    rules.append(
        f".{c('table')}{{width:100%;border-collapse:collapse;font-size:.88rem}}"
        f".{c('table')} th{{text-align:left;font-weight:600;color:var({var('muted')});"
        f"font-size:.76rem;letter-spacing:.06em;text-transform:uppercase;"
        f"padding:.55rem .8rem;border-bottom:1px solid var({var('line')})}}"
        f".{c('table')} td{{padding:.6rem .8rem;border-bottom:1px solid var({var('line')});"
        "vertical-align:top}"
    )
    rules.append(
        f".{c('method')}{{font-family:var({var('mono')});font-size:.72rem;"
        "font-weight:600;letter-spacing:.06em;padding:.15rem .4rem;"
        f"border:1px solid var({var('line')});border-radius:var({var('radius')});"
        f"color:var({var('accent')})}}"
    )
    rules.append(
        f".{c('dot')}{{display:inline-block;width:8px;height:8px;border-radius:50%;"
        "background:#2ea043;margin-right:.5rem;vertical-align:middle}"
    )
    rules.append(
        f".{c('status')}{{display:flex;align-items:center;justify-content:space-between;"
        f"gap:1rem;padding:{round(0.7 * scale, 2)}rem 0;"
        f"border-bottom:1px solid var({var('line')})}}"
    )
    rules.append(
        f".{c('meta')}{{display:flex;gap:{round(1.6 * scale, 2)}rem;flex-wrap:wrap;"
        f"color:var({var('muted')});font-size:.83rem;"
        f"margin-top:{round(1.3 * scale, 2)}rem}}"
    )
    rules.append(
        f".{c('meta')} b{{display:block;color:var({var('ink')});font-weight:500;"
        "margin-top:.15rem;font-family:var(" + var("mono") + ")}"
    )
    rules.append(
        f".{c('footer')}{{border-top:1px solid var({var('line')});"
        f"padding:{round(1.5 * scale, 2)}rem 0;color:var({var('muted')});"
        "font-size:.82rem}"
    )
    rules.append(f".{c('prose')} p{{max-width:66ch;margin-bottom:.9rem;"
                 f"color:var({var('muted')});line-height:1.65}}")
    rules.append(
        f".{c('list')} li{{padding:{round(0.6 * scale, 2)}rem 0;"
        f"border-bottom:1px solid var({var('line')});display:flex;gap:.9rem;"
        "align-items:baseline;flex-wrap:wrap}"
    )
    rules.append(
        f".{c('side')}{{display:grid;gap:{round(2.0 * scale, 2)}rem;"
        "grid-template-columns:200px minmax(0,1fr);align-items:start}"
    )
    rules.append(
        f".{c('toc')} li{{padding:.3rem 0;font-size:.87rem}}"
        f".{c('toc')} a{{color:var({var('muted')})}}"
    )
    rules.append(
        f"@media(max-width:760px){{.{c('side')}{{grid-template-columns:1fr}}"
        f".{c('nav')} ul{{gap:.9rem}}}}"
    )

    # Rule order carries no semantics here (no competing specificity), so it is
    # safe to shuffle the presentational tail for additional byte-level variance.
    head, tail = rules[:8], rules[8:]
    return "\n".join(head + rng.shuffled(tail)) + "\n"
