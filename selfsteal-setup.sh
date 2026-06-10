#!/bin/bash

# ============================================================
#  SelfSteal Caddy Stub Installer  (single-page, DPI-hardened)
#  For Remnawave + Xray Reality nodes
#
#  Usage: bash selfsteal-setup.sh
#  Requirements: Debian/Ubuntu, root access
#
#  Цель: бэкенд-заглушка, неотличимая от обычного статического
#  HTTPS-сайта при активном зондировании TSPU/DPI:
#    - один аккуратный лендинг (200 на /),
#    - честный 404 на несуществующие пути (не «всё → 200»),
#    - favicon.ico и robots.txt, чтобы сайт выглядел законченным,
#    - gzip/zstd-сжатие и кэш-заголовки как у нормального сервера,
#    - убран заголовок Server: Caddy (типичный маркер self-steal),
#    - редирект 80 → https://домен (на 443, без «странного» :8443).
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

echo -e "${CYAN}"
cat << 'BANNER'
 ╔═══════════════════════════════════════════════╗
 ║       SelfSteal Caddy Stub Installer           ║
 ║       single-page · DPI-hardened               ║
 ╚═══════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# ---- Check root ----
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}[✗] This script must be run as root${NC}"
    echo -e "    Run: ${CYAN}sudo bash $0${NC}"
    exit 1
fi

# ---- Domain input ----
read -rp "$(echo -e "${YELLOW}[?] Enter your domain: ${NC}")" DOMAIN

if [[ -z "$DOMAIN" ]]; then
    echo -e "${RED}[✗] Domain cannot be empty${NC}"
    exit 1
fi

DOMAIN=$(echo "$DOMAIN" | xargs)

# ---- Check DNS ----
echo -e "${CYAN}[*] Checking DNS for ${DOMAIN}...${NC}"

SERVER_IP=$(curl -s4 --max-time 5 ifconfig.me 2>/dev/null || curl -s4 --max-time 5 icanhazip.com 2>/dev/null || echo "unknown")
DOMAIN_IP=$(dig +short "$DOMAIN" A 2>/dev/null | head -1)

if [[ -z "$DOMAIN_IP" ]]; then
    echo -e "${RED}[✗] Domain ${DOMAIN} does not resolve to any IP${NC}"
    echo -e "    Make sure DNS A record points to this server: ${CYAN}${SERVER_IP}${NC}"
    read -rp "$(echo -e "${YELLOW}[?] Continue anyway? (y/n): ${NC}")" CONT
    [[ "$CONT" != "y" ]] && exit 1
elif [[ "$SERVER_IP" == "$DOMAIN_IP" ]]; then
    echo -e "${GREEN}[✓] DNS OK: ${DOMAIN} → ${DOMAIN_IP}${NC}"
else
    echo -e "${YELLOW}[!] Warning: ${DOMAIN} → ${DOMAIN_IP}, but server IP is ${SERVER_IP}${NC}"
    read -rp "$(echo -e "${YELLOW}[?] Continue anyway? (y/n): ${NC}")" CONT
    [[ "$CONT" != "y" ]] && exit 1
fi

# ---- Install dependencies ----
echo -e "${CYAN}[*] Checking dependencies...${NC}"

for pkg in curl dnsutils; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        apt install -y "$pkg" > /dev/null 2>&1
    fi
done

# ---- Install Caddy ----
echo -e "${CYAN}[*] Installing Caddy...${NC}"

if command -v caddy &>/dev/null; then
    CADDY_VER=$(caddy version 2>/dev/null | awk '{print $1}')
    echo -e "${GREEN}[✓] Caddy already installed (${CADDY_VER})${NC}"
else
    apt install -y debian-keyring debian-archive-keyring apt-transport-https > /dev/null 2>&1

    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null

    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        | tee /etc/apt/sources.list.d/caddy-stable.list > /dev/null

    apt update -qq > /dev/null 2>&1
    apt install -y caddy > /dev/null 2>&1

    if command -v caddy &>/dev/null; then
        echo -e "${GREEN}[✓] Caddy installed successfully${NC}"
    else
        echo -e "${RED}[✗] Failed to install Caddy${NC}"
        exit 1
    fi
fi

# ---- Web root ----
echo -e "${CYAN}[*] Creating site files...${NC}"
mkdir -p /var/www/html

