"""Command line interface.

The bash installer shells out to exactly these subcommands, so the Python side
stays independently testable and the installer stays readable.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import validate as validation
from .caddyfile import ConfigError
from .generator import generate
from .registry import REGISTRY, known_themes, prepare


def _summary(result) -> str:
    p = result.profile
    lines = [
        f"Theme:       {p.theme} ({p.kind})",
        f"Variant:     {p.variant}",
        f"Service:     {p.brand.product}",
        f"Company:     {p.brand.company}",
        f"Brand:       {p.brand.name}",
        f"API version: {p.api_version if p.endpoints else '-'}",
        f"Region:      {p.region.city} ({p.region.pop}, {p.region.zone})",
        f"Palette:     {p.palette.accent} on {p.palette.bg}",
        f"Seed id:     {p.seed_id}",
        f"Pages:       {len(p.pages)}  " + " ".join(sorted(p.pages)[:8]) +
        ("  ..." if len(p.pages) > 8 else ""),
        f"Endpoints:   {len(p.endpoints)}  " + " ".join(sorted(p.endpoints)[:8]) +
        ("  ..." if len(p.endpoints) > 8 else ""),
        f"Webroot:     {result.webroot}",
        f"Caddyfile:   {result.caddyfile_path}",
        f"Files:       {len(result.files_written)} "
        f"{'planned' if result.dry_run else 'written'}, "
        f"{len(result.files_removed)} "
        f"{'to remove' if result.dry_run else 'removed'}",
    ]
    if result.dry_run:
        lines.append("Dry run:     nothing was written to disk")
    return "\n".join(lines)


def _seed_from(args: argparse.Namespace) -> Optional[str]:
    """Prefer the environment over argv.

    A seed passed as ``--seed`` is visible in ``ps`` to every local user and
    lands in the shell trace under DEBUG=1.  Since the seed is what keeps a
    node's appearance unpredictable, it is handled like any other secret.
    """
    return args.seed or os.environ.get("SELFSTEAL_SEED") or None


def cmd_generate(args: argparse.Namespace) -> int:
    result = generate(
        domain=args.domain,
        theme=args.theme,
        webroot=args.webroot,
        caddyfile_path=args.caddyfile,
        seed=_seed_from(args),
        dry_run=args.dry_run,
        https_port=args.https_port,
        admin_socket=args.admin_socket,
        bind_addr=args.bind,
    )
    if args.json:
        print(json.dumps({
            "profile": result.profile.to_public_dict(),
            "webroot": str(result.webroot),
            "caddyfile": str(result.caddyfile_path),
            "written": result.files_written,
            "removed": result.files_removed,
        }, indent=2))
    else:
        print(_summary(result))
    return 0


def cmd_themes(args: argparse.Namespace) -> int:
    if args.json:
        print(json.dumps({
            key: {"label": spec.label, "kind": spec.kind,
                  "description": spec.description, "variants": spec.variants}
            for key, spec in sorted(REGISTRY.items())
        }, indent=2))
        return 0
    width = max(len(k) for k in REGISTRY)
    for key, spec in sorted(REGISTRY.items(), key=lambda kv: (kv[1].kind, kv[0])):
        print(f"{key:<{width}}  {spec.kind:<9}  {spec.description}")
    print()
    print("meta: random, technical, classic")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    report = validation.check_tree(Path(args.webroot), args.domain)
    if args.base_url:
        profile_path = Path(args.webroot) / ".selfsteal-profile.json"
        endpoints: List[str] = []
        pages: List[str] = []
        if profile_path.exists():
            data = json.loads(profile_path.read_text("utf-8"))
            endpoints = data.get("endpoints", [])
            pages = data.get("pages", [])
        report.merge(validation.check_live(
            args.base_url, validation.default_probes(endpoints, pages),
            connect_addr=args.connect))
    if args.http_url:
        report.merge(validation.check_live(
            args.http_url,
            validation.public_http_probes(args.domain, args.https_port),
            connect_addr=args.connect))

    for failure in report.failures:
        print(f"FAIL  {failure}", file=sys.stderr)
    for warning in report.warnings:
        print(f"WARN  {warning}", file=sys.stderr)
    print(f"{report.checks} checks, {len(report.failures)} failed, "
          f"{len(report.warnings)} warnings")
    return 0 if report.ok() else 1


def cmd_plan(args: argparse.Namespace) -> int:
    spec, profile = prepare(args.domain, args.theme, seed=_seed_from(args))
    print(json.dumps(profile.to_public_dict(), indent=2))
    return 0


def cmd_paths(args: argparse.Namespace) -> int:
    """Validate everything the installer will interpolate or chown.

    The installer runs this before it touches apt, DNS or systemd, so a bad
    WEBROOT fails on a box that is still exactly as it was found.  Keeping the
    rules in one place means the shell and the generator cannot drift apart.
    """
    from .caddyfile import (validate_bind, validate_domain, validate_path,
                            validate_port, validate_socket, validate_webroot)
    validate_domain(args.domain)
    validate_webroot(args.webroot)
    validate_path(args.caddyfile, "caddyfile path")
    validate_socket(args.admin_socket)
    validate_bind(args.bind)
    validate_port(args.https_port, "https port")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="selfsteal",
        description="Generate a self-contained technical web service for a "
                    "Caddy-backed host.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="generate a site and Caddyfile")
    gen.add_argument("--domain", required=True)
    gen.add_argument("--theme", default="random",
                     help=f"one of: {', '.join(known_themes())}")
    gen.add_argument("--webroot", default="/var/www/html")
    gen.add_argument("--caddyfile", default="/etc/caddy/Caddyfile")
    gen.add_argument("--seed", default=None,
                     help="override the installation seed; prefer the "
                          "SELFSTEAL_SEED environment variable, which does not "
                          "expose the value through ps")
    gen.add_argument("--https-port", type=int, default=8443)
    gen.add_argument("--admin-socket", default="/run/caddy/admin.sock")
    gen.add_argument("--bind", default="127.0.0.1",
                     help="address the backend listens on; empty string binds "
                          "all interfaces")
    gen.add_argument("--dry-run", action="store_true")
    gen.add_argument("--json", action="store_true")
    gen.set_defaults(func=cmd_generate)

    themes = sub.add_parser("themes", help="list available themes")
    themes.add_argument("--json", action="store_true")
    themes.set_defaults(func=cmd_themes)

    val = sub.add_parser("validate", help="validate a generated tree")
    val.add_argument("--webroot", required=True)
    val.add_argument("--domain", required=True)
    val.add_argument("--base-url", default=None,
                     help="also run live HTTP probes against this base URL")
    val.add_argument("--https-port", type=int, default=8443,
                     help="backend port that must never appear in a redirect")
    val.add_argument("--http-url", default=None,
                     help="also probe the public :80 listener at this base URL "
                          "(redirect contract and identity headers)")
    val.add_argument("--connect", default=None,
                     help="dial this address instead of resolving the base URL "
                          "host, while still sending its SNI and Host header "
                          "(e.g. 127.0.0.1 for a loopback-bound backend)")
    val.set_defaults(func=cmd_validate)

    paths = sub.add_parser(
        "paths", help="validate installer paths and addresses, then exit")
    paths.add_argument("--domain", required=True)
    paths.add_argument("--webroot", required=True)
    paths.add_argument("--caddyfile", required=True)
    paths.add_argument("--admin-socket", default="/run/caddy/admin.sock")
    paths.add_argument("--bind", default="127.0.0.1")
    paths.add_argument("--https-port", default=8443)
    paths.set_defaults(func=cmd_paths)

    plan = sub.add_parser("plan", help="resolve a profile without writing anything")
    plan.add_argument("--domain", required=True)
    plan.add_argument("--theme", default="random")
    plan.add_argument("--seed", default=None)
    plan.set_defaults(func=cmd_plan)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ConfigError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
