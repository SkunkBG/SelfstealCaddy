"""The four original themes, ported onto the new engine.

Backward compatibility is exact at the interface level: the theme keys, the
page URLs (``/work.html`` and friends) and the CLI contract are unchanged.
What changed is underneath — content is drawn from pools rather than
hard-coded, so two ``studio`` nodes no longer serve the same sentences.

These themes deliberately publish no API surface and no health endpoints.  A
neighbourhood coffee shop that answers ``/healthz`` is a stronger signal than
no decoy at all.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ..profile import Profile
from ..render import HeadMeta, build_document, esc
from ..rng import SeededRandom
from .base import Page, Site

_STUDIO_HEADLINES = [
    "Quiet design for brands that intend to last.",
    "Considered work for people who care about the details.",
    "Identity and product design, made slowly.",
    "Design that holds up after the launch.",
    "A small practice for brands with long horizons.",
]

_STUDIO_SERVICES = [
    ("Brand Identity", "Naming, marks, typography and the systems that hold a brand together as it grows."),
    ("Digital Product", "Interfaces and websites designed to be calm to use and unremarkable to maintain."),
    ("Editorial", "Print, photography direction and the long-form pieces that give a brand a voice."),
    ("Packaging", "Structure, print specification and the details that survive a production run."),
    ("Art Direction", "Photography, illustration and the visual language around a launch."),
    ("Design Systems", "Component libraries and documentation that outlive the team that wrote them."),
]

_STUDIO_PROJECTS = [
    "Marbury", "Field Atlas", "Sable", "Quill Press", "Longmere", "Aster",
    "Rookery", "Pale Fire", "Hollow Lane", "Winterbourne", "Thornbury",
]
_STUDIO_CATEGORIES = [
    "Identity, Packaging", "Brand, Web", "Editorial, Art Direction",
    "Identity, Digital", "Naming, Brand System", "Print, Signage",
]

_COFFEE_HEADLINES = [
    "Coffee, bread and a quiet room.",
    "Small batch roasting, seven days a week.",
    "A corner shop that takes coffee seriously.",
    "Slow mornings, good beans.",
]
_COFFEE_MENU = [
    ("Espresso", "2.60"), ("Macchiato", "2.90"), ("Cortado", "3.20"),
    ("Flat White", "3.60"), ("Filter", "3.10"), ("Cold Brew", "3.90"),
    ("Cappuccino", "3.40"), ("Mocha", "4.10"), ("Chai", "3.80"),
    ("Hot Chocolate", "3.50"),
]
_COFFEE_FOOD = [
    ("Sourdough toast", "4.20"), ("Almond croissant", "3.40"),
    ("Banana bread", "3.10"), ("Cinnamon bun", "3.60"),
    ("Seasonal galette", "4.60"), ("Granola & yoghurt", "5.20"),
]

_LAW_HEADLINES = [
    "Considered counsel for closely held businesses.",
    "A small practice, carefully run.",
    "Commercial advice without the overhead.",
    "Practical counsel for owners and founders.",
]
_LAW_PRACTICE = [
    ("Commercial", "Contracts, supply arrangements and the agreements that hold a business together."),
    ("Corporate", "Formation, shareholder arrangements, and the mechanics of ownership."),
    ("Employment", "Contracts, policies and the difficult conversations that follow them."),
    ("Property", "Commercial leases, acquisitions and disposals."),
    ("Disputes", "Early resolution where possible, and proper preparation where not."),
    ("Private Client", "Succession, trusts and the arrangements families rely on."),
]

_CONTRACTOR_HEADLINES = [
    "Building work, done properly.",
    "Renovation and extension, start to finish.",
    "Careful work on old buildings.",
    "A builder you can reach on the phone.",
]
_CONTRACTOR_SERVICES = [
    ("Extensions", "Single and two-storey extensions, from drawings through to sign-off."),
    ("Renovation", "Full-property refurbishment, sequenced so you can plan around it."),
    ("Roofing", "Flat and pitched roofing, repairs and full replacement."),
    ("Groundworks", "Foundations, drainage and hard landscaping."),
    ("Loft Conversion", "Structural work, stairs and building control throughout."),
    ("Restoration", "Sympathetic repair of period brick, timber and stone."),
]

_CLASSIC_PALETTES: Dict[str, List[Tuple[str, ...]]] = {
    "studio": [("#f3efe6", "#1c1a16", "#a9542f"), ("#f6f4ef", "#191817", "#3f6f5f"),
               ("#faf7f2", "#1b1a1c", "#6b5b95")],
    "coffee": [("#f6efe4", "#2a211b", "#9c5a2c"), ("#f7f2e8", "#241d18", "#7a7f3f"),
               ("#fbf6ee", "#2b2119", "#b5462f")],
    "law": [("#ffffff", "#10202f", "#9a7b34"), ("#fdfdfd", "#131f2c", "#1f3a5f"),
            ("#fcfbf9", "#181818", "#6e4a2f")],
    "contractor": [("#f2f1ee", "#1b1d20", "#c2671f"), ("#f4f4f2", "#17191c", "#3a6ea5"),
                   ("#f6f5f2", "#1d1c1a", "#9e3b2e")],
}


def _stylesheet(profile: Profile, bg: str, ink: str, accent: str) -> str:
    """Editorial stylesheet, still varied per install via mangled names."""
    c = profile.css
    rng = profile.rng.derive("classic-css")
    maxw = rng.choice([1000, 1040, 1080, 1120])
    pad = rng.choice([3.6, 4.2, 4.8])
    serif = profile.typography.serif
    sans = profile.typography.sans
    return "\n".join([
        f":root{{--bg:{bg};--ink:{ink};--accent:{accent};--muted:#6f6a5f;"
        f"--line:#ddd6c8;--max:{maxw}px;--serif:{serif};--sans:{sans}}}",
        "*{margin:0;padding:0;box-sizing:border-box}",
        "body{font-family:var(--sans);background:var(--bg);color:var(--ink);"
        "line-height:1.6;-webkit-font-smoothing:antialiased}",
        "a{color:inherit}",
        f".{c('wrap')}{{max-width:var(--max);margin:0 auto;padding:0 1.6rem}}",
        f".{c('bar')}{{display:flex;align-items:center;justify-content:space-between;"
        "flex-wrap:wrap;gap:1rem}",
        f".{c('header')}{{padding:1.7rem 0;border-bottom:1px solid var(--line)}}",
        f".{c('brand')}{{font-family:var(--serif);font-size:1.35rem;font-weight:600;"
        "text-decoration:none;letter-spacing:-.01em}",
        f".{c('nav')} ul{{list-style:none;display:flex;gap:1.9rem}}",
        f".{c('nav')} a{{text-decoration:none;color:var(--muted);font-size:.9rem}}",
        f".{c('nav')} a:hover{{color:var(--ink)}}",
        f".{c('hero')}{{padding:{pad}rem 0;border-bottom:1px solid var(--line)}}",
        f".{c('eyebrow')}{{font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;"
        "color:var(--accent);margin-bottom:1.4rem}",
        f".{c('h1')}{{font-family:var(--serif);font-weight:600;"
        "font-size:clamp(2.1rem,5.4vw,3.6rem);line-height:1.08;"
        "letter-spacing:-.015em;max-width:17ch}",
        f".{c('lead')}{{margin-top:1.5rem;max-width:56ch;color:var(--muted);"
        "font-size:1.1rem}",
        f".{c('section')}{{padding:{pad * 0.85:.1f}rem 0;border-bottom:1px solid var(--line)}}",
        f".{c('label')}{{font-size:.78rem;letter-spacing:.2em;text-transform:uppercase;"
        "color:var(--muted);margin-bottom:2rem}",
        f".{c('grid')}{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));"
        "gap:2.1rem}",
        f".{c('card')} h3{{font-family:var(--serif);font-weight:600;font-size:1.25rem;"
        "margin-bottom:.4rem}",
        f".{c('card')} p{{color:var(--muted);font-size:.95rem}}",
        f".{c('rows')} a{{display:flex;align-items:baseline;justify-content:space-between;"
        "gap:1rem;padding:1.25rem 0;border-top:1px solid var(--line);text-decoration:none}",
        f".{c('rows')} a:last-child{{border-bottom:1px solid var(--line)}}",
        f".{c('name')}{{font-family:var(--serif);font-size:1.3rem;font-weight:600}}",
        f".{c('cat')}{{color:var(--muted);font-size:.9rem;flex:1;text-align:right;"
        "padding-right:1.4rem}",
        f".{c('yr')}{{color:var(--accent);font-size:.85rem;font-variant-numeric:tabular-nums}}",
        f".{c('menu')} li{{display:flex;justify-content:space-between;gap:1rem;"
        "padding:.7rem 0;border-bottom:1px solid var(--line);list-style:none}",
        f".{c('email')}{{font-size:1.15rem;color:var(--accent);text-decoration:none}}",
        f".{c('prose')} p{{max-width:60ch;color:var(--muted);margin-top:1.05rem}}",
        f".{c('footer')}{{padding:2.2rem 0;color:var(--muted);font-size:.82rem}}",
        f"@media(max-width:640px){{.{c('nav')}{{display:none}}.{c('cat')}{{display:none}}}}",
    ]) + "\n"


def _shell(profile: Profile, nav: List[Tuple[str, str]]) -> Tuple[str, str]:
    c = profile.css
    links = "".join(f'<li><a href="{h}">{esc(t)}</a></li>' for h, t in nav)
    header = (
        f'<header {c.attr("header")}><div {c.attr("wrap")} {c.attr("bar")}>'
        f'<a {c.attr("brand")} href="/">{esc(profile.brand.name)}</a>'
        f'<nav {c.attr("nav")} aria-label="Primary"><ul>{links}</ul></nav>'
        f"</div></header>"
    )
    footer = (
        f'<footer {c.attr("footer")}><div {c.attr("wrap")} {c.attr("bar")}>'
        f"<span>&copy; {profile.year} {esc(profile.brand.name)}</span>"
        f"<span>{esc(profile.city)}</span></div></footer>"
    )
    return header, footer


def _page(profile: Profile, header: str, footer: str, *, url: str, file: str,
          title: str, description: str, body: str, priority: str = "0.5") -> Page:
    html = build_document(
        profile.doc,
        HeadMeta(title=title, description=description, canonical=url.lstrip("/")),
        header + body + footer,
        domain=profile.domain, theme_color=profile.palette.bg,
    )
    return Page(url=url, file=file, title=title, html=html, priority=priority)


def build(profile: Profile, key: str) -> Site:
    rng = profile.rng.derive("classic")
    c = profile.css
    bg, ink, accent = rng.choice(_CLASSIC_PALETTES[key])
    site = Site(profile=profile)
    site.files["style.css"] = _stylesheet(profile, bg, ink, accent)

    builder = {
        "studio": _build_studio,
        "coffee": _build_coffee,
        "law": _build_law,
        "contractor": _build_contractor,
    }[key]
    builder(profile, site, rng)

    header, footer = _shell(profile, _NAV[key](profile))
    site.files["404.html"] = build_document(
        profile.doc,
        HeadMeta(title=f"Page not found &mdash; {profile.brand.name}",
                 description="", canonical="404.html"),
        header +
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<h1 {c.attr("h1")}>Page not found</h1>'
        f'<p {c.attr("lead")}>We couldn&rsquo;t find that page. '
        f'<a href="/">Return home</a>.</p></div></section></main>' + footer,
        domain=profile.domain, theme_color=bg,
    )
    return site


_NAV = {
    "studio": lambda p: [("/work.html", "Work"), ("/studio.html", "Studio"),
                         ("/contact.html", "Contact")],
    "coffee": lambda p: [("/menu.html", "Menu"), ("/about.html", "About"),
                         ("/visit.html", "Visit")],
    "law": lambda p: [("/practice.html", "Practice"), ("/people.html", "People"),
                      ("/contact.html", "Contact")],
    "contractor": lambda p: [("/services.html", "Services"),
                             ("/projects.html", "Projects"), ("/contact.html", "Contact")],
}


def _cards(profile: Profile, items) -> str:
    c = profile.css
    return f'<div {c.attr("grid")}>' + "".join(
        f'<div {c.attr("card")}><h3>{esc(t)}</h3><p>{esc(d)}</p></div>'
        for t, d in items
    ) + "</div>"


def _build_studio(profile: Profile, site: Site, rng) -> None:
    c = profile.css
    header, footer = _shell(profile, _NAV["studio"](profile))
    headline = rng.choice(_STUDIO_HEADLINES)
    services = rng.sample(_STUDIO_SERVICES, rng.between(3, 4))
    projects = rng.sample(_STUDIO_PROJECTS, rng.between(4, 6))
    site.add_page(_page(
        profile, header, footer, url="/", file="index.html",
        title=f"{profile.brand.name} &mdash; Independent design studio",
        description=f"Independent design studio in {profile.city} working on brand "
                    f"identity, digital products and art direction.",
        priority="1.0",
        body=(f'<main><div {c.attr("hero")}><div {c.attr("wrap")}>'
              f'<p {c.attr("eyebrow")}>Independent design studio</p>'
              f'<h1 {c.attr("h1")}>{esc(headline)}</h1>'
              f'<p {c.attr("lead")}>We partner with founders and small teams on '
              f"identity, product and the in-between.</p></div></div>"
              f'<section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>What we do</p>{_cards(profile, services)}'
              f"</div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/studio.html", file="studio.html",
        title=f"Studio &mdash; {profile.brand.name}",
        description=f"About {profile.brand.name}, an independent design studio in "
                    f"{profile.city}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>Studio</p>'
              f'<h1 {c.attr("h1")}>A small studio, by design.</h1>'
              f'<div {c.attr("prose")}>'
              f"<p>{esc(profile.brand.name)} is a small practice that has worked "
              f"quietly since {profile.year}. We take on a handful of engagements "
              f"each year so that each one gets the attention it needs.</p>"
              f"<p>Most of our work arrives by referral, which suits us.</p>"
              f"</div></div></section></main>"),
    ))
    rows = "".join(
        f'<a href="/contact.html"><span {c.attr("name")}>{esc(name)}</span>'
        f'<span {c.attr("cat")}>{esc(rng.choice(_STUDIO_CATEGORIES))}</span>'
        f'<span {c.attr("yr")}>{rng.between(profile.year + 2, 2024)}</span></a>'
        for name in projects
    )
    site.add_page(_page(
        profile, header, footer, url="/work.html", file="work.html",
        title=f"Work &mdash; {profile.brand.name}",
        description=f"Selected work by {profile.brand.name}.",
        body=(f'<main><section {c.attr("section")} {c.attr("rows")}>'
              f'<div {c.attr("wrap")}><p {c.attr("label")}>Selected work</p>'
              f"<div>{rows}</div></div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/contact.html", file="contact.html",
        title=f"Contact &mdash; {profile.brand.name}",
        description=f"Get in touch with {profile.brand.name}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<h1 {c.attr("h1")}>Have something worth making well?</h1>'
              f'<p style="margin-top:1.4rem"><a {c.attr("email")} '
              f'href="mailto:hello@{profile.domain}">hello@{profile.domain}</a></p>'
              f"</div></section></main>"),
    ))


def _build_coffee(profile: Profile, site: Site, rng) -> None:
    c = profile.css
    header, footer = _shell(profile, _NAV["coffee"](profile))
    drinks = rng.sample(_COFFEE_MENU, rng.between(6, 8))
    food = rng.sample(_COFFEE_FOOD, rng.between(3, 5))
    opens = rng.choice(["07:00", "07:30", "08:00"])
    closes = rng.choice(["16:00", "17:00", "18:00"])
    site.add_page(_page(
        profile, header, footer, url="/", file="index.html",
        title=f"{profile.brand.name} &mdash; Coffee in {profile.city}",
        description=f"Independent coffee shop in {profile.city}. "
                    f"Open daily from {opens}.",
        priority="1.0",
        body=(f'<main><div {c.attr("hero")}><div {c.attr("wrap")}>'
              f'<p {c.attr("eyebrow")}>{esc(profile.city)} &middot; since {profile.year}</p>'
              f'<h1 {c.attr("h1")}>{esc(rng.choice(_COFFEE_HEADLINES))}</h1>'
              f'<p {c.attr("lead")}>Open {opens}&ndash;{closes}, seven days a week.'
              f"</p></div></div>"
              f'<section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>Today</p><ul {c.attr("menu")}>' +
              "".join(f"<li><span>{esc(n)}</span><span>{p}</span></li>"
                      for n, p in drinks[:4]) +
              "</ul></div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/menu.html", file="menu.html",
        title=f"Menu &mdash; {profile.brand.name}",
        description=f"Coffee and food menu at {profile.brand.name}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>Coffee</p><ul {c.attr("menu")}>' +
              "".join(f"<li><span>{esc(n)}</span><span>{p}</span></li>"
                      for n, p in drinks) +
              f'</ul><p {c.attr("label")} style="margin-top:2.4rem">Kitchen</p>'
              f'<ul {c.attr("menu")}>' +
              "".join(f"<li><span>{esc(n)}</span><span>{p}</span></li>"
                      for n, p in food) +
              "</ul></div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/about.html", file="about.html",
        title=f"About &mdash; {profile.brand.name}",
        description=f"About {profile.brand.name} in {profile.city}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<h1 {c.attr("h1")}>A corner shop.</h1>'
              f'<div {c.attr("prose")}><p>We opened in {profile.year} with one '
              f"machine and a short menu. Not much has changed.</p>"
              f"<p>Beans are roasted in small batches and rotated through the "
              f"week.</p></div></div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/visit.html", file="visit.html",
        title=f"Visit &mdash; {profile.brand.name}",
        description=f"Opening hours and location for {profile.brand.name}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<h1 {c.attr("h1")}>Visit</h1>'
              f'<div {c.attr("prose")}><p>Open daily {opens}&ndash;{closes}.</p>'
              f"<p>{esc(profile.city)}. No bookings &mdash; walk in.</p></div>"
              f'<p style="margin-top:1.4rem"><a {c.attr("email")} '
              f'href="mailto:hello@{profile.domain}">hello@{profile.domain}</a></p>'
              f"</div></section></main>"),
    ))


def _build_law(profile: Profile, site: Site, rng) -> None:
    c = profile.css
    header, footer = _shell(profile, _NAV["law"](profile))
    areas = rng.sample(_LAW_PRACTICE, rng.between(3, 5))
    firm = f"{profile.brand.name}"
    site.add_page(_page(
        profile, header, footer, url="/", file="index.html",
        title=f"{firm} &mdash; Commercial law",
        description=f"Commercial legal practice in {profile.city}, established "
                    f"{profile.year}.",
        priority="1.0",
        body=(f'<main><div {c.attr("hero")}><div {c.attr("wrap")}>'
              f'<p {c.attr("eyebrow")}>Established {profile.year}</p>'
              f'<h1 {c.attr("h1")}>{esc(rng.choice(_LAW_HEADLINES))}</h1>'
              f'<p {c.attr("lead")}>A commercial practice in {esc(profile.city)} '
              f"advising owner-managed businesses.</p></div></div>"
              f'<section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>Practice areas</p>{_cards(profile, areas)}'
              f"</div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/practice.html", file="practice.html",
        title=f"Practice &mdash; {firm}",
        description=f"Practice areas at {firm}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>Practice</p>'
              f'<h1 {c.attr("h1")}>What we do.</h1>{_cards(profile, areas)}'
              f"</div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/people.html", file="people.html",
        title=f"People &mdash; {firm}",
        description=f"The people at {firm}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<h1 {c.attr("h1")}>A small team.</h1>'
              f'<div {c.attr("prose")}><p>The practice has been run on the same '
              f"basis since {profile.year}: partners do the work.</p>"
              f"<p>Enquiries are answered within one working day.</p></div>"
              f"</div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/contact.html", file="contact.html",
        title=f"Contact &mdash; {firm}",
        description=f"Contact {firm}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<h1 {c.attr("h1")}>Get in touch.</h1>'
              f'<p style="margin-top:1.4rem"><a {c.attr("email")} '
              f'href="mailto:enquiries@{profile.domain}">enquiries@{profile.domain}</a>'
              f"</p></div></section></main>"),
    ))


def _build_contractor(profile: Profile, site: Site, rng) -> None:
    c = profile.css
    header, footer = _shell(profile, _NAV["contractor"](profile))
    services = rng.sample(_CONTRACTOR_SERVICES, rng.between(3, 5))
    site.add_page(_page(
        profile, header, footer, url="/", file="index.html",
        title=f"{profile.brand.name} &mdash; Building contractor",
        description=f"Building contractor in {profile.city}. Extensions, "
                    f"renovation and roofing since {profile.year}.",
        priority="1.0",
        body=(f'<main><div {c.attr("hero")}><div {c.attr("wrap")}>'
              f'<p {c.attr("eyebrow")}>{esc(profile.city)} &middot; since {profile.year}</p>'
              f'<h1 {c.attr("h1")}>{esc(rng.choice(_CONTRACTOR_HEADLINES))}</h1>'
              f'<p {c.attr("lead")}>Extensions, renovation and roofing for '
              f"domestic and light commercial clients.</p></div></div>"
              f'<section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>Services</p>{_cards(profile, services)}'
              f"</div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/services.html", file="services.html",
        title=f"Services &mdash; {profile.brand.name}",
        description=f"Services offered by {profile.brand.name}.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<p {c.attr("label")}>Services</p>'
              f'<h1 {c.attr("h1")}>What we take on.</h1>{_cards(profile, services)}'
              f"</div></section></main>"),
    ))
    rows = "".join(
        f'<a href="/contact.html"><span {c.attr("name")}>{esc(name)}</span>'
        f'<span {c.attr("cat")}>{esc(kind)}</span>'
        f'<span {c.attr("yr")}>{rng.between(profile.year + 3, 2024)}</span></a>'
        for name, kind in rng.sample([
            ("Mill Lane", "Extension"), ("Rookery Road", "Renovation"),
            ("Chapel Yard", "Roofing"), ("Old Forge", "Restoration"),
            ("Beech Court", "Loft conversion"), ("Station Row", "Groundworks"),
        ], rng.between(4, 6))
    )
    site.add_page(_page(
        profile, header, footer, url="/projects.html", file="projects.html",
        title=f"Projects &mdash; {profile.brand.name}",
        description=f"Recent projects completed by {profile.brand.name}.",
        body=(f'<main><section {c.attr("section")} {c.attr("rows")}>'
              f'<div {c.attr("wrap")}><p {c.attr("label")}>Recent projects</p>'
              f"<div>{rows}</div></div></section></main>"),
    ))
    site.add_page(_page(
        profile, header, footer, url="/contact.html", file="contact.html",
        title=f"Contact &mdash; {profile.brand.name}",
        description=f"Contact {profile.brand.name} for a quotation.",
        body=(f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
              f'<h1 {c.attr("h1")}>Ask for a quotation.</h1>'
              f'<p style="margin-top:1.4rem"><a {c.attr("email")} '
              f'href="mailto:office@{profile.domain}">office@{profile.domain}</a></p>'
              f"</div></section></main>"),
    ))