# ---- index.html : Northbound studio landing (self-contained, no JS, no external requests) ----
cat > /var/www/html/index.html << HTMLEOF
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Northbound — Design Studio</title>
    <meta name="description" content="Northbound is an independent design studio working on brand identity, digital products and art direction for considered, long-lived companies.">
    <meta name="theme-color" content="#f3efe6">
    <link rel="canonical" href="https://${DOMAIN}/">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <meta property="og:type" content="website">
    <meta property="og:title" content="Northbound — Design Studio">
    <meta property="og:description" content="Independent design studio. Brand identity, digital products and art direction.">
    <meta property="og:url" content="https://${DOMAIN}/">
    <style>
        :root{
            --paper:#f3efe6;--ink:#1c1a16;--muted:#6f6a5f;--line:#ddd6c8;
            --clay:#a9542f;--cream:#fbf9f4;--max:1080px;
            --serif:ui-serif,Georgia,'Times New Roman',serif;
            --sans:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;
        }
        *{margin:0;padding:0;box-sizing:border-box}
        html{scroll-behavior:smooth}
        body{
            font-family:var(--sans);background:var(--paper);color:var(--ink);
            line-height:1.6;-webkit-font-smoothing:antialiased;
            background-image:radial-gradient(circle at 18% -10%,rgba(169,84,47,.06),transparent 45%);
        }
        .wrap{max-width:var(--max);margin:0 auto;padding:0 1.6rem}
        a{color:inherit}
        .reveal{opacity:0;transform:translateY(14px);animation:rise .8s cubic-bezier(.2,.7,.2,1) forwards}
        .d1{animation-delay:.05s}.d2{animation-delay:.16s}.d3{animation-delay:.27s}
        .d4{animation-delay:.38s}.d5{animation-delay:.49s}
        @keyframes rise{to{opacity:1;transform:none}}

        header{padding:1.8rem 0;border-bottom:1px solid var(--line)}
        .bar{display:flex;align-items:center;justify-content:space-between}
        .mark{font-family:var(--serif);font-size:1.35rem;letter-spacing:-.01em;font-weight:600}
        .mark b{color:var(--clay);font-weight:600}
        nav ul{list-style:none;display:flex;gap:1.9rem}
        nav a{text-decoration:none;color:var(--muted);font-size:.9rem;letter-spacing:.02em;transition:color .25s}
        nav a:hover,nav a:focus-visible{color:var(--ink)}

        .hero{padding:6.5rem 0 5rem;border-bottom:1px solid var(--line)}
        .eyebrow{font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;color:var(--clay);margin-bottom:1.6rem}
        .hero h1{font-family:var(--serif);font-weight:600;font-size:clamp(2.4rem,6.4vw,4.4rem);line-height:1.04;letter-spacing:-.015em;max-width:15ch}
        .hero p{margin-top:1.7rem;max-width:54ch;color:var(--muted);font-size:1.12rem}
        .meta{margin-top:2.6rem;display:flex;gap:2.4rem;flex-wrap:wrap;font-size:.85rem;color:var(--muted)}
        .meta span{display:block;color:var(--ink);font-family:var(--serif);font-size:1.05rem;margin-top:.15rem}

        section{padding:5rem 0;border-bottom:1px solid var(--line)}
        .label{font-size:.78rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);margin-bottom:2.4rem}
        .services{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:2.2rem}
        .svc svg{width:26px;height:26px;stroke:var(--clay);fill:none;stroke-width:1.4;margin-bottom:1.1rem}
        .svc h3{font-family:var(--serif);font-weight:600;font-size:1.3rem;margin-bottom:.5rem}
        .svc p{color:var(--muted);font-size:.96rem}

        .work a{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;
            padding:1.35rem 0;border-top:1px solid var(--line);text-decoration:none;transition:padding-left .3s}
        .work a:last-child{border-bottom:1px solid var(--line)}
        .work a:hover,.work a:focus-visible{padding-left:.7rem}
        .work .name{font-family:var(--serif);font-size:1.4rem;font-weight:600}
        .work .cat{color:var(--muted);font-size:.9rem;flex:1;text-align:right;padding-right:1.4rem}
        .work .yr{color:var(--clay);font-size:.85rem;font-variant-numeric:tabular-nums}

        .contact{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:2rem}
        .contact h2{font-family:var(--serif);font-weight:600;font-size:clamp(1.8rem,4.4vw,2.8rem);line-height:1.1;letter-spacing:-.01em}
        .contact .email{font-size:1.15rem;color:var(--clay);text-decoration:none;border-bottom:1px solid transparent;transition:border-color .25s}
        .contact .email:hover,.contact .email:focus-visible{border-color:var(--clay)}

        footer{padding:2.4rem 0;display:flex;flex-wrap:wrap;gap:1rem;justify-content:space-between;
            color:var(--muted);font-size:.82rem}

        :focus-visible{outline:2px solid var(--clay);outline-offset:3px;border-radius:2px}
        @media (max-width:640px){
            nav{display:none}
            .hero{padding:4.5rem 0 3.5rem}
            .work .cat{display:none}
        }
        @media (prefers-reduced-motion:reduce){
            .reveal{animation:none;opacity:1;transform:none}
            html{scroll-behavior:auto}
        }
    </style>
