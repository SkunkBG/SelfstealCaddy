"""Generation orchestrator.

Writing strategy: every file is written to a hidden sibling and atomically
renamed into place, so a reader never sees a half-written page.  The temporary
name starts with a dot because the Caddyfile 404s dotfiles: if the process is
killed mid-write, the leftover is invisible to the internet rather than being
served as a stray copy of the page.  Files no longer produced are removed --
the original installer wrote in place and never cleaned up, so switching a node
from ``coffee`` to ``studio`` left ``menu.html`` serving 200 with the previous
brand's content while the sitemap claimed it did not exist.  An internally
inconsistent site is a worse decoy than a plain one.

``dry_run`` resolves the whole installation and returns the plan without
touching the filesystem at all.  It used to write everything anyway, which made
``DRY_RUN=1`` on default paths silently replace a live Caddyfile and webroot.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from . import assets, caddyfile, favicon
from .css import build_stylesheet
from .profile import Profile
from .registry import build_site, prepare
from .themes.base import Site

MANIFEST_NAME = ".selfsteal-manifest.json"
PROFILE_NAME = ".selfsteal-profile.json"
TMP_SUFFIX = ".selfsteal-tmp"

# Pages emitted by 1.x, which kept no manifest. On upgrade there is nothing to
# diff against, so a stale page from the previous theme would keep answering
# 200 with another brand's content while being absent from the new sitemap.
LEGACY_PAGES = [
    "studio.html", "work.html", "contact.html",
    "menu.html", "about.html", "visit.html",
    "practice.html", "people.html",
    "services.html", "projects.html",
]
LEGACY_MARKERS = ["index.html", "style.css", "404.html", "sitemap.xml"]


@dataclass
class Result:
    profile: Profile
    site: Site
    webroot: Path
    caddyfile_path: Path
    caddyfile_text: str
    files_written: List[str]
    files_removed: List[str]
    dry_run: bool = False


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
        return _legacy_manifest(webroot)


def _legacy_manifest(webroot: Path) -> List[str]:
    """Synthesise a manifest for a 1.x installation being upgraded.

    Only the fixed set of filenames 1.x could produce is considered, and only
    when the directory actually looks like one of its installs. Anything the
    operator put there themselves is left alone.
    """
    if not all((webroot / name).is_file() for name in LEGACY_MARKERS):
        return []
    return [name for name in LEGACY_PAGES if (webroot / name).is_file()]


def _sweep_temp_files(webroot: Path) -> None:
    """Remove leftovers from a run that was killed between write and rename."""
    if not webroot.is_dir():
        return
    for path in webroot.rglob("*" + TMP_SUFFIX):
        try:
            if path.is_file():
                path.unlink()
        except OSError:
            pass


def _plan(webroot: Path, files: Dict[str, bytes]) -> Tuple[List[str], List[str]]:
    previous = set(_read_manifest(webroot))
    current = set(files)
    removable = sorted(
        name for name in previous - current if (webroot / name).is_file()
    )
    return sorted(current), removable


def _write_tree(webroot: Path, files: Dict[str, bytes]) -> Tuple[List[str], List[str]]:
    previous = set(_read_manifest(webroot))
    current = set(files)

    _sweep_temp_files(webroot)

    written: List[str] = []
    for name in sorted(files):
        target = webroot / name
        _make_dirs(webroot, target.parent)
        # Hidden temporary name: the Caddyfile 404s dotfiles, so an interrupted
        # run cannot leave a servable copy of a page behind.
        tmp = target.with_name("." + target.name + TMP_SUFFIX)
        tmp.write_bytes(files[name])
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)
        written.append(name)

    removed: List[str] = []
    touched: Set[Path] = set()
    for name in sorted(previous - current):
        stale = webroot / name
        # Only ever remove paths this tool previously wrote, recorded in the
        # manifest. Nothing is deleted on the basis of a glob.
        try:
            if stale.is_file():
                stale.unlink()
                removed.append(name)
                touched.add(stale.parent)
        except OSError:
            pass
    _prune_emptied_dirs(webroot, touched)

    manifest = {
        "files": sorted(current),
        "schema": 1,
    }
    _write_private(webroot / MANIFEST_NAME,
                    json.dumps(manifest, indent=2) + "\n")
    return written, removed


def _make_dirs(webroot: Path, directory: Path) -> None:
    """Create directories with an explicit mode rather than inheriting umask."""
    if directory == webroot or webroot not in directory.parents:
        directory.mkdir(parents=True, exist_ok=True)
        return
    _make_dirs(webroot, directory.parent)
    if not directory.is_dir():
        directory.mkdir(exist_ok=True)
    os.chmod(directory, 0o755)


def _write_private(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    os.chmod(path, 0o600)


def _prune_emptied_dirs(webroot: Path, touched: Set[Path]) -> None:
    """Remove directories emptied by *our own* deletions, and only those.

    The previous implementation walked the whole webroot and removed every
    empty directory it found, including ones the operator had created.  That
    contradicted the guarantee the manifest exists to provide.
    """
    for directory in sorted(touched, key=lambda p: len(p.parts), reverse=True):
        current = directory
        while current != webroot and webroot in current.parents:
            try:
                next(current.iterdir())
                break
            except StopIteration:
                pass
            except OSError:
                break
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent


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
    bind_addr: str = "127.0.0.1",
) -> Result:
    """Generate one complete installation.

    With ``dry_run`` the function is pure: it resolves the profile, renders
    every byte and reports what *would* change, without creating, modifying or
    deleting anything.
    """
    domain = caddyfile.validate_domain(domain)
    root = Path(caddyfile.validate_webroot(webroot))

    spec, profile = prepare(domain, theme, seed=seed)
    site = build_site(spec, profile)

    files = _render_files(site)

    config = caddyfile.build(
        domain=domain,
        webroot=str(root),
        endpoints=site.endpoints,
        admin_socket=admin_socket,
        https_port=https_port,
        bind_addr=bind_addr,
    )
    target = Path(caddyfile_path)

    if dry_run:
        written, removed = _plan(root, files)
        return Result(
            profile=profile,
            site=site,
            webroot=root,
            caddyfile_path=target,
            caddyfile_text=config,
            files_written=written,
            files_removed=removed,
            dry_run=True,
        )

    written, removed = _write_tree(root, files)

    if write_caddyfile:
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name("." + target.name + TMP_SUFFIX)
        tmp.write_text(config, encoding="utf-8")
        os.chmod(tmp, 0o644)
        os.replace(tmp, target)

    # The profile records the resolved identity for later inspection. It stays
    # 0600 and, unlike the manifest, never contains the seed: the seed is the
    # secret that makes a node's appearance unpredictable, and the webroot is
    # the one directory on the box that is definitionally served to strangers.
    _write_private(root / PROFILE_NAME, profile.to_public_json())

    return Result(
        profile=profile,
        site=site,
        webroot=root,
        caddyfile_path=target,
        caddyfile_text=config,
        files_written=written,
        files_removed=removed,
        dry_run=False,
    )
