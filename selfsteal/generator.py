"""Generation orchestrator.

Writing strategy: the tree is built in a sibling temporary directory and moved
into place, and files no longer produced are removed.  The original installer
wrote in place and never cleaned up, so switching a node from ``coffee`` to
``studio`` left ``menu.html`` serving 200 with the previous brand's content
while the sitemap claimed it did not exist.  An internally inconsistent site is
a worse decoy than a plain one.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from . import assets, caddyfile, favicon
from .css import build_stylesheet
from .profile import Profile
from .registry import build_site, prepare
from .themes.base import Site

MANIFEST_NAME = ".selfsteal-manifest.json"


@dataclass
class Result:
    profile: Profile
    site: Site
    webroot: Path
    caddyfile_path: Path
    caddyfile_text: str
    files_written: List[str]
    files_removed: List[str]


def _render_files(site: Site) -> Dict[str, bytes]:
    """Flatten a Site into the exact byte content of every file."""
    profile = site.profile
    out: Dict[str, bytes] = {}

    for page in site.pages:
        out[page.file] = page.html.encode("utf-8")
    for name, text in site.files.items():
        out[name] = text.encode("utf-8")
    for name, blob in site.binaries.items():
        out[name] = blob

    if "style.css" not in out:
        out["style.css"] = build_stylesheet(profile).encode("utf-8")

    out["favicon.svg"] = favicon.build_svg(profile).encode("utf-8")
    out["favicon.ico"] = favicon.build_ico(profile)

    has_api = bool(site.endpoints)
    out["sitemap.xml"] = assets.build_sitemap(profile, site.pages).encode("utf-8")
    out["robots.txt"] = assets.build_robots(profile, has_api).encode("utf-8")
    out[".well-known/security.txt"] = assets.build_security_txt(
        profile, _dt.date.today()
    ).encode("utf-8")

    for endpoint in site.endpoints:
        body = json.dumps(endpoint.payload, indent=2) + "\n"
        target = f"_api{endpoint.path}"
        # ``/api/v1`` needs a directory index because ``/api/v1/media`` also
        # exists; a bare ``.json`` sibling would work too, but try_files
        # resolves the index form for both shapes.
        if any(other.path.startswith(endpoint.path + "/")
               for other in site.endpoints):
            target += "/index.json"
        else:
            target += ".json"
        out[target] = body.encode("utf-8")

    # /status.json is routed through the API handler, so its body lives in the
    # internal tree like every other JSON document.
    status_ep = next((e for e in site.endpoints if e.path.endswith("/status")), None)
    if status_ep is not None:
        out["_api/status.json"] = (
            json.dumps(status_ep.payload, indent=2) + "\n"
        ).encode()

    for name, text in assets.api_error_documents().items():
        out[name] = text.encode("utf-8")

    return out


def _read_manifest(webroot: Path) -> List[str]:
    path = webroot / MANIFEST_NAME
    try:
        data = json.loads(path.read_text("utf-8"))
        return [str(x) for x in data.get("files", [])]
    except (OSError, ValueError):
        return []


def _write_tree(webroot: Path, files: Dict[str, bytes],
                dry_run: bool) -> tuple:
    previous = set(_read_manifest(webroot))
    current = set(files)

    if dry_run:
        webroot.mkdir(parents=True, exist_ok=True)

    written: List[str] = []
    for name in sorted(files):
        target = webroot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(files[name])
        os.replace(tmp, target)
        os.chmod(target, 0o644)
        written.append(name)

    removed: List[str] = []
    for name in sorted(previous - current):
        stale = webroot / name
        # Only ever remove paths this tool previously wrote, recorded in the
        # manifest. Nothing is deleted on the basis of a glob.
        try:
            if stale.is_file():
                stale.unlink()
                removed.append(name)
        except OSError:
            pass
    _prune_empty_dirs(webroot)

    manifest = {
        "files": sorted(current),
        "schema": 1,
    }
    (webroot / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    os.chmod(webroot / MANIFEST_NAME, 0o600)
    return written, removed


def _prune_empty_dirs(root: Path) -> None:
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            try:
                next(path.iterdir())
            except StopIteration:
                try:
                    path.rmdir()
                except OSError:
                    pass
            except OSError:
                pass


def generate(
    *,
    domain: str,
    theme: str = "random",
    webroot: str = "/var/www/html",
    caddyfile_path: str = "/etc/caddy/Caddyfile",
    seed: Optional[str] = None,
    dry_run: bool = False,
    write_caddyfile: bool = True,
    admin_socket: str = "/run/caddy/admin.sock",
    https_port: int = 8443,
) -> Result:
    """Generate one complete installation.  Pure apart from filesystem writes."""
    domain = caddyfile.validate_domain(domain)
    root = Path(caddyfile.validate_path(webroot, "webroot"))

    spec, profile = prepare(domain, theme, seed=seed)
    site = build_site(spec, profile)

    files = _render_files(site)
    written, removed = _write_tree(root, files, dry_run)

    config = caddyfile.build(
        domain=domain,
        webroot=str(root),
        endpoints=site.endpoints,
        admin_socket=admin_socket,
        https_port=https_port,
    )
    target = Path(caddyfile_path)
    if write_caddyfile:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".selfsteal.tmp")
        tmp.write_text(config, encoding="utf-8")
        os.replace(tmp, target)

    profile_path = root / MANIFEST_NAME
    (root / ".selfsteal-profile.json").write_text(profile.to_json(), encoding="utf-8")
    os.chmod(root / ".selfsteal-profile.json", 0o600)

    return Result(
        profile=profile,
        site=site,
        webroot=root,
        caddyfile_path=target,
        caddyfile_text=config,
        files_written=written,
        files_removed=removed,
    )
