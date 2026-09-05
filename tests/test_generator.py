"""Offline test suite. Standard library only, no network, no Caddy binary.

The live HTTP contract is covered separately by ``scripts/live-check.sh``,
which needs a real Caddy; everything here runs anywhere Python 3.9+ runs.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selfsteal import caddyfile, favicon, validate  # noqa: E402
from selfsteal.generator import _render_files, generate  # noqa: E402
from selfsteal.registry import REGISTRY, build_site, prepare  # noqa: E402
from selfsteal.rng import SeededRandom, seed_from  # noqa: E402

DOMAIN = "example.com"
ALL_THEMES = sorted(REGISTRY)
CLASSIC_URLS = {
    "studio": {"/", "/studio.html", "/work.html", "/contact.html"},
    "coffee": {"/", "/menu.html", "/about.html", "/visit.html"},
    "law": {"/", "/practice.html", "/people.html", "/contact.html"},
    "contractor": {"/", "/services.html", "/projects.html", "/contact.html"},
}


def render(domain=DOMAIN, theme="media-api", seed=None):
    spec, profile = prepare(domain, theme, seed=seed)
    site = build_site(spec, profile)
    return profile, site, _render_files(site)


class TestRng(unittest.TestCase):
    def test_stream_is_reproducible(self):
        a = SeededRandom("abc")
        b = SeededRandom("abc")
        self.assertEqual([a.below(1000) for _ in range(20)],
                         [b.below(1000) for _ in range(20)])

    def test_substreams_are_independent(self):
        root = SeededRandom("abc")
        first = [root.derive("x").below(1000) for _ in range(5)]
        root.below(10)  # consuming the parent must not shift the substream
        second = [root.derive("x").below(1000) for _ in range(5)]
        self.assertEqual(first, second)

    def test_below_is_unbiased_enough(self):
        rng = SeededRandom("bias")
        counts = [0] * 7
        for _ in range(7000):
            counts[rng.below(7)] += 1
        for count in counts:
            self.assertGreater(count, 850, f"skewed distribution: {counts}")

    def test_seed_from_is_order_sensitive(self):
        self.assertNotEqual(seed_from("a", "b"), seed_from("b", "a"))


class TestDeterminism(unittest.TestCase):
    def test_same_inputs_produce_identical_bytes(self):
        _, _, first = render(theme="cdn")
        _, _, second = render(theme="cdn")
        self.assertEqual(first, second)

    def test_domain_changes_output(self):
        _, _, a = render(domain="one.example.com", theme="cdn")
        _, _, b = render(domain="two.example.com", theme="cdn")
        self.assertNotEqual(a["index.html"], b["index.html"])

    def test_explicit_seed_overrides_domain(self):
        _, _, a = render(domain="one.example.com", theme="cdn", seed="fixed-seed")
        _, _, b = render(domain="one.example.com", theme="cdn", seed="other-seed")
        self.assertNotEqual(a["index.html"], b["index.html"])

    def test_output_does_not_depend_on_the_clock(self):
        """Nothing but security.txt Expires may vary between runs."""
        _, _, first = render(theme="status")
        _, _, second = render(theme="status")
        for name in first:
            if name.endswith("security.txt"):
                continue
            self.assertEqual(first[name], second[name], f"{name} is not stable")


class TestAllThemes(unittest.TestCase):
    def test_every_theme_builds(self):
        for theme in ALL_THEMES:
            with self.subTest(theme=theme):
                profile, site, files = render(theme=theme)
                self.assertIn("index.html", files)
                self.assertIn("404.html", files)
                self.assertTrue(site.pages)

    def test_every_payload_is_valid_json(self):
        for theme in ALL_THEMES:
            with self.subTest(theme=theme):
                _, site, _ = render(theme=theme)
                for endpoint in site.endpoints:
                    json.loads(json.dumps(endpoint.payload))

    def test_technical_themes_expose_health_probes(self):
        for theme, spec in REGISTRY.items():
            if spec.kind != "technical":
                continue
            with self.subTest(theme=theme):
                _, site, _ = render(theme=theme)
                paths = set(site.api_paths)
                for probe in ("/health", "/healthz", "/ready", "/readyz"):
                    self.assertIn(probe, paths)

    def test_classic_themes_expose_no_api(self):
        """A coffee shop answering /healthz is a stronger tell than no decoy."""
        for theme, spec in REGISTRY.items():
            if spec.kind != "classic":
                continue
            with self.subTest(theme=theme):
                _, site, _ = render(theme=theme)
                self.assertEqual(site.endpoints, [])

    def test_endpoints_and_docs_agree(self):
        for theme, spec in REGISTRY.items():
            if spec.kind != "technical":
                continue
            with self.subTest(theme=theme):
                _, site, _ = render(theme=theme)
                documented = {p.url[len("/docs"):] for p in site.pages
                              if p.url.startswith("/docs/api/")}
                live = {e.path for e in site.endpoints
                        if e.path.startswith("/api/") and e.path.count("/") >= 3}
                self.assertEqual(documented, live,
                                 "documentation must describe exactly the "
                                 "endpoints that exist")

    def test_api_version_is_consistent(self):
        for theme, spec in REGISTRY.items():
            if spec.kind != "technical":
                continue
            with self.subTest(theme=theme):
                profile, site, _ = render(theme=theme)
                for endpoint in site.endpoints:
                    if endpoint.path.startswith("/api/"):
                        self.assertTrue(
                            endpoint.path.startswith(f"/api/{profile.api_version}"),
                            f"{endpoint.path} disagrees with {profile.api_version}")


class TestBackwardCompatibility(unittest.TestCase):
    def test_classic_theme_urls_are_unchanged(self):
        for theme, expected in CLASSIC_URLS.items():
            with self.subTest(theme=theme):
                _, site, files = render(theme=theme)
                self.assertEqual({p.url for p in site.pages}, expected)
                for url in expected:
                    name = "index.html" if url == "/" else url.lstrip("/")
                    self.assertIn(name, files)

    def test_legacy_theme_keys_still_resolve(self):
        for theme in ("studio", "coffee", "law", "contractor", "random"):
            with self.subTest(theme=theme):
                spec, _ = prepare(DOMAIN, theme)
                self.assertIn(spec.key, REGISTRY)


class TestSecurity(unittest.TestCase):
    def test_domain_injection_is_rejected(self):
        hostile = [
            "example.com { } :8443 { root * / }",
            "example.com\nevil.com:80 {",
            "../../etc/passwd",
            "exam ple.com",
            "",
            "-example.com",
            "example",
        ]
        for value in hostile:
            with self.subTest(value=value):
                with self.assertRaises(caddyfile.ConfigError):
                    caddyfile.validate_domain(value)

    def test_webroot_traversal_is_rejected(self):
        for value in ("/var/www/../../etc", "relative/path", "/var/www; rm -rf /"):
            with self.subTest(value=value):
                with self.assertRaises(caddyfile.ConfigError):
                    caddyfile.validate_path(value, "webroot")

    def test_generated_content_has_no_external_references(self):
        for theme in ALL_THEMES:
            with self.subTest(theme=theme):
                _, _, files = render(theme=theme)
                for name, blob in files.items():
                    if not name.endswith((".html", ".css", ".svg")):
                        continue
                    text = blob.decode("utf-8")
                    for host in validate.EXTERNAL_URL_RE.findall(text):
                        self.assertEqual(host.split(":")[0], DOMAIN,
                                         f"{name} references {host}")

    def test_generated_content_has_no_markers(self):
        for theme in ALL_THEMES:
            with self.subTest(theme=theme):
                _, _, files = render(theme=theme)
                for name, blob in files.items():
                    if name.endswith(".ico"):
                        continue
                    text = blob.decode("utf-8", "ignore")
                    self.assertIsNone(validate.MARKER_RE.search(text),
                                      f"{name} leaks an infrastructure marker")
                    self.assertIsNone(validate.SECRET_RE.search(text),
                                      f"{name} contains a credential-shaped string")

    def test_caddyfile_blocks_dotfiles_and_internal_trees(self):
        _, site, _ = render(theme="media-api")
        config = caddyfile.build(domain=DOMAIN, webroot="/var/www/html",
                                 endpoints=site.endpoints)
        self.assertIn("@dotfiles", config)
        self.assertIn("@internal", config)
        # A path matcher's * does not cross slashes, so the old
        # `path /.* /*/.* /*/*/.*` list stopped at three levels and served
        # /a/b/c/.env with a 200. Verified against Caddy 2.11.
        self.assertIn("@dotfiles path_regexp", config)
        self.assertNotIn("@dotfiles path /", config)
        # .well-known has to be handled before the dotfile refusal, or
        # security.txt and the ACME challenge would 404 with it.
        self.assertLess(config.index("@wellknown"), config.index("@dotfiles"))
        self.assertIn("-Server", config)
        # The header block must be repeated inside handle_errors, or the
        # backend identifies itself on every 404.
        errors = config.split("handle_errors {", 1)[1]
        self.assertIn("-Server", errors)

    def test_caddyfile_binds_the_backend_to_loopback(self):
        _, site, _ = render(theme="storage")
        config = caddyfile.build(domain=DOMAIN, webroot="/var/www/html",
                                 endpoints=site.endpoints)
        self.assertIn("bind 127.0.0.1", config)
        # TLS-ALPN cannot reach a loopback-bound port, so issuance must not
        # depend on it.
        self.assertIn("disable_tlsalpn_challenge", config)
        wide = caddyfile.build(domain=DOMAIN, webroot="/var/www/html",
                               endpoints=site.endpoints, bind_addr="")
        self.assertNotIn("bind ", wide)

    def test_caddyfile_does_not_enable_http3_or_admin_tcp(self):
        _, site, _ = render(theme="cdn")
        config = caddyfile.build(domain=DOMAIN, webroot="/var/www/html",
                                 endpoints=site.endpoints)
        self.assertIn("protocols h1 h2", config)
        self.assertNotIn("h3", config)
        self.assertIn("admin unix/", config)
        self.assertNotIn("localhost:2019", config)


class TestAssets(unittest.TestCase):
    def test_favicon_ico_is_a_valid_container(self):
        for theme in ALL_THEMES[:6]:
            with self.subTest(theme=theme):
                profile, _, _ = render(theme=theme)
                blob = favicon.build_ico(profile)
                self.assertEqual(blob[:4], b"\x00\x00\x01\x00")
                self.assertGreater(len(blob), 4000)

    def test_favicons_differ_across_installs(self):
        blobs = set()
        for i in range(25):
            profile, _, _ = render(domain=f"n{i}.example.com", theme="random")
            blobs.add(favicon.build_ico(profile))
        self.assertGreaterEqual(len(blobs), 20,
                                "favicon.ico must not be a fleet-wide constant")

    def test_sitemap_lists_only_real_pages(self):
        for theme in ALL_THEMES:
            with self.subTest(theme=theme):
                _, site, files = render(theme=theme)
                sitemap = files["sitemap.xml"].decode()
                urls = re.findall(r"<loc>https://[^/]+([^<]*)</loc>", sitemap)
                self.assertTrue(urls)
                page_urls = {p.url for p in site.pages}
                for url in urls:
                    self.assertIn(url, page_urls)
                    self.assertFalse(url.startswith("/api"),
                                     "API routes must not appear in the sitemap")

    def test_robots_references_the_sitemap(self):
        for theme in ALL_THEMES:
            with self.subTest(theme=theme):
                _, _, files = render(theme=theme)
                self.assertIn("Sitemap:", files["robots.txt"].decode())

    def test_security_txt_expires_in_the_future(self):
        import datetime as dt
        _, _, files = render(theme="storage")
        body = files[".well-known/security.txt"].decode()
        match = re.search(r"Expires:\s*(\d{4}-\d{2}-\d{2})", body)
        self.assertIsNotNone(match)
        self.assertGreater(dt.date.fromisoformat(match.group(1)), dt.date.today())


class TestDiversity(unittest.TestCase):
    def test_installs_do_not_share_markup(self):
        """The regression this whole release exists to prevent."""
        seen = {"index.html": set(), "style.css": set(), "404.html": set()}
        for i in range(30):
            _, _, files = render(domain=f"node{i}.example.com", theme="media-api")
            for key in seen:
                seen[key].add(files[key])
        for key, values in seen.items():
            self.assertGreaterEqual(len(values), 29,
                                    f"{key} is shared across installs")

    def test_random_mixes_classic_and_technical(self):
        kinds = set()
        for i in range(40):
            spec, _ = prepare(f"n{i}.example.com", "random")
            kinds.add(spec.kind)
        self.assertEqual(kinds, {"classic", "technical"})


class TestFilesystem(unittest.TestCase):
    def test_stale_files_are_removed_on_theme_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            generate(domain="a.example.com", theme="coffee", webroot=str(root),
                     caddyfile_path=str(config))
            self.assertTrue((root / "menu.html").exists())
            generate(domain="a.example.com", theme="studio", webroot=str(root),
                     caddyfile_path=str(config))
            self.assertFalse((root / "menu.html").exists(),
                             "a stale page from the previous theme would keep "
                             "serving 200 with another brand's content")
            self.assertTrue((root / "work.html").exists())

    def test_upgrade_from_1x_removes_its_pages(self):
        """1.x kept no manifest, so its pages would otherwise survive forever."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            root.mkdir()
            (root / ".well-known").mkdir()
            for name in ("index.html", "style.css", "404.html", "sitemap.xml",
                         "robots.txt", "studio.html", "work.html",
                         "contact.html"):
                (root / name).write_text("1.x content")
            (root / "operator-note.html").write_text("not ours")
            generate(domain=DOMAIN, theme="storage", webroot=str(root),
                     caddyfile_path=str(Path(tmp) / "Caddyfile"))
            for name in ("studio.html", "work.html", "contact.html"):
                self.assertFalse((root / name).exists(), name)
            self.assertTrue((root / "operator-note.html").exists(),
                            "files the operator put there must be left alone")

    def test_upgrade_cleanup_needs_a_1x_looking_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            root.mkdir()
            (root / "services.html").write_text("someone else's site")
            generate(domain=DOMAIN, theme="cdn", webroot=str(root),
                     caddyfile_path=str(Path(tmp) / "Caddyfile"))
            self.assertTrue((root / "services.html").exists())

    def test_generated_tree_passes_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            for theme in ALL_THEMES:
                with self.subTest(theme=theme):
                    generate(domain=DOMAIN, theme=theme, webroot=str(root),
                             caddyfile_path=str(config))
                    report = validate.check_tree(root, DOMAIN)
                    self.assertTrue(report.ok(), "\n".join(report.failures))

    def test_reinstall_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            generate(domain=DOMAIN, theme="platform", webroot=str(root),
                     caddyfile_path=str(config))
            before = {p.relative_to(root).as_posix(): p.read_bytes()
                      for p in root.rglob("*") if p.is_file()
                      and "security.txt" not in p.name}
            generate(domain=DOMAIN, theme="platform", webroot=str(root),
                     caddyfile_path=str(config))
            after = {p.relative_to(root).as_posix(): p.read_bytes()
                     for p in root.rglob("*") if p.is_file()
                     and "security.txt" not in p.name}
            self.assertEqual(before, after)