</head>
<body>
    <header>
        <div class="wrap bar reveal d1">
            <div class="mark">North<b>bound</b></div>
            <nav aria-label="Primary">
                <ul>
                    <li><a href="#work">Work</a></li>
                    <li><a href="#studio">Studio</a></li>
                    <li><a href="#contact">Contact</a></li>
                </ul>
            </nav>
        </div>
    </header>

    <main>
        <div class="hero">
            <div class="wrap">
                <p class="eyebrow reveal d1">Independent design studio</p>
                <h1 class="reveal d2">Quiet design for brands that intend to last.</h1>
                <p class="reveal d3">We partner with founders and small teams on identity, product and the in-between — the unglamorous details that make a brand feel considered rather than assembled.</p>
                <div class="meta reveal d4">
                    <div>Established<span>2014</span></div>
                    <div>Practice<span>Brand &amp; Digital</span></div>
                    <div>Engagements<span>By referral</span></div>
                </div>
            </div>
        </div>

        <section id="studio">
            <div class="wrap">
                <p class="label reveal d1">What we do</p>
                <div class="services">
                    <div class="svc reveal d2">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/></svg>
                        <h3>Brand Identity</h3>
                        <p>Naming, marks, typography and the systems that hold a brand together as it grows.</p>
                    </div>
                    <div class="svc reveal d3">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M3 9h18M8 21h8"/></svg>
                        <h3>Digital Product</h3>
                        <p>Interfaces and websites designed to be calm to use and unremarkable to maintain.</p>
                    </div>
                    <div class="svc reveal d4">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 19V5l8 6 8-6v14"/></svg>
                        <h3>Editorial &amp; Art Direction</h3>
                        <p>Print, photography direction and the long-form pieces that give a brand a voice.</p>
                    </div>
                </div>
            </div>
        </section>

        <section id="work" class="work">
            <div class="wrap">
                <p class="label reveal d1">Selected work</p>
                <div class="reveal d2">
                    <a href="#"><span class="name">Marbury &amp; Crane</span><span class="cat">Identity, Packaging</span><span class="yr">2024</span></a>
                    <a href="#"><span class="name">Harbon Coffee</span><span class="cat">Brand, Web</span><span class="yr">2023</span></a>
                    <a href="#"><span class="name">Field Atlas</span><span class="cat">Editorial, Art Direction</span><span class="yr">2023</span></a>
                    <a href="#"><span class="name">Sable Architects</span><span class="cat">Identity, Digital</span><span class="yr">2022</span></a>
                    <a href="#"><span class="name">Quill Press</span><span class="cat">Naming, Brand System</span><span class="yr">2021</span></a>
                </div>
            </div>
        </section>

        <section id="contact">
            <div class="wrap contact">
                <h2 class="reveal d1">Have something<br>worth making well?</h2>
                <a class="email reveal d2" href="mailto:hello@${DOMAIN}">hello@${DOMAIN}</a>
            </div>
        </section>
    </main>

    <footer>
        <div class="wrap bar">
            <span>&copy; 2026 Northbound Studio</span>
            <span>By appointment &middot; Replies within two working days</span>
        </div>
    </footer>
</body>
</html>
HTMLEOF

