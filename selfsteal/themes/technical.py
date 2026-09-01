"""Technical theme engine.

One engine, eleven archetypes, six structural variants.  The variant decides
the DOM: which elements exist, how the landing page is composed, what the
navigation is called and which secondary pages are published.  Two nodes
running ``media-api`` with different variants share no markup skeleton.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from .. import payloads
from ..profile import Profile
from ..render import HeadMeta, build_document, code_block, esc, table
from ..rng import SeededRandom
from .base import Endpoint, Page, Param, Site
from .catalog import TechResource, TechTheme

VARIANTS = ["portal", "minimal", "console", "docsfirst", "platform", "reference"]

_FACTORIES: Dict[str, Callable] = {
    "collection": payloads.collection,
    "enumeration": payloads.enumeration,
    "regions": payloads.regions,
    "usage": payloads.usage,
    "limits": payloads.limits,
    "schema_doc": payloads.schema_doc,
}


# --------------------------------------------------------------------------
# endpoints
# --------------------------------------------------------------------------

def _build_payload(profile: Profile, resource: TechResource) -> dict:
    rng = profile.rng.derive(f"payload:{resource.name}")
    factory = _FACTORIES[resource.factory]
    args = dict(resource.args)
    if "item" in args:
        args["item"] = payloads.ITEM_BUILDERS[args["item"]]
    return factory(profile, rng, **args)


def build_endpoints(profile: Profile, theme: TechTheme,
                    resources: List[TechResource]) -> List[Endpoint]:
    rng = profile.rng.derive("endpoints")
    ver = profile.api_version
    names = [r.name for r in resources]

    endpoints: List[Endpoint] = [
        Endpoint("/api", "Supported API versions.",
                 payloads.root_document(profile, rng.derive("root")),
                 cache="public, max-age=3600"),
        Endpoint(f"/api/{ver}", "Version index and resource map.",
                 payloads.index_document(profile, rng.derive("index"), resources=names),
                 cache="public, max-age=300"),
    ]
    for resource in resources:
        endpoints.append(Endpoint(
            path=f"/api/{ver}/{resource.name}",
            summary=resource.summary,
            payload=_build_payload(profile, resource),
            params=[Param(n, t, req, d) for n, t, req, d in resource.params],
            cache=resource.cache,
            doc_slug=resource.name,
        ))
    endpoints.append(Endpoint(
        f"/api/{ver}/status", "Machine-readable service status.",
        payloads.status_document(profile, rng.derive("status"),
                                 components=theme.components),
        cache="no-store",
    ))
    return endpoints


def build_health(profile: Profile) -> List[Endpoint]:
    rng = profile.rng.derive("health")
    return [
        Endpoint("/health", "Liveness probe.",
                 payloads.health_document(profile, rng), cache="no-store"),
        Endpoint("/healthz", "Liveness probe (Kubernetes convention).",
                 payloads.health_document(profile, rng), cache="no-store"),
        Endpoint("/ready", "Readiness probe.",
                 payloads.health_document(profile, rng, ready=True), cache="no-store"),
        Endpoint("/readyz", "Readiness probe (Kubernetes convention).",
                 payloads.health_document(profile, rng, ready=True), cache="no-store"),
    ]


# --------------------------------------------------------------------------
# chrome
# --------------------------------------------------------------------------

def _logo(profile: Profile) -> str:
    """Inline SVG mark, so the header needs no extra request."""
    rng = profile.rng.derive("logo")
    accent = profile.palette.accent
    shape = rng.choice(["rect", "hex", "layers", "dot", "chevron"])
    if shape == "rect":
        body = f'<rect x="2" y="2" width="20" height="20" rx="4" fill="{accent}"/>'
    elif shape == "hex":
        body = f'<path d="M12 2 21 7v10l-9 5-9-5V7z" fill="{accent}"/>'
    elif shape == "layers":
        body = (f'<path d="M12 3 3 8l9 5 9-5z" fill="{accent}"/>'
                f'<path d="M3 13l9 5 9-5" stroke="{accent}" stroke-width="2" fill="none"/>')
    elif shape == "dot":
        body = (f'<circle cx="12" cy="12" r="9" fill="none" stroke="{accent}" stroke-width="2"/>'
                f'<circle cx="12" cy="12" r="3.5" fill="{accent}"/>')
    else:
        body = (f'<path d="M6 4l7 8-7 8" stroke="{accent}" stroke-width="2.4" '
                'fill="none" stroke-linecap="round"/>')
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{body}</svg>'


def _nav_items(profile: Profile, variant: str) -> List[Tuple[str, str]]:
    rng = profile.rng.derive("nav")
    docs_label = rng.choice(["Docs", "Documentation", "Developers", "Reference"])
    status_label = rng.choice(["Status", "System Status", "Availability"])
    items = [("/docs", docs_label), ("/status", status_label)]
    if variant in ("portal", "platform", "console"):
        items.insert(1, (f"/docs/api", rng.choice(["API", "API Reference", "Endpoints"])))
    if variant in ("minimal", "docsfirst", "reference"):
        items.append(("/about", "About"))
    return items


def _header(profile: Profile, variant: str) -> str:
    c = profile.css
    nav = "".join(
        f'<li><a href="{href}">{esc(label)}</a></li>'
        for href, label in _nav_items(profile, variant)
    )
    logo = _logo(profile) if profile.rng.derive("logo-show").chance(75) else ""
    return (
        f'<header {c.attr("header")}><div {c.attr("wrap")}><div {c.attr("bar")}>'
        f'<a {c.attr("brand")} href="/">{logo}{esc(profile.brand.name)}</a>'
        f'<nav {c.attr("nav")} aria-label="Primary"><ul>{nav}</ul></nav>'
        f"</div></div></header>"
    )


def _footer(profile: Profile) -> str:
    c = profile.css
    rng = profile.rng.derive("footer")
    bits = [f"&copy; {profile.year}&ndash;{min(profile.year + 12, 2025)} "
            f"{esc(profile.brand.company)}"]
    if rng.chance(70):
        bits.append(f'<a href="/status">Status</a>')
    if rng.chance(60):
        bits.append(f'<a href="/docs">Documentation</a>')
    if rng.chance(45):
        bits.append(f"{esc(profile.region.city)} &middot; {esc(profile.region.zone)}")
    sep = rng.choice([" &middot; ", " &nbsp;&nbsp; ", " | "])
    return (
        f'<footer {c.attr("footer")}><div {c.attr("wrap")}>'
        f"{sep.join(bits)}</div></footer>"
    )


def _page(profile: Profile, *, url: str, file: str, title: str, description: str,
          body: str, in_sitemap: bool = True, priority: str = "0.5",
          variant: str = "portal") -> Page:
    html = build_document(
        profile.doc,
        HeadMeta(title=title, description=description,
                 canonical=url.lstrip("/")),
        _header(profile, variant) + body + _footer(profile),
        domain=profile.domain,
        theme_color=profile.palette.bg,
    )
    return Page(url=url, file=file, title=title, html=html,
                in_sitemap=in_sitemap, priority=priority)


# --------------------------------------------------------------------------
# landing page variants
# --------------------------------------------------------------------------

def _curl_example(profile: Profile, endpoint: Endpoint) -> List[str]:
    return [
        f"$ curl https://{profile.domain}{endpoint.path}",
        "",
        *payloads_json_lines(endpoint.payload),
    ]


def payloads_json_lines(payload: dict, limit: int = 12) -> List[str]:
    import json
    text = json.dumps(payload, indent=2)
    lines = text.splitlines()
    if len(lines) > limit:
        lines = lines[: limit - 1] + ["  ..."]
    return lines


def _meta_strip(profile: Profile) -> str:
    c = profile.css
    return (
        f'<div {c.attr("meta")}>'
        f"<div>Version<b>{esc(profile.api_version)}</b></div>"
        f"<div>Region<b>{esc(profile.region.pop)}</b></div>"
        f"<div>Status<b>operational</b></div>"
        f"<div>Updated<b>{esc(profile.release)}</b></div>"
        f"</div>"
    )


def _endpoint_cards(profile: Profile, endpoints: List[Endpoint]) -> str:
    c = profile.css
    cards = []
    for ep in endpoints:
        cards.append(
            f'<div {c.attr("card")}><h3><span {c.attr("method")}>GET</span> '
            f'<a href="/docs{ep.path}"><code {c.attr("mono")}>{esc(ep.path)}</code></a></h3>'
            f"<p>{esc(ep.summary)}</p></div>"
        )
    return f'<div {c.attr("grid")}>' + "".join(cards) + "</div>"


def _endpoint_table(profile: Profile, endpoints: List[Endpoint]) -> str:
    c = profile.css
    rows = [
        (f'<span {c.attr("method")}>GET</span>',
         f'<a href="/docs{ep.path}"><code {c.attr("mono")}>{esc(ep.path)}</code></a>',
         esc(ep.summary))
        for ep in endpoints
    ]
    return table(c, ["Method", "Endpoint", "Description"], rows)


def _endpoint_list(profile: Profile, endpoints: List[Endpoint]) -> str:
    c = profile.css
    items = "".join(
        f'<li><span {c.attr("method")}>GET</span>'
        f'<a href="/docs{ep.path}"><code {c.attr("mono")}>{esc(ep.path)}</code></a>'
        f"<span>{esc(ep.summary)}</span></li>"
        for ep in endpoints
    )
    return f'<ul {c.attr("list")}>{items}</ul>'


def render_home(profile: Profile, theme: TechTheme, variant: str,
                endpoints: List[Endpoint]) -> str:
    c = profile.css
    quick = next((e for e in endpoints if e.path.endswith(theme.quickstart)),
                 endpoints[1])
    public = [e for e in endpoints if e.path.startswith("/api/")
              and not e.path.endswith("/status")]
    title = profile.brand.product
    tagline = profile.tagline

    if variant == "portal":
        return (
            f'<main><div {c.attr("lede")}><div {c.attr("wrap")}>'
            f'<p {c.attr("eyebrow")}>{esc(theme.label)} &middot; {esc(profile.api_version)}</p>'
            f'<h1 {c.attr("h1")}>{esc(tagline)}</h1>'
            f'<p {c.attr("sub")}>{esc(profile.description)}</p>'
            f"{_meta_strip(profile)}</div></div>"
            f'<section {c.attr("section")}><div {c.attr("wrap")}>'
            f'<h2 {c.attr("h2")}>Endpoints</h2>{_endpoint_cards(profile, public)}'
            f"</div></section>"
            f'<section {c.attr("section")}><div {c.attr("wrap")}>'
            f'<h2 {c.attr("h2")}>Quick start</h2>'
            f"{code_block(c, _curl_example(profile, quick))}</div></section></main>"
        )

    if variant == "minimal":
        return (
            f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
            f'<h1 {c.attr("h1")}>{esc(title)}</h1>'
            f'<p {c.attr("sub")}>{esc(profile.description)}</p>'
            f'<div {c.attr("prose")}><p>Base URL '
            f'<code {c.attr("mono")}>{esc(profile.api_base)}</code>. '
            f"All responses are JSON. Read endpoints are cacheable; "
            f"probe endpoints are not.</p></div>"
            f"{_endpoint_list(profile, public)}"
            f"{code_block(c, _curl_example(profile, quick))}"
            f"</div></section></main>"
        )

    if variant == "console":
        tiles = "".join(
            f'<div {c.attr("card")}><h3>{esc(name)}</h3>'
            f'<p><span {c.attr("dot")}></span>Operational</p></div>'
            for name in theme.components
        )
        return (
            f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
            f'<div {c.attr("side")}>'
            f'<aside><p {c.attr("eyebrow")}>{esc(theme.noun)}</p>'
            f'<ul {c.attr("toc")}>'
            + "".join(f'<li><a href="/docs{e.path}">{esc(e.path.split("/")[-1])}</a></li>'
                      for e in public)
            + "</ul></aside>"
            f'<div><h1 {c.attr("h1")}>{esc(title)}</h1>'
            f'<p {c.attr("sub")}>{esc(profile.description)}</p>'
            f'<div {c.attr("grid")} style="margin-top:1.6rem">{tiles}</div>'
            f"{_meta_strip(profile)}"
            f"{code_block(c, _curl_example(profile, quick))}"
            f"</div></div></div></section></main>"
        )

    if variant == "docsfirst":
        return (
            f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
            f'<div {c.attr("side")}>'
            f'<aside><p {c.attr("eyebrow")}>Contents</p><ul {c.attr("toc")}>'
            f'<li><a href="#overview">Overview</a></li>'
            f'<li><a href="#auth">Authentication</a></li>'
            f'<li><a href="#endpoints">Endpoints</a></li>'
            f'<li><a href="/docs">Full reference</a></li></ul></aside>'
            f'<div {c.attr("prose")}>'
            f'<h1 {c.attr("h1")} id="overview">{esc(title)}</h1>'
            f"<p>{esc(profile.description)}</p>"
            f'<h2 {c.attr("h2")} id="auth">Authentication</h2>'
            f"<p>Requests are authenticated with a project key supplied in the "
            f"<code>Authorization</code> header. Keys are issued from the account "
            f"dashboard and are scoped per environment.</p>"
            f'<h2 {c.attr("h2")} id="endpoints">Endpoints</h2>'
            f"{_endpoint_table(profile, public)}"
            f"{code_block(c, _curl_example(profile, quick))}"
            f"</div></div></div></section></main>"
        )

    if variant == "platform":
        comps = "".join(
            f'<div {c.attr("status")}><span>{esc(name)}</span>'
            f'<span><span {c.attr("dot")}></span>Operational</span></div>'
            for name in theme.components
        )
        return (
            f'<main><div {c.attr("lede")}><div {c.attr("wrap")}>'
            f'<h1 {c.attr("h1")}>{esc(tagline)}</h1>'
            f'<p {c.attr("sub")}>{esc(profile.description)}</p></div></div>'
            f'<section {c.attr("section")}><div {c.attr("wrap")}>'
            f'<h2 {c.attr("h2")}>API</h2>{_endpoint_table(profile, public)}'
            f"</div></section>"
            f'<section {c.attr("section")}><div {c.attr("wrap")}>'
            f'<h2 {c.attr("h2")}>Components</h2>{comps}{_meta_strip(profile)}'
            f"</div></section></main>"
        )

    # reference
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<p {c.attr("eyebrow")}>{esc(profile.brand.name)} &middot; {esc(theme.label)}</p>'
        f'<h1 {c.attr("h1")}>{esc(title)}</h1>'
        f'<p {c.attr("sub")}>Base URL <code {c.attr("mono")}>{esc(profile.api_base)}</code></p>'
        f"{_endpoint_table(profile, public)}"
        f'<h2 {c.attr("h2")} style="margin-top:2rem">Example</h2>'
        f"{code_block(c, _curl_example(profile, quick))}"
        f"{_meta_strip(profile)}</div></section></main>"
    )


# --------------------------------------------------------------------------
# secondary pages
# --------------------------------------------------------------------------

def render_docs_index(profile: Profile, theme: TechTheme,
                      endpoints: List[Endpoint]) -> str:
    c = profile.css
    public = [e for e in endpoints if e.path.startswith("/api/")]
    sections = [
        ("Overview", f"{esc(profile.brand.product)} is a read-oriented HTTP API. "
                     f"All responses are JSON encoded in UTF-8."),
        ("Quick start", f"Every resource is reachable under "
                        f"<code>{esc(profile.api_base)}</code>. No SDK is required."),
        ("Authentication", "Requests carry a project key in the "
                           "<code>Authorization</code> header. Keys are scoped per "
                           "environment and may be rotated without downtime."),
        ("Errors", "Errors return a JSON object with an <code>error.code</code> and "
                   "<code>error.message</code>. The HTTP status carries the same "
                   "meaning as the code."),
        ("Rate limits", "Limits are applied per key. Exceeding a limit returns "
                        "<code>429</code> with a <code>Retry-After</code> header."),
    ]
    blocks = "".join(
        f'<h2 {c.attr("h2")} id="{name.lower().replace(" ", "-")}">{esc(name)}</h2>'
        f"<p>{text}</p>"
        for name, text in sections
    )
    toc = "".join(
        f'<li><a href="#{name.lower().replace(" ", "-")}">{esc(name)}</a></li>'
        for name, _ in sections
    ) + '<li><a href="/docs/api">API reference</a></li>'
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<div {c.attr("side")}>'
        f'<aside><p {c.attr("eyebrow")}>Documentation</p>'
        f'<ul {c.attr("toc")}>{toc}</ul></aside>'
        f'<div {c.attr("prose")}><h1 {c.attr("h1")}>Documentation</h1>'
        f"{blocks}"
        f'<h2 {c.attr("h2")}>Endpoints</h2>{_endpoint_table(profile, public)}'
        f"</div></div></div></section></main>"
    )


def render_docs_api(profile: Profile, endpoints: List[Endpoint]) -> str:
    c = profile.css
    public = [e for e in endpoints if e.path.startswith("/api/")]
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<h1 {c.attr("h1")}>API reference</h1>'
        f'<p {c.attr("sub")}>Version {esc(profile.api_version)}. '
        f"All endpoints are read-only.</p>"
        f"{_endpoint_table(profile, public)}</div></section></main>"
    )


def render_endpoint_doc(profile: Profile, endpoint: Endpoint) -> str:
    c = profile.css
    if endpoint.params:
        params = table(
            c, ["Parameter", "Type", "Required", "Description"],
            [(f'<code {c.attr("mono")}>{esc(p.name)}</code>', esc(p.kind),
              "yes" if p.required else "no", esc(p.description))
             for p in endpoint.params],
        )
    else:
        params = "<p>This endpoint takes no parameters.</p>"
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<p {c.attr("eyebrow")}>API reference</p>'
        f'<h1 {c.attr("h1")}><span {c.attr("method")}>GET</span> '
        f'<code {c.attr("mono")}>{esc(endpoint.path)}</code></h1>'
        f'<p {c.attr("sub")}>{esc(endpoint.summary)}</p>'
        f'<h2 {c.attr("h2")} style="margin-top:2rem">Parameters</h2>{params}'
        f'<h2 {c.attr("h2")} style="margin-top:2rem">Response</h2>'
        f'<p {c.attr("sub")}>Content-Type <code {c.attr("mono")}>application/json</code>. '
        f'Cache-Control <code {c.attr("mono")}>{esc(endpoint.cache)}</code>.</p>'
        f"{code_block(c, payloads_json_lines(endpoint.payload, limit=30))}"
        f'<h2 {c.attr("h2")} style="margin-top:2rem">Example</h2>'
        f"{code_block(c, [f'curl -s https://{profile.domain}{endpoint.path}'])}"
        f"</div></section></main>"
    )


def render_status(profile: Profile, theme: TechTheme) -> str:
    c = profile.css
    rng = profile.rng.derive("statuspage")
    rows = "".join(
        f'<div {c.attr("status")}><span>{esc(name)}</span>'
        f'<span><span {c.attr("dot")}></span>Operational</span></div>'
        for name in theme.components
    )
    history = "".join(
        f'<div {c.attr("status")}><span>{esc(item["title"])}</span>'
        f'<span>{esc(item["resolved_at"][:10])} &middot; resolved</span></div>'
        for item in [payloads.incident_item(profile, rng) for _ in range(rng.between(1, 3))]
    )
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<h1 {c.attr("h1")}>System status</h1>'
        f'<p {c.attr("sub")}><span {c.attr("dot")}></span>'
        f"All systems operational</p>"
        f"{_meta_strip(profile)}"
        f'<h2 {c.attr("h2")} style="margin-top:2.4rem">Components</h2>{rows}'
        f'<h2 {c.attr("h2")} style="margin-top:2.4rem">Recent incidents</h2>{history}'
        f'<p {c.attr("sub")}>Machine-readable status is available at '
        f'<a href="/status.json"><code {c.attr("mono")}>/status.json</code></a>.</p>'
        f"</div></section></main>"
    )


def render_about(profile: Profile, theme: TechTheme) -> str:
    c = profile.css
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<div {c.attr("prose")}><h1 {c.attr("h1")}>About</h1>'
        f"<p>{esc(profile.brand.company)} operates {esc(profile.brand.product)}, "
        f"{theme.description[0].lower() + theme.description[1:]}</p>"
        f"<p>The service has been in operation since {profile.year} and is "
        f"currently served from {esc(profile.region.city)} "
        f"({esc(profile.region.zone)}).</p>"
        f"<p>Technical enquiries: "
        f'<a href="mailto:{esc(profile.contact_email)}">{esc(profile.contact_email)}</a>.</p>'
        f"</div></div></section></main>"
    )


def render_changelog(profile: Profile) -> str:
    c = profile.css
    rng = profile.rng.derive("changelog")
    entries = []
    import datetime as dt
    day = dt.date.fromisoformat(profile.release)
    notes = rng.shuffled([
        "Added cursor-based pagination to list endpoints.",
        "Reduced p99 latency on read requests.",
        "Documented cache semantics for each endpoint.",
        "Added readiness probe alongside the existing liveness probe.",
        "Response payloads now include an explicit object type.",
        "Corrected Cache-Control on volatile endpoints.",
    ])[:rng.between(3, 5)]
    for note in notes:
        entries.append(
            f'<li><code {c.attr("mono")}>{day.isoformat()}</code>'
            f"<span>{esc(note)}</span></li>"
        )
        day -= dt.timedelta(days=rng.between(9, 70))
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<h1 {c.attr("h1")}>Changelog</h1>'
        f'<ul {c.attr("list")} style="margin-top:1.4rem">' + "".join(entries) +
        "</ul></div></section></main>"
    )


def render_404(profile: Profile, variant: str) -> str:
    c = profile.css
    return (
        f'<main><section {c.attr("section")}><div {c.attr("wrap")}>'
        f'<p {c.attr("eyebrow")}>404</p>'
        f'<h1 {c.attr("h1")}>Page not found</h1>'
        f'<p {c.attr("sub")}>The page you requested does not exist. '
        f'Try the <a href="/docs">documentation</a> or return to the '
        f'<a href="/">overview</a>.</p></div></section></main>'
    )


# --------------------------------------------------------------------------
# build
# --------------------------------------------------------------------------

def build(profile: Profile, theme: TechTheme) -> Site:
    variant = profile.variant
    rng = profile.rng.derive("compose")

    # Not every install publishes every resource: dropping one or two is both
    # realistic (services differ) and a further source of divergence.
    resources = list(theme.resources)
    if len(resources) > 3 and rng.chance(35):
        resources = rng.sample(resources, len(resources) - 1)
        resources.sort(key=lambda r: [x.name for x in theme.resources].index(r.name))

    endpoints = build_endpoints(profile, theme, resources)
    health = build_health(profile)
    site = Site(profile=profile)
    site.endpoints = endpoints + health
    site.health_paths = [e.path for e in health]

    site.add_page(_page(
        profile, url="/", file="index.html",
        title=f"{profile.brand.product}", description=profile.description,
        body=render_home(profile, theme, variant, endpoints),
        priority="1.0", variant=variant,
    ))
    site.add_page(_page(
        profile, url="/docs", file="docs/index.html",
        title=f"Documentation &mdash; {profile.brand.name}",
        description=f"Developer documentation for {profile.brand.product}.",
        body=render_docs_index(profile, theme, endpoints),
        priority="0.8", variant=variant,
    ))
    site.add_page(_page(
        profile, url="/docs/api", file="docs/api/index.html",
        title=f"API reference &mdash; {profile.brand.name}",
        description=f"Endpoint reference for {profile.brand.product} "
                    f"{profile.api_version}.",
        body=render_docs_api(profile, endpoints),
        priority="0.7", variant=variant,
    ))
    for endpoint in endpoints:
        if not endpoint.path.startswith("/api/") or endpoint.path.count("/") < 3:
            continue
        site.add_page(_page(
            profile, url=f"/docs{endpoint.path}",
            file=f"docs{endpoint.path}/index.html",
            title=f"{endpoint.path} &mdash; {profile.brand.name}",
            description=endpoint.summary,
            body=render_endpoint_doc(profile, endpoint),
            priority="0.5", variant=variant,
        ))
    site.add_page(_page(
        profile, url="/status", file="status/index.html",
        title=f"System status &mdash; {profile.brand.name}",
        description=f"Current operational status of {profile.brand.product}.",
        body=render_status(profile, theme),
        priority="0.6", variant=variant,
    ))
    if variant in ("minimal", "docsfirst", "reference") or rng.chance(50):
        site.add_page(_page(
            profile, url="/about", file="about/index.html",
            title=f"About &mdash; {profile.brand.name}",
            description=f"About {profile.brand.company}.",
            body=render_about(profile, theme),
            priority="0.4", variant=variant,
        ))
    if rng.chance(55):
        site.add_page(_page(
            profile, url="/changelog", file="changelog/index.html",
            title=f"Changelog &mdash; {profile.brand.name}",
            description=f"Release notes for {profile.brand.product}.",
            body=render_changelog(profile),
            priority="0.3", variant=variant,
        ))

    site.files["404.html"] = build_document(
        profile.doc,
        HeadMeta(title=f"Page not found &mdash; {profile.brand.name}",
                 description="", canonical="404"),
        _header(profile, variant) + render_404(profile, variant) + _footer(profile),
        domain=profile.domain, theme_color=profile.palette.bg,
    )
    return site