class TestDryRun(unittest.TestCase):
    """``--dry-run`` used to write the entire tree and the Caddyfile anyway.

    On default paths that silently replaced a live installation, and without a
    backup: the backup is taken by the apply step, which a dry run skips.
    """

    def test_dry_run_touches_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            generate(domain=DOMAIN, theme="cdn", webroot=str(root),
                     caddyfile_path=str(config), dry_run=True)
            self.assertFalse(root.exists(), "dry run created the webroot")
            self.assertFalse(config.exists(), "dry run wrote the Caddyfile")

    def test_dry_run_does_not_disturb_an_existing_install(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            generate(domain=DOMAIN, theme="coffee", webroot=str(root),
                     caddyfile_path=str(config))
            before = {p.relative_to(root).as_posix(): p.read_bytes()
                      for p in root.rglob("*") if p.is_file()}
            config_before = config.read_bytes()
            generate(domain=DOMAIN, theme="cdn", webroot=str(root),
                     caddyfile_path=str(config), dry_run=True)
            after = {p.relative_to(root).as_posix(): p.read_bytes()
                     for p in root.rglob("*") if p.is_file()}
            self.assertEqual(before, after)
            self.assertEqual(config_before, config.read_bytes())

    def test_dry_run_still_reports_the_real_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            generate(domain=DOMAIN, theme="coffee", webroot=str(root),
                     caddyfile_path=str(config))
            plan = generate(domain=DOMAIN, theme="studio", webroot=str(root),
                            caddyfile_path=str(config), dry_run=True)
            self.assertTrue(plan.dry_run)
            self.assertIn("index.html", plan.files_written)
            self.assertIn("menu.html", plan.files_removed,
                          "the plan must name the stale pages it would delete")
            self.assertTrue((root / "menu.html").exists(),
                            "planning to remove a file is not removing it")


class TestWebrootGuard(unittest.TestCase):
    """The webroot is chowned recursively and pruned, so a system path here is
    destructive in a way no later check can undo."""

    def test_system_directories_are_refused(self):
        for bad in ("/", "/etc", "/usr", "/var", "/home", "/root", "/boot"):
            with self.subTest(webroot=bad):
                with self.assertRaises(caddyfile.ConfigError):
                    caddyfile.validate_webroot(bad)

    def test_top_level_directories_are_refused(self):
        with self.assertRaises(caddyfile.ConfigError):
            caddyfile.validate_webroot("/srv2")

    def test_a_real_webroot_is_accepted(self):
        self.assertEqual(caddyfile.validate_webroot("/var/www/html/"),
                         "/var/www/html")

    def test_generate_refuses_a_system_webroot(self):
        with self.assertRaises(caddyfile.ConfigError):
            generate(domain=DOMAIN, theme="cdn", webroot="/etc",
                     caddyfile_path="/tmp/ignored", dry_run=True)


class TestConfigInputValidation(unittest.TestCase):
    """Domain and webroot were validated; everything else was interpolated raw."""

    def test_admin_socket_cannot_inject_directives(self):
        with self.assertRaises(caddyfile.ConfigError):
            caddyfile.validate_socket("/run/caddy/admin.sock\n\tauto_https off")

    def test_bind_address_must_be_an_ip_literal(self):
        for bad in ("0.0.0.0 evil", "127.0.0.1\n}", "999.1.1.1", "localhost"):
            with self.subTest(bind=bad):
                with self.assertRaises(caddyfile.ConfigError):
                    caddyfile.validate_bind(bad)
        self.assertEqual(caddyfile.validate_bind("127.0.0.1"), "127.0.0.1")
        self.assertEqual(caddyfile.validate_bind(""), "",
                         "an empty bind is meaningful: listen on all interfaces")

    def test_ports_must_be_in_range(self):
        for bad in (0, 65536, "http", None):
            with self.subTest(port=bad):
                with self.assertRaises(caddyfile.ConfigError):
                    caddyfile.validate_port(bad, "https port")

    def test_backend_and_public_port_must_differ(self):
        _, site, _ = render(theme="cdn")
        with self.assertRaises(caddyfile.ConfigError):
            caddyfile.build(domain=DOMAIN, webroot="/var/www/html",
                            endpoints=site.endpoints, https_port=80,
                            http_port=80)


class TestPublicHttpSurface(unittest.TestCase):
    """:80 is the only Caddy listener reachable from the internet.

    It used to answer ``Server: Caddy`` on every request while the backend
    behind it went to some trouble to strip exactly that header.
    """

    def _http_block(self, **kwargs):
        _, site, _ = render(theme="cdn")
        text = caddyfile.build(domain=DOMAIN, webroot="/var/www/html",
                               endpoints=site.endpoints, **kwargs)
        start = text.index(f"{DOMAIN}:80 {{")
        return text[start:text.index("\n}\n", start)]

    def test_redirect_block_strips_the_server_header(self):
        block = self._http_block()
        self.assertIn("-Server", block)
        self.assertIn("-Alt-Svc", block)

    def test_redirect_never_leaks_the_backend_port(self):
        block = self._http_block(https_port=8443)
        self.assertIn(f"redir https://{DOMAIN}", block)
        self.assertNotIn(":8443", block.split("redir", 1)[1])

    def test_automatic_redirects_are_disabled(self):
        """Caddy prepends its own 308 redirect ahead of the :80 block.

        It carries ``Server: Caddy`` and, because https_port is not 443, writes
        the backend port into Location -- undoing both guarantees this block
        exists to provide.
        """
        _, site, _ = render(theme="cdn")
        text = caddyfile.build(domain=DOMAIN, webroot="/var/www/html",
                               endpoints=site.endpoints)
        self.assertIn("auto_https disable_redirects", text)

    def test_probes_assert_the_redirect_contract(self):
        probes = validate.public_http_probes(DOMAIN, 8443)
        self.assertTrue(probes)
        for probe in probes:
            self.assertEqual(probe.status, 301)
            self.assertEqual(probe.location_prefix, f"https://{DOMAIN}")


class TestSecretHandling(unittest.TestCase):
    def test_profile_on_disk_carries_no_seed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            generate(domain=DOMAIN, theme="cdn", webroot=str(root),
                     caddyfile_path=str(Path(tmp) / "Caddyfile"),
                     seed="a-secret-node-seed")
            data = json.loads((root / ".selfsteal-profile.json").read_text())
            self.assertNotIn("seed", data)
            self.assertIn("seed_id", data)
            self.assertNotIn("a-secret-node-seed",
                             (root / ".selfsteal-profile.json").read_text())

    def test_seed_id_is_stable_and_not_the_seed(self):
        _, first = prepare(DOMAIN, "cdn", seed="s")
        _, again = prepare(DOMAIN, "cdn", seed="s")
        _, other = prepare(DOMAIN, "cdn", seed="t")
        self.assertEqual(first.seed_id, again.seed_id)
        self.assertNotEqual(first.seed_id, other.seed_id)
        self.assertNotIn(first.seed_id, "s")


class TestCleanupScope(unittest.TestCase):
    def test_only_directories_we_emptied_are_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            generate(domain=DOMAIN, theme="cdn", webroot=str(root),
                     caddyfile_path=str(config))
            operator = root / "operator-empty"
            operator.mkdir()
            generate(domain=DOMAIN, theme="coffee", webroot=str(root),
                     caddyfile_path=str(config))
            self.assertTrue(operator.is_dir(),
                            "an empty directory the operator created is not ours "
                            "to delete")

    def test_interrupted_writes_leave_nothing_servable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "site"
            config = Path(tmp) / "Caddyfile"
            generate(domain=DOMAIN, theme="cdn", webroot=str(root),
                     caddyfile_path=str(config))
            stale = root / ".index.html.selfsteal-tmp"
            stale.write_text("half-written page")
            generate(domain=DOMAIN, theme="cdn", webroot=str(root),
                     caddyfile_path=str(config))
            self.assertFalse(stale.exists(), "stale temp file survived a re-run")
            leftovers = [p.name for p in root.rglob("*.selfsteal-tmp")]
            self.assertEqual(leftovers, [])
            for path in root.rglob("*"):
                if path.is_file():
                    self.assertFalse(
                        path.name.endswith(".tmp") and not path.name.startswith("."),
                        f"{path.name} would be served by the file_server")


if __name__ == "__main__":
    unittest.main(verbosity=2)