# ---- 404.html : on-brand error page (served WITH 404 status) ----
cat > /var/www/html/404.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page not found — Northbound</title>
    <meta name="robots" content="noindex">
    <link rel="icon" href="/favicon.ico" sizes="any">
    <style>
        :root{--paper:#f3efe6;--ink:#1c1a16;--muted:#6f6a5f;--clay:#a9542f;
            --serif:ui-serif,Georgia,'Times New Roman',serif;
            --sans:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:var(--sans);background:var(--paper);color:var(--ink);
            min-height:100vh;display:flex;align-items:center;justify-content:center;
            text-align:center;padding:2rem;
            background-image:radial-gradient(circle at 18% -10%,rgba(169,84,47,.06),transparent 45%)}
        .code{font-family:var(--serif);font-weight:600;font-size:clamp(3rem,9vw,5rem);letter-spacing:-.02em}
        .msg{margin-top:.6rem;color:var(--muted);font-size:1.05rem}
        .home{display:inline-block;margin-top:1.8rem;color:var(--clay);text-decoration:none;
            border-bottom:1px solid transparent;transition:border-color .25s;font-size:.95rem}
        .home:hover{border-color:var(--clay)}
    </style>
</head>
<body>
    <div>
        <div class="code">404</div>
        <p class="msg">We couldn&rsquo;t find that page.</p>
        <a class="home" href="/">Return to the studio</a>
    </div>
</body>
</html>
HTMLEOF

# ---- robots.txt : ordinary, allow-all ----
cat > /var/www/html/robots.txt << 'ROBOTSEOF'
User-agent: *
Allow: /
ROBOTSEOF

# ---- favicon.ico : small embedded mark, so /favicon.ico returns 200 ----
base64 -d > /var/www/html/favicon.ico << 'ICOEOF'
AAABAAEAEBAAAAAAIACOAgAAFgAAAIlQTkcNChoKAAAADUlIRFIAAAAQAAAAEAgGAAAAH/P/YQAA
AlVJREFUeJx1kUFIVFEUhr9z3/W90STSpKIhQsMowSkLbFEEEgRtIsTKIIsWbSXXrdu0cRkELYJA
TQkCIWhZtAkpkSRMTEKMskkmdXTm+d49Ld6MOmYH7ubc8/985/wCMNCZuZ6y5kGk2ugUAYSdS42g
VmS2ELn7N15MDMlg18mrvuE5QOhU5f/ixAHUNyLJPNcM6voBwtjFFWIRxHjJky1tkDB2ceLm+q0R
SYdOERFvUyu4KGK9uAaqeH6A5weoavnfC51iRNJWoQJbjGE9v8yBU+c4ePo84XKOML/E1Mun+Lvr
0Dguk6CgdvvB1CmenyLT00tDcxsAxZVFvo+9YTX7A6/K3yABxGwVi2cJl3McvXyThuY2onCFKMwT
1NaRuXWPOCxul2A2rQzRWp66pmO0dN0FIDs1wc+J96g6Dp+9RLq9g3DlD2I2zoWtyCeOydzuI6it
J14v8PHJQ6LCKvtb2/H8gExPLwufxtA4KpFoQiDGI8wv0XjhCofOXARg+tUAi9OTLM3N8mX0GSKW
+qZWjnfeIVxdRozZJFB12FQ1vz5/4NvbUeqOtDA5+AibqkZEmBx+TLq9g6W5r8y9e01VaheqLll9
qOuEAwQR4mIBRKip30ch9xuxyYYaRQR79lJYXMC5GJuqgSQJtQLiAFHFBikA1nJZjK0qDyHWUsxl
MX6Ah6Dq0CQBMU513jeCqsaqiqpWiBMERUo9VYeqxr4RnOq8QUwfgO8ZT0HLgn+q1FNQ3yvlKKbP
dI+MDxcj1y0w4wlK2WTnUk9QgZli5Lq7R8aH/wKImhKGbGsTWQAAAABJRU5ErkJggg==
ICOEOF

echo -e "${GREEN}[✓] Site files created (index.html, 404.html, robots.txt, favicon.ico)${NC}"

# ---- Configure Caddy ----
echo -e "${CYAN}[*] Configuring Caddy...${NC}"

if [[ -f /etc/caddy/Caddyfile ]]; then
    cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%s)"
fi

cat > /etc/caddy/Caddyfile << CADDYEOF
{
    http_port 80
    https_port 8443
}

# HTTP :80 — used by Caddy for the ACME (Let's Encrypt) challenge.
# Everything else is redirected to plain https://domain (port 443),
# so the public surface looks like an ordinary site on 443 — Xray
# Reality fronts this backend for probes. No odd :8443 in Location.
${DOMAIN}:80 {
    redir https://${DOMAIN}{uri} permanent
}

