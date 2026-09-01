"""Non-HTML site assets.

Two rules govern this module.  First, the sitemap describes only pages that
actually exist and return 200 — a sitemap listing API routes or absent URLs is
a self-inflicted inconsistency that a crawler (or a reviewer) notices
immediately.  Second, nothing here may encode the installation timestamp: the
original emitted ``lastmod`` equal to the install date on every URL, which both
dated the node and made all pages look modified in the same second forever.
"""

from __future__ import annotations

import datetime as _dt
from typing import List

from .themes.base import Page, Site
from .profile import Profile


def build_sitemap(profile: Profile, pages: List[Page]) -> str:
    rng = profile.rng.derive("sitemap")
    release = _dt.date.fromisoformat(profile.release)
    verbose = rng.chance(55)   # some sitemaps carry changefreq/priority, some don't
    pretty = rng.chance(70)

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in sorted(pages, key=lambda p: p.url):
        if not page.in_sitemap:
            continue
        lastmod = (release - _dt.timedelta(days=rng.between(0, 240))).isoformat()
        parts = [f"<loc>https://{profile.domain}{page.url}</loc>",
                 f"<lastmod>{lastmod}</lastmod>"]
        if verbose:
            parts.append(f"<changefreq>{page.changefreq}</changefreq>")
            parts.append(f"<priority>{page.priority}</priority>")
        if pretty:
            lines.append("  <url>")
            lines.extend(f"    {p}" for p in parts)
            lines.append("  </url>")
        else:
            lines.append("  <url>" + "".join(parts) + "</url>")
    lines.append("</urlset>")
    return "\n".join(lines) + "\n"


def build_robots(profile: Profile, has_api: bool) -> str:
    rng = profile.rng.derive("robots")
    lines = ["User-agent: *"]
    if has_api:
        # Real API hosts keep crawlers off the JSON surface but leave the
        # documentation indexable.
        lines.append("Disallow: /api/")
        if rng.chance(45):
            lines.append("Disallow: /health")
        if rng.chance(35):
            lines.append("Allow: /docs")
    else:
        lines.append("Allow: /")
    if rng.chance(30):
        lines.append(f"Crawl-delay: {rng.choice([1, 2, 5, 10])}")
    lines.append("")
    lines.append(f"Sitemap: https://{profile.domain}/sitemap.xml")
    return "\n".join(lines) + "\n"


def build_security_txt(profile: Profile, today: _dt.date) -> str:
    """RFC 9116 security.txt.

    ``Expires`` must be in the future or the file is invalid, so this is the
    one field that legitimately depends on the clock.  It is snapped to a
    month boundary plus a seed-derived offset, so the value does not disclose
    the installation date and two nodes installed the same day do not share it.
    """
    rng = profile.rng.derive("securitytxt")
    target = today.replace(day=1) + _dt.timedelta(days=395)
    expires = target.replace(day=1) + _dt.timedelta(days=rng.between(0, 27))
    lines = [
        f"Contact: mailto:{profile.security_email}",
        f"Expires: {expires.isoformat()}T00:00:00.000Z",
        f"Preferred-Languages: {rng.choice(['en', 'en', 'en, de', 'en, nl'])}",
    ]
    if rng.chance(55):
        lines.append(f"Canonical: https://{profile.domain}/.well-known/security.txt")
    return "\n".join(lines) + "\n"


def api_error_documents() -> dict:
    """Static error bodies served by the Caddy error routes."""
    return {
        "_err/404.json": (
            '{\n'
            '  "error": {\n'
            '    "code": "not_found",\n'
            '    "message": "The requested resource was not found."\n'
            '  }\n'
            '}\n'
        ),
        "_err/500.json": (
            '{\n'
            '  "error": {\n'
            '    "code": "internal_error",\n'
            '    "message": "The request could not be completed."\n'
            '  }\n'
            '}\n'
        ),
    }
