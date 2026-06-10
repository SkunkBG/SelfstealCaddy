# SelfSteal Mem

Single-command installer of a **SelfSteal** stub backend for [Remnawave](https://github.com/remnawave) + Xray Reality nodes.

It installs [Caddy](https://caddyserver.com/) as a local HTTPS backend serving one ordinary-looking website, so your Reality node masquerades behind **your own domain** with a valid TLS certificate — and, just as importantly, behaves like a real static site under active probing.

## How it works

```
Client (SNI: your-domain.com)
        │
        ▼
  Xray Reality (:443)            ◄── public surface, looks like normal HTTPS
        │
        ├── VPN client? ──► VPN tunnel
        │
        └── Probe/scanner? ──► proxied to 127.0.0.1:8443
                                        │
                                        ▼
                               Caddy (valid TLS cert for your-domain.com)
                                        │
                                        ▼
                                  Stub website
```

A DPI box or active prober sees a legitimate cert that matches the SNI and a perfectly ordinary website — nothing that flags as a VPN.

## What makes the stub look like a real site

The whole point of a SelfSteal page is to be unremarkable when probed. This build is tuned so that the backend is hard to distinguish from a normal static HTTPS site:

- **One clean landing page** — a light, editorial design-studio site (*Northbound*). System fonts only, all CSS inline, **zero external requests, zero JS**. It loads like plain static content and leaves no extra network traces.
- **Honest status codes** — `GET /` returns `200`; unknown paths return a real `404`. Many naive stubs answer **every** path with `200` (an SPA-style catch-all), which is a well-known SelfSteal tell. This one doesn't.
- **A complete-looking site** — ships `favicon.ico` and `robots.txt`, so a browser-like prober doesn't get a bare 404 on `/favicon.ico` or a missing `robots.txt`.
- **Normal server behavior** — `gzip`/`zstd` compression, `ETag` / `Last-Modified` from the file server, and sensible cache headers, just like a typical web host.
- **No `Server: Caddy` header** — that header is a common fingerprint of these setups, so it's stripped.
- **Clean redirect** — `http://domain` → `https://domain` (port 443, implicit). No odd `:8443` leaking into the `Location` header.

The email address on the page is auto-filled to your domain (`hello@your-domain.com`).

> **Note.** The page only protects you against *active probing* of the backend. The traffic shape your clients generate is determined by Xray Reality / your inbound settings, not by this page.

## Requirements

- Debian / Ubuntu server
- Root access
- A domain with a DNS A record pointing to the server IP
- An Xray Reality node (Remnawave or standalone)

## Install

**One command:**

```
bash <(curl -Ls https://raw.githubusercontent.com/SkunkBG/SelfStealMem/main/selfsteal-setup.sh)
```

**Or manually:**

```
curl -Lo selfsteal-setup.sh https://raw.githubusercontent.com/SkunkBG/SelfStealMem/main/selfsteal-setup.sh
bash selfsteal-setup.sh
```

The script asks only for your domain.

## What the script does

1. Asks for the domain and checks DNS resolution
2. Installs Caddy (if not already present)
3. Writes the site to `/var/www/html/` (`index.html`, `404.html`, `robots.txt`, `favicon.ico`)
4. Configures Caddy:
   - port `80` — Let's Encrypt challenge + HTTP→HTTPS redirect
   - port `8443` — HTTPS backend with a valid certificate, compression, security/cache headers, real 404s
5. Configures UFW (opens `80`, `443`; closes `8443`)
6. Validates the config, starts Caddy, and verifies that `/` → `200` and unknown paths → `404`

## After install

Update your Xray / Remnawave node — change two fields in `realitySettings`:

```
"realitySettings": {
    "target": "127.0.0.1:8443",
    "serverNames": ["your-domain.com"]
}
```

| Before                           | After                                |
| -------------------------------- | ------------------------------------ |
| `"target": "www.google.com:443"` | `"target": "127.0.0.1:8443"`         |
| `"serverNames": ["google.com"]`  | `"serverNames": ["your-domain.com"]` |

Everything else (`shortIds`, `privateKey`, routing, outbounds) stays unchanged.

## Ports

| Port   | Service       | Access                                      |
| ------ | ------------- | ------------------------------------------- |
| `443`  | Xray Reality  | Public — VPN connections                    |
| `80`   | Caddy         | Public — certificate renewal + redirect     |
| `8443` | Caddy HTTPS   | **Local only** (`127.0.0.1`)                |

## File locations

| File          | Path                         |
| ------------- | ---------------------------- |
| Landing page  | `/var/www/html/index.html`   |
| 404 page      | `/var/www/html/404.html`     |
| robots.txt    | `/var/www/html/robots.txt`   |
| favicon       | `/var/www/html/favicon.ico`  |
| Caddy config  | `/etc/caddy/Caddyfile`       |
| Config backup | `/etc/caddy/Caddyfile.bak.*` |

## Customization

Replace the page with any HTML you like:

```
nano /var/www/html/index.html
systemctl restart caddy
```

To change the *Northbound* copy (studio name, services, work list, email), edit the `index.html` heredoc block in `selfsteal-setup.sh` and re-run, or edit the file in place.

## Removal

```
systemctl stop caddy
systemctl disable caddy
apt remove caddy -y
rm -rf /var/www/html
rm -f /etc/apt/sources.list.d/caddy-stable.list
rm -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg
```

## Troubleshooting

**Caddy won't start:**

```
journalctl -u caddy --no-pager -n 30
```

**Certificate not issued:**

- Make sure port `80` is open and the DNS A record points to the server
- Check: `curl -I http://your-domain.com`

**Manual HTTPS check (local backend):**

```
curl -I https://your-domain.com:8443
curl -o /dev/null -w "%{http_code}\n" https://your-domain.com:8443/nope   # expect 404
```

## License

MIT
