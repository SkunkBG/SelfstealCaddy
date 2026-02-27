# SelfSteal Caddy 404 Stub

Automated setup script for **SelfSteal** technique on [Remnawave](https://github.com/remnawave) + Xray Reality nodes.

Installs [Caddy](https://caddyserver.com/) as a local HTTPS backend with a stylish 404 stub page, so your Reality node uses **your own domain** with a valid TLS certificate instead of masquerading as someone else's site.

## How it works

```
Client (SNI: your-domain.com)
        │
        ▼
  Xray Reality (:443)
        │
        ├── VPN client? ──► VPN tunnel
        │
        └── Probe/scanner? ──► proxy to 127.0.0.1:8443
                                        │
                                        ▼
                               Caddy (valid TLS cert
                               for your-domain.com)
                                        │
                                        ▼
                                  404 stub page
```

DPI or active probing sees a legitimate TLS certificate matching the SNI — nothing suspicious.

## Requirements

- Debian / Ubuntu server
- Root access
- Domain with DNS A record pointing to your server IP
- Xray Reality node (Remnawave or standalone)

## Installation

**One command:**

```bash
bash <(curl -Ls https://raw.githubusercontent.com/SkunkBG/SelfstealCaddy/main/selfsteal-setup.sh)
```

**Or manually:**

```bash
curl -Lo selfsteal-setup.sh https://raw.githubusercontent.com/SkunkBG/SelfstealCaddy/main/selfsteal-setup.sh
bash selfsteal-setup.sh
```

The script will ask for your domain interactively.

## What the script does

1. Checks DNS resolution for your domain
2. Installs Caddy (if not already installed)
3. Creates a styled 404 HTML page at `/var/www/html/404.html`
4. Configures Caddy:
   - Port `80` — Let's Encrypt certificate + HTTP → HTTPS redirect
   - Port `8443` — HTTPS with valid TLS certificate, serves 404 page
5. Configures UFW firewall (opens `80`, `443`, closes `8443`)
6. Starts Caddy and verifies the certificate

## After installation

Update your Xray / Remnawave node config — change two fields in `realitySettings`:

```json
"realitySettings": {
    "target": "127.0.0.1:8443",
    "serverNames": ["your-domain.com"]
}
```

| Before | After |
|--------|-------|
| `"target": "www.google.com:443"` | `"target": "127.0.0.1:8443"` |
| `"serverNames": ["google.com"]` | `"serverNames": ["your-domain.com"]` |

Everything else in the config (`shortIds`, `privateKey`, routing, outbounds) stays the same.

## Ports

| Port | Service | Access |
|------|---------|--------|
| `443` | Xray Reality | Public — VPN connections |
| `80` | Caddy | Public — certificate renewal + redirect |
| `8443` | Caddy HTTPS | **Internal only** (`127.0.0.1`) |

## File locations

| File | Path |
|------|------|
| 404 page | `/var/www/html/404.html` |
| Caddy config | `/etc/caddy/Caddyfile` |
| Caddy config backup | `/etc/caddy/Caddyfile.bak.*` |

## Customization

To change the 404 page design, edit `/var/www/html/404.html` and restart Caddy:

```bash
nano /var/www/html/404.html
systemctl restart caddy
```

## Uninstall

```bash
systemctl stop caddy
systemctl disable caddy
apt remove caddy -y
rm -rf /var/www/html/404.html
rm -f /etc/apt/sources.list.d/caddy-stable.list
rm -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg
```

## Troubleshooting

**Caddy won't start:**
```bash
journalctl -u caddy --no-pager -n 30
```

**Certificate not issued:**
- Make sure port `80` is open and DNS A record points to your server
- Check: `curl -I http://your-domain.com`

**Test HTTPS manually:**
```bash
curl -I https://your-domain.com:8443
```

## License

MIT
