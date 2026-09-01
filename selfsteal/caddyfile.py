"""Caddyfile generation.

Design notes, because several of these are non-obvious:

* ``admin`` moves from ``off`` to a unix socket.  ``off`` removed the
  ``localhost:2019`` listener, which was the right instinct, but it also
  removed ``caddy reload`` and forced ``systemctl restart``.  A restart leaves
  a window in which the Reality ``dest`` refuses connections, and a refused
  probe is precisely the signal this project exists to suppress.  A unix
  socket keeps the listener off the network and restores zero-downtime reload.

* Header directives are repeated inside ``handle_errors``.  They are not
  inherited: the original config stripped ``Server`` on 200 responses and
  leaked ``Server: Caddy`` on every 404, so any unknown path identified the
  backend.

* Dotfiles are blocked explicitly.  Caddy's ``file_server``, unlike nginx,
  serves hidden files by default; a stray ``.env`` or ``.git`` in the webroot
  would otherwise be public.

* The JSON tree lives under ``/_api`` and is unreachable directly, so
  ``/api/v1/index.json`` 404s the way it would on a real service.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

from .themes.base import Endpoint

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)
PATH_RE = re.compile(r"^/[A-Za-z0-9._/-]*$")


class ConfigError(ValueError):
    """Raised for input that must never reach a Caddyfile."""


def validate_domain(domain: str) -> str:
    """Reject anything that could break out of the config or the markup.

    The original interpolated ``$DOMAIN`` straight into both the Caddyfile and
    the HTML, so a crafted value could append arbitrary site blocks.
    """
    value = (domain or "").strip().lower().rstrip(".")
    if not DOMAIN_RE.match(value):
        raise ConfigError(
            f"invalid domain {domain!r}: expected a hostname such as example.com"
        )
    return value


def validate_path(path: str, label: str) -> str:
    value = (path or "").strip()
    if not PATH_RE.match(value) or ".." in value:
        raise ConfigError(f"invalid {label} {path!r}: expected an absolute path")
    return value.rstrip("/") or "/"


def _matcher_list(paths: Iterable[str]) -> str:
    return " ".join(sorted(set(paths)))


def _cache_groups(endpoints: List[Endpoint]) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for endpoint in endpoints:
        groups.setdefault(endpoint.cache, []).append(endpoint.path)
    return groups


def build(
    *,
    domain: str,
    webroot: str,
    endpoints: List[Endpoint],
    admin_socket: str = "/run/caddy/admin.sock",
    https_port: int = 8443,
    http_port: int = 80,
    strip_server: bool = True,
    access_log: bool = False,
) -> str:
    domain = validate_domain(domain)
    webroot = validate_path(webroot, "webroot")

    api_paths = [e.path for e in endpoints]
    has_api = bool(api_paths)
    json_paths = list(api_paths)

    out: List[str] = []
    add = out.append

    # ---- global options ----
    add("{")
    add(f"\tadmin unix/{admin_socket}")
    add(f"\thttp_port {http_port}")
    add(f"\thttps_port {https_port}")
    add("\tservers {")
    # HTTP/3 stays off: Caddy listens on TCP only behind Reality, and
    # advertising a QUIC service that does not answer on UDP is a tell.
    add("\t\tprotocols h1 h2")
    add("\t}")
    add("}")
    add("")

    # ---- :80 — ACME plus redirect ----
    add(f"# Public :80 — ACME HTTP-01 challenge and redirect to the public 443.")
    add(f"# Never emits :{https_port} in Location: the backend port must not leak.")
    add(f"{domain}:{http_port} {{")
    add(f"\tredir https://{domain}{{uri}} permanent")
    add("}")
    add("")

    # ---- :8443 — the site itself ----
    add(f"# Local HTTPS backend. Xray Reality proxies probe traffic here.")
    add(f"{domain}:{https_port} {{")
    add(f"\troot * {webroot}")
    add("\tencode zstd gzip")
    add("")
    add("\theader {")
    if strip_server:
        add("\t\t-Server")
    add("\t\t-Alt-Svc")
    add('\t\tStrict-Transport-Security "max-age=31536000; includeSubDomains"')
    add('\t\tX-Content-Type-Options "nosniff"')
    add('\t\tX-Frame-Options "SAMEORIGIN"')
    add('\t\tReferrer-Policy "strict-origin-when-cross-origin"')
    add("\t}")
    add("")

    # ---- internal trees ----
    add("\t# Backing stores for the API and error routes: never directly reachable.")
    add("\t@internal path /_api /_api/* /_err /_err/*")
    add("\thandle @internal {")
    add("\t\terror 404")
    add("\t}")
    add("")

    # ---- dotfiles ----
    add("\t# Caddy serves hidden files by default; only .well-known is public.")
    add("\t@wellknown path /.well-known/*")
    add("\thandle @wellknown {")
    add('\t\theader Cache-Control "public, max-age=3600"')
    add("\t\tfile_server")
    add("\t}")
    add("")
    add("\t@dotfiles path /.* /*/.* /*/*/.*")
    add("\thandle @dotfiles {")
    add("\t\terror 404")
    add("\t}")
    add("")

    if has_api:
        add("\t# Public machine-readable status, the convention real status pages use.")
        add("\t# Routed explicitly rather than through the API rewrite, because its")
        add("\t# public path already carries the .json suffix.")
        add("\t@statusjson path /status.json")
        add("\thandle @statusjson {")
        add('\t\theader Content-Type "application/json; charset=utf-8"')
        add('\t\theader Cache-Control "no-store"')
        add("\t\trewrite * /_api/status.json")
        add("\t\tfile_server")
        add("\t}")
        add("")
        add("\t# JSON surface: honest method semantics, JSON errors, no runtime.")
        add(f"\t@api path {_matcher_list(json_paths)}")
        add("\thandle @api {")
        add("\t\t@write not method GET HEAD OPTIONS")
        add("\t\thandle @write {")
        add('\t\t\theader Content-Type "application/json; charset=utf-8"')
        add('\t\t\theader Allow "GET, HEAD, OPTIONS"')
        add('\t\t\theader Cache-Control "no-store"')
        add("\t\t\trespond `{\"error\":{\"code\":\"method_not_allowed\","
            "\"message\":\"The requested method is not supported.\"}}` 405")
        add("\t\t}")
        add("")
        add("\t\t@options method OPTIONS")
        add("\t\thandle @options {")
        add('\t\t\theader Allow "GET, HEAD, OPTIONS"')
        add('\t\t\trespond "" 204')
        add("\t\t}")
        add("")
        add("\t\thandle {")
        add('\t\t\theader Content-Type "application/json; charset=utf-8"')
        for cache_value, paths in sorted(_cache_groups(endpoints).items()):
            safe = f"cache_{re.sub('[^a-z0-9]+', '_', cache_value.lower()).strip('_')}"
            add(f"\t\t\t@{safe} path {_matcher_list(paths)}")
            add(f'\t\t\theader @{safe} Cache-Control "{cache_value}"')
        add("\t\t\trewrite * /_api{path}")
        add("\t\t\ttry_files {path}.json {path}/index.json")
        add("\t\t\tfile_server")
        add("\t\t}")
        add("\t}")
        add("")

    # ---- long-lived static assets ----
    add("\t# Fingerprinted-in-practice assets: cache hard, like a real host.")
    add("\t@assets path /style.css /favicon.svg /favicon.ico /robots.txt")
    add("\thandle @assets {")
    add('\t\theader Cache-Control "public, max-age=86400"')
    add("\t\tfile_server")
    add("\t}")
    add("")

    # ---- HTML ----
    add("\thandle {")
    add('\t\theader Cache-Control "public, max-age=300"')
    add("\t\ttry_files {path} {path}/index.html {path}.html")
    add("\t\tfile_server")
    add("\t}")
    add("")

    # ---- errors ----
    add("\t# handle_errors is a separate route: headers are NOT inherited from")
    add("\t# the block above, so the hardening has to be repeated here.")
    add("\thandle_errors {")
    add("\t\theader {")
    if strip_server:
        add("\t\t\t-Server")
    add("\t\t\t-Alt-Svc")
    add('\t\t\tX-Content-Type-Options "nosniff"')
    add('\t\t\tReferrer-Policy "strict-origin-when-cross-origin"')
    add("\t\t}")
    if has_api:
        add("")
        add("\t\t# Errors under the API surface answer in JSON, like the API does.")
        add("\t\t@apierr path /api /api/* /health /healthz /ready /readyz /status.json")
        add("\t\thandle @apierr {")
        add('\t\t\theader Content-Type "application/json; charset=utf-8"')
        add('\t\t\theader Cache-Control "no-store"')
        add("\t\t\trewrite * /_err/404.json")
        add("\t\t\tfile_server {")
        add("\t\t\t\tstatus {err.status_code}")
        add("\t\t\t}")
        add("\t\t}")
    add("")
    add("\t\thandle {")
    add("\t\t\trewrite * /404.html")
    add("\t\t\tfile_server {")
    add("\t\t\t\tstatus {err.status_code}")
    add("\t\t\t}")
    add("\t\t}")
    add("\t}")

    if access_log:
        add("")
        add("\tlog {")
        add("\t\toutput discard")
        add("\t}")

    add("}")
    return "\n".join(out) + "\n"