# HTTPS backend on 127.0.0.1:8443 — what Reality proxies probes to.
${DOMAIN}:8443 {
    root * /var/www/html

    # Behave like a normal server: negotiate compression.
    encode zstd gzip

    header {
        # Drop the "Server: Caddy" tell; ordinary sites don't advertise it.
        -Server
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        Cache-Control "public, max-age=600"
    }

    # Real sites return 404 for unknown paths. Serve the on-brand
    # 404 page but KEEP the real status code (not a blanket 200).
    handle_errors {
        rewrite * /404.html
        file_server {
            status {err.status_code}
        }
    }

    # No try_files / SPA fallback: missing files 404 naturally.
    file_server
}
CADDYEOF

caddy fmt --overwrite /etc/caddy/Caddyfile > /dev/null 2>&1 || true

if caddy validate --config /etc/caddy/Caddyfile > /dev/null 2>&1; then
    echo -e "${GREEN}[✓] Caddyfile configured and validated${NC}"
else
    echo -e "${YELLOW}[!] caddy validate reported issues — check /etc/caddy/Caddyfile${NC}"
fi

# ---- Firewall ----
echo -e "${CYAN}[*] Configuring firewall...${NC}"

if command -v ufw &>/dev/null; then
    ufw allow 80/tcp  > /dev/null 2>&1 || true
    ufw allow 443/tcp > /dev/null 2>&1 || true
    ufw delete allow 8443/tcp > /dev/null 2>&1 || true
    echo -e "${GREEN}[✓] UFW: 80/tcp, 443/tcp open | 8443 closed (internal only)${NC}"
else
    echo -e "${YELLOW}[!] UFW not found — make sure ports 80 and 443 are open${NC}"
fi

# ---- Start Caddy ----
echo -e "${CYAN}[*] Starting Caddy...${NC}"

systemctl enable caddy > /dev/null 2>&1
systemctl restart caddy

echo -e "${CYAN}[*] Waiting for TLS certificate...${NC}"
sleep 5

if systemctl is-active --quiet caddy; then
    echo -e "${GREEN}[✓] Caddy is running${NC}"
else
    echo -e "${RED}[✗] Caddy failed to start${NC}"
    echo -e "    Check: ${CYAN}journalctl -u caddy --no-pager -n 20${NC}"
    exit 1
fi

# ---- Verify (local) ----
ROOT_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${DOMAIN}:8443/" 2>/dev/null || echo "000")
NF_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${DOMAIN}:8443/this-path-does-not-exist-$RANDOM" 2>/dev/null || echo "000")

if [[ "$ROOT_CODE" == "200" ]]; then
    echo -e "${GREEN}[✓] Homepage serves HTTP 200${NC}"
elif [[ "$ROOT_CODE" == "000" ]]; then
    echo -e "${YELLOW}[!] Could not verify homepage yet (cert may still be issuing)${NC}"
else
    echo -e "${YELLOW}[!] Homepage returned HTTP ${ROOT_CODE}${NC}"
fi

if [[ "$NF_CODE" == "404" ]]; then
    echo -e "${GREEN}[✓] Unknown paths correctly return HTTP 404${NC}"
elif [[ "$NF_CODE" != "000" ]]; then
    echo -e "${YELLOW}[!] Unknown path returned HTTP ${NF_CODE} (expected 404)${NC}"
fi

# ---- Summary ----
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✓ Installation Complete              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Domain:${NC}     ${CYAN}${DOMAIN}${NC}"
echo -e "  ${BOLD}Page:${NC}       ${CYAN}Northbound (studio landing, single page)${NC}"
echo -e "  ${BOLD}Backend:${NC}    ${CYAN}https://127.0.0.1:8443${NC} (local only)"
echo ""
echo -e "  ${YELLOW}━━━ Update your Xray / Remnawave node config ━━━${NC}"
echo ""
echo -e "    \"target\":      ${GREEN}\"127.0.0.1:8443\"${NC}"
echo -e "    \"serverNames\": ${GREEN}[\"${DOMAIN}\"]${NC}"
echo ""
echo -e "  ${BOLD}Open ports:${NC}  80 (cert + redirect), 443 (Xray Reality, public)"
echo -e "  ${BOLD}Internal:${NC}    8443 (Caddy backend, localhost only)"
echo ""
echo -e "  ${DIM}Edit text/brand: /var/www/html/index.html → systemctl restart caddy${NC}"
echo ""
