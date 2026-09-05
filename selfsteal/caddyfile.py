"""Caddyfile generation.

Design notes, because several of these are non-obvious:

* ``admin`` moves from ``off`` to a unix socket.  ``off`` removed the
  ``localhost:2019`` listener, which was the right instinct, but it also
  removed ``caddy reload`` and forced ``systemctl restart``.  A restart leaves
  a window in which the Reality ``dest`` refuses connections, and a refused
  probe is precisely the signal this project exists to suppress.  A unix
  socket keeps the listener off the network and restores zero-downtime reload.

* Header directives are repeated in every route that can answer a request.
  They are not inherited: the original config stripped ``Server`` on the
  backend's 200 responses and leaked ``Server: Caddy`` on every 404 *and* on
  the public :80 redirect, which is the only Caddy surface reachable from the
  internet.

* Dotfiles are blocked explicitly.  Caddy's ``file_server``, unlike nginx,
  serves hidden files by default; a stray ``.env`` or ``.git`` in the webroot
  would otherwise be public.

* The JSON tree lives under ``/_api`` and is unreachable directly, so
  ``/api/v1/index.json`` 404s the way it would on a real service.

Everything interpolated into the output is validated first.  The values come
from the operator's environment rather than from the network, but a config
generator that trusts *any* of its inputs unchecked is one copy-paste away
from being wrong.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

from .themes.base import Endpoint

DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))+$"
)
PATH_RE = re.compile(r"^/[A-Za-z0-9._/-]*$")
IPV4_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
IPV6_RE = re.compile(r"^[0-9A-Fa-f:]+$")

# A webroot is about to be chowned recursively and served to the internet.
# These are the paths where getting it wrong is unrecoverable rather than
# merely wrong: a stray WEBROOT=/etc turns /etc/shadow world-readable.
FORBIDDEN_WEBROOTS = frozenset({
    "/", "/bin", "/boot", "/dev", "/etc", "/home", "/lib", "/lib32", "/lib64",
    "/media", "/mnt", "/opt", "/proc", "/root", "/run", "/sbin", "/srv",
    "/sys", "/tmp", "/usr", "/var",
})


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


def validate_webroot(path: str) -> str:
    """A webroot must be a directory this tool can own outright.

    The installer chowns it recursively and the generator prunes empty
    directories inside it, so a system path here is destructive in a way no
    later check can undo.  Requiring at least two components also rules out
    the single-segment top-level directories a typo produces.
    """
    value = validate_path(path, "webroot")
    if value in FORBIDDEN_WEBROOTS or value.rstrip("/") in FORBIDDEN_WEBROOTS:
        raise ConfigError(
            f"refusing to use {value!r} as a webroot: it is a system directory "
            f"that would be chowned and pruned recursively"
        )
    if len([p for p in value.split("/") if p]) < 2:
        raise ConfigError(
            f"refusing to use {value!r} as a webroot: expected a dedicated "
            f"directory such as /var/www/html, not a top-level one"
        )
    return value


def validate_socket(path: str) -> str:
    """The admin socket path is interpolated into the global options block."""
    return validate_path(path, "admin socket")


def validate_bind(addr: str) -> str:
    """An empty value is meaningful: it means 'do not emit a bind directive'."""
    value = (addr or "").strip()
    if not value:
        return ""
    if IPV4_RE.match(value):
        if any(int(part) > 255 for part in value.split(".")):
            raise ConfigError(f"invalid bind address {addr!r}")
        return value
    if ":" in value and IPV6_RE.match(value):
        return value
    raise ConfigError(
        f"invalid bind address {addr!r}: expected an IP literal or an empty string"
    )


def validate_port(port, label: str) -> int:
    try:
        value = int(port)
    except (TypeError, ValueError):
        raise ConfigError(f"invalid {label} {port!r}: expected an integer") from None
    if not 1 <= value <= 65535:
        raise ConfigError(f"invalid {label} {value}: expected 1-65535")
    return value


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
    bind_addr: str = "127.0.0.1",
) -> str:
    domain = validate_domain(domain)
    webroot = validate_webroot(webroot)
    admin_socket = validate_socket(admin_socket)
    bind_addr = validate_bind(bind_addr)
    https_port = validate_port(https_port, "https port")
    http_port = validate_port(http_port, "http port")
    if https_port == http_port:
        raise ConfigError("https port and http port must differ")

    api_paths = [e.path for e in endpoints]
    has_api = bool(api_paths)
    json_paths = list(api_paths)

    out: List[str] = []
    add = out.append

    # ---- global options ----
    add("{")
    add(f"\tadmin unix/{admin_socket}")
    # Caddy installs its own HTTP->HTTPS redirect for every host it serves over
    # HTTPS, and prepends it ahead of the :80 site block below. That redirect is
    # a 308 that carries `Server: Caddy` and, because https_port is not 443,
    # spells the backend port out in Location: `https://domain:8443/`. The whole
    # point of the block below is that neither of those reaches a prober, so the
    # automatic one is turned off. Certificate management is untouched -- only
    # the redirect routes are.
    add("\tauto_https disable_redirects")
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
    add("# Public :80 — ACME HTTP-01 challenge and redirect to the public 443.")
    add("# This is the ONLY Caddy surface reachable from the internet, so it")
    add("# carries the same identity stripping as the backend: a redirect that")
    add("# answers `Server: Caddy` identifies the stack to anyone running curl.")
    add(f"# Never emits :{https_port} in Location: the backend port must not leak.")
    add(f"{domain}:{http_port} {{")
    add("\theader {")
    if strip_server:
        add("\t\t-Server")
    add("\t\t-Alt-Svc")
    add("\t}")
    # No handle_errors here on purpose: redir carries no matcher, so every
    # request to this listener is answered by it and there is no error path to
    # harden. The backend block below is the one that needs the repetition.
    add(f"\tredir https://{domain}{{uri}} permanent")
    add("}")
    add("")

    # ---- :8443 — the site itself ----
    add("# Local HTTPS backend. Xray Reality proxies probe traffic here.")
    add(f"{domain}:{https_port} {{")
    if bind_addr:
        # Only Xray needs to reach the backend. Binding to loopback makes that
        # structural rather than a firewall rule that might be absent.
        add(f"\tbind {bind_addr}")
    add(f"\troot * {webroot}")
    if bind_addr and bind_addr.startswith("127."):
        # TLS-ALPN would be attempted on the backend port, which is now
        # unreachable from outside. Pinning HTTP-01 avoids a pointless retry
        # cycle on every certificate issuance and renewal.
        add("\ttls {")
        add("\t\tissuer acme {")
        add("\t\t\tdisable_tlsalpn_challenge")
        add("\t\t}")
        add("\t}")
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
    # A path matcher's * does not cross slashes, so the old
    # `path /.* /*/.* /*/*/.*` list only covered three levels: a file at
    # /a/b/c/.env was served with a 200. path_regexp has no depth limit --
    # anything with a dot-segment anywhere in the path is refused.
    add("\t@dotfiles path_regexp /\\.")
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
