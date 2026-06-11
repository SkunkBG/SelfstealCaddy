#!/bin/bash

# =============================================================================
#  SelfSteal Caddy Stub Installer  —  multi-theme, DPI-hardened
#  For Remnawave + Xray Reality nodes
#
#  Usage:
#     bash selfsteal-setup.sh                  # interactive (asks domain + theme)
#     DOMAIN=ex.com STUB_THEME=random bash selfsteal-setup.sh   # non-interactive
#     DRY_RUN=1 DOMAIN=ex.com STUB_THEME=law WEBROOT=/tmp/site \
#        CADDYFILE=/tmp/Caddyfile bash selfsteal-setup.sh       # preview only
#
#  Each install produces ONE realistic multi-page static site, randomized
#  (theme + brand + accent + city + year) so nodes don't share a fingerprint.
#
#  Anti-scanning hardening:
#   - real multi-page site with /sitemap.xml and /.well-known/security.txt
#   - honest status codes: GET / => 200, unknown paths => real 404
#   - HTTP/1.1 + HTTP/2 only — HTTP/3 disabled, Alt-Svc stripped
#     (no QUIC service is advertised that doesn't exist on :443)
#   - no "Server: Caddy" header (removes a known self-steal tell)
#   - Caddy admin API disabled (no localhost:2019 listener)
#   - gzip/zstd, ETag/Last-Modified, sane cache headers — like a real host
#   - http://domain -> https://domain (443, implicit), never :8443 in Location
#
#  STUB_THEME: studio | coffee | law | contractor | random   (default: random)
#  Requirements: Debian/Ubuntu, root (unless DRY_RUN=1)
# =============================================================================

set -e

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

WEBROOT="${WEBROOT:-/var/www/html}"
CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
DRY_RUN="${DRY_RUN:-0}"

echo -e "${CYAN}"
cat << 'BANNER'
 ╔═══════════════════════════════════════════════╗
 ║   SelfSteal Caddy Stub  ·  multi-theme         ║
 ║   randomized · DPI-hardened                    ║
 ╚═══════════════════════════════════════════════╝
BANNER
echo -e "${NC}"

# ---- root ----
if [[ "$DRY_RUN" != "1" && $EUID -ne 0 ]]; then
    echo -e "${RED}[✗] Run as root:${NC} sudo bash $0"
    exit 1
fi

# ---- domain ----
if [[ -z "${DOMAIN:-}" ]]; then
    read -rp "$(echo -e "${YELLOW}[?] Enter your domain: ${NC}")" DOMAIN
fi
DOMAIN="$(echo "$DOMAIN" | xargs)"
if [[ -z "$DOMAIN" ]]; then
    echo -e "${RED}[✗] Domain cannot be empty${NC}"; exit 1
fi

# ---- theme selection ----
if [[ -z "${STUB_THEME:-}" ]]; then
    echo ""
    echo -e "${BOLD}  Выберите тип сайта-заглушки:${NC}"
    echo ""
    echo -e "  ${CYAN}1)${NC} ${BOLD}Студия${NC}            ${DIM}— дизайн-студия (editorial, светлый)${NC}"
    echo -e "  ${CYAN}2)${NC} ${BOLD}Кофейня${NC}           ${DIM}— локальная кофейня с меню${NC}"
    echo -e "  ${CYAN}3)${NC} ${BOLD}Юрфирма${NC}           ${DIM}— юридическая практика (строгий)${NC}"
    echo -e "  ${CYAN}4)${NC} ${BOLD}Подрядчик${NC}         ${DIM}— строительная компания${NC}"
    echo -e "  ${CYAN}5)${NC} ${BOLD}Случайно${NC}          ${DIM}— выбрать наугад (по умолчанию)${NC}"
    echo ""
    read -rp "$(echo -e "${YELLOW}[?] Выбор (1-5) [5]: ${NC}")" CH
    case "${CH:-5}" in
        1) STUB_THEME=studio ;;
        2) STUB_THEME=coffee ;;
        3) STUB_THEME=law ;;
        4) STUB_THEME=contractor ;;
        *) STUB_THEME=random ;;
    esac
fi

if [[ "$STUB_THEME" == "random" ]]; then
    THEMES=(studio coffee law contractor)
    STUB_THEME="${THEMES[RANDOM % ${#THEMES[@]}]}"
fi
echo -e "${GREEN}[✓] Тема: ${STUB_THEME}${NC}"

# ---- DNS + install (skipped in DRY_RUN) ----
if [[ "$DRY_RUN" != "1" ]]; then
    echo -e "${CYAN}[*] Checking DNS for ${DOMAIN}...${NC}"
    SERVER_IP=$(curl -s4 --max-time 5 ifconfig.me 2>/dev/null || curl -s4 --max-time 5 icanhazip.com 2>/dev/null || echo "unknown")
    DOMAIN_IP=$(dig +short "$DOMAIN" A 2>/dev/null | head -1)
    if [[ -z "$DOMAIN_IP" ]]; then
        echo -e "${RED}[✗] ${DOMAIN} does not resolve${NC}"
        echo -e "    Point a DNS A record at: ${CYAN}${SERVER_IP}${NC}"
        read -rp "$(echo -e "${YELLOW}[?] Continue anyway? (y/n): ${NC}")" C; [[ "$C" != "y" ]] && exit 1
    elif [[ "$SERVER_IP" == "$DOMAIN_IP" ]]; then
        echo -e "${GREEN}[✓] DNS OK: ${DOMAIN} → ${DOMAIN_IP}${NC}"
    else
        echo -e "${YELLOW}[!] ${DOMAIN} → ${DOMAIN_IP}, server IP ${SERVER_IP}${NC}"
        read -rp "$(echo -e "${YELLOW}[?] Continue anyway? (y/n): ${NC}")" C; [[ "$C" != "y" ]] && exit 1
    fi

    echo -e "${CYAN}[*] Checking dependencies...${NC}"
    for pkg in curl dnsutils; do
        dpkg -s "$pkg" &>/dev/null || apt install -y "$pkg" >/dev/null 2>&1
    done

    echo -e "${CYAN}[*] Installing Caddy...${NC}"
    if command -v caddy &>/dev/null; then
        echo -e "${GREEN}[✓] Caddy already installed ($(caddy version 2>/dev/null | awk '{print $1}'))${NC}"
    else
        apt install -y debian-keyring debian-archive-keyring apt-transport-https >/dev/null 2>&1
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
            | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg 2>/dev/null
        curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
            | tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
        apt update -qq >/dev/null 2>&1
        apt install -y caddy >/dev/null 2>&1
        command -v caddy &>/dev/null && echo -e "${GREEN}[✓] Caddy installed${NC}" \
            || { echo -e "${RED}[✗] Caddy install failed${NC}"; exit 1; }
    fi
fi

# =============================================================================
#  Randomized identity
# =============================================================================
CITIES=(Portland Austin Bristol Leeds Hamburg Aarhus Lyon Ghent Tallinn Porto Antwerp Utrecht)
CITY="${CITIES[RANDOM % ${#CITIES[@]}]}"
YEAR=$(( 2007 + RANDOM % 13 ))   # 2007–2019

case "$STUB_THEME" in
  studio)
    BR=(Northbound Fieldnote Atelier Quietwork Harbourline Maren Foldwork Linden)
    AC=("#a9542f" "#3f6f5f" "#6b5b95"); BG="#f3efe6"; INK="#1c1a16" ;;
  coffee)
    BR=(Harbon Cardinal Foxglove Tideline Ember Sparrow Quill Maple)
    AC=("#9c5a2c" "#7a7f3f" "#b5462f"); BG="#f6efe4"; INK="#2a211b" ;;
  law)
    BR=(Whitmore Castellan Ashford Brevard Halloway Sterling Marwick Pennington)
    AC=("#9a7b34" "#1f3a5f" "#6e4a2f"); BG="#ffffff"; INK="#10202f" ;;
  contractor)
    BR=(Ridgeline Keystone Brandt Holloway Ironwood Meridian Caldwell Granite)
    AC=("#c2671f" "#3a6ea5" "#9e3b2e"); BG="#f2f1ee"; INK="#1b1d20" ;;
esac
BRAND="${BR[RANDOM % ${#BR[@]}]}"
ACCENT="${AC[RANDOM % ${#AC[@]}]}"
INIT="${BRAND:0:1}"

echo -e "${GREEN}[✓] Brand: ${BRAND} · ${CITY} · est. ${YEAR} · accent ${ACCENT}${NC}"

mkdir -p "$WEBROOT" "$WEBROOT/.well-known"

# ---- shared <head> emitter ----
# args: $1 = full <title>, $2 = description, $3 = canonical path ("" or "work.html")
emit_head() {
cat <<HEAD
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>$1</title>
<meta name="description" content="$2">
<meta name="theme-color" content="$BG">
<link rel="canonical" href="https://$DOMAIN/$3">
<link rel="stylesheet" href="/style.css">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="icon" href="/favicon.ico" sizes="any">
<meta property="og:type" content="website">
<meta property="og:title" content="$1">
<meta property="og:url" content="https://$DOMAIN/$3">
</head>
<body>
HEAD
}

# ---- favicon.svg (monogram) ----
FG="#ffffff"
cat > "$WEBROOT/favicon.svg" <<SVG
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="$ACCENT"/><text x="32" y="44" font-family="Georgia,'Times New Roman',serif" font-size="38" font-weight="700" text-anchor="middle" fill="$FG">$INIT</text></svg>
SVG

# ---- favicon.ico (generic fallback, so /favicon.ico returns 200) ----
base64 -d > "$WEBROOT/favicon.ico" <<'ICOEOF'
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

# =============================================================================
#  THEME 1 — Studio (editorial, serif)
# =============================================================================
gen_studio() {
DISPLAY="$BRAND"
cat > "$WEBROOT/style.css" <<CSS
:root{--bg:$BG;--ink:$INK;--muted:#6f6a5f;--line:#ddd6c8;--accent:$ACCENT;--max:1080px;
 --serif:ui-serif,Georgia,'Times New Roman',serif;--sans:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
*{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg);color:var(--ink);line-height:1.6;-webkit-font-smoothing:antialiased;
 background-image:radial-gradient(circle at 18% -10%,rgba(0,0,0,.04),transparent 45%)}
.wrap{max-width:var(--max);margin:0 auto;padding:0 1.6rem}a{color:inherit}
.bar{display:flex;align-items:center;justify-content:space-between}
.site-header{padding:1.7rem 0;border-bottom:1px solid var(--line)}
.brand{font-family:var(--serif);font-size:1.35rem;font-weight:600;letter-spacing:-.01em;text-decoration:none}
nav ul{list-style:none;display:flex;gap:1.9rem}
nav a{text-decoration:none;color:var(--muted);font-size:.9rem;letter-spacing:.02em}
nav a:hover{color:var(--ink)}
.hero{padding:6rem 0 4.5rem;border-bottom:1px solid var(--line)}
.eyebrow{font-size:.78rem;letter-spacing:.22em;text-transform:uppercase;color:var(--accent);margin-bottom:1.5rem}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(2.3rem,6vw,4.2rem);line-height:1.05;letter-spacing:-.015em;max-width:16ch}
.lead{margin-top:1.6rem;max-width:56ch;color:var(--muted);font-size:1.12rem}
.meta{margin-top:2.4rem;display:flex;gap:2.4rem;flex-wrap:wrap;font-size:.85rem;color:var(--muted)}
.meta span{display:block;color:var(--ink);font-family:var(--serif);font-size:1.05rem;margin-top:.15rem}
section{padding:4.5rem 0;border-bottom:1px solid var(--line)}
.label{font-size:.78rem;letter-spacing:.2em;text-transform:uppercase;color:var(--muted);margin-bottom:2.2rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:2.2rem}
.card svg{width:26px;height:26px;stroke:var(--accent);fill:none;stroke-width:1.4;margin-bottom:1rem}
.card h3{font-family:var(--serif);font-weight:600;font-size:1.3rem;margin-bottom:.4rem}
.card p{color:var(--muted);font-size:.96rem}
.rows a{display:flex;align-items:baseline;justify-content:space-between;gap:1rem;padding:1.3rem 0;border-top:1px solid var(--line);text-decoration:none}
.rows a:last-child{border-bottom:1px solid var(--line)}
.rows .name{font-family:var(--serif);font-size:1.35rem;font-weight:600}
.rows .cat{color:var(--muted);font-size:.9rem;flex:1;text-align:right;padding-right:1.4rem}
.rows .yr{color:var(--accent);font-size:.85rem;font-variant-numeric:tabular-nums}
.contact{display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:2rem}
.contact h2{font-family:var(--serif);font-weight:600;font-size:clamp(1.8rem,4.4vw,2.8rem);line-height:1.1}
.email{font-size:1.15rem;color:var(--accent);text-decoration:none;border-bottom:1px solid transparent}
.email:hover{border-color:var(--accent)}
.prose p{max-width:60ch;color:var(--muted);margin-top:1.1rem}
.site-footer{padding:2.3rem 0;color:var(--muted);font-size:.82rem}
@media(max-width:640px){nav{display:none}.hero{padding:4rem 0 3rem}.rows .cat{display:none}}
CSS

local HDR FTR
HDR=$(cat <<H
<header class="site-header"><div class="wrap bar">
<a class="brand" href="/">$DISPLAY</a>
<nav aria-label="Primary"><ul><li><a href="/work.html">Work</a></li><li><a href="/studio.html">Studio</a></li><li><a href="/contact.html">Contact</a></li></ul></nav>
</div></header>
H
)
FTR=$(cat <<F
<footer class="site-footer"><div class="wrap bar"><span>&copy; $YEAR $DISPLAY</span><span>$CITY &middot; By referral</span></div></footer></body></html>
F
)

{ emit_head "$DISPLAY — Independent design studio" "Independent design studio in $CITY working on brand identity, digital products and art direction." ""
  echo "$HDR"
cat <<H
<main>
<div class="hero"><div class="wrap">
<p class="eyebrow">Independent design studio</p>
<h1>Quiet design for brands that intend to last.</h1>
<p class="lead">We partner with founders and small teams on identity, product and the in-between — the unglamorous details that make a brand feel considered rather than assembled.</p>
<div class="meta"><div>Established<span>$YEAR</span></div><div>Based in<span>$CITY</span></div><div>Engagements<span>By referral</span></div></div>
</div></div>
<section><div class="wrap"><p class="label">What we do</p><div class="grid">
<div class="card"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 3v18M3 12h18"/></svg><h3>Brand Identity</h3><p>Naming, marks, typography and the systems that hold a brand together as it grows.</p></div>
<div class="card"><svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M3 9h18M8 21h8"/></svg><h3>Digital Product</h3><p>Interfaces and websites designed to be calm to use and unremarkable to maintain.</p></div>
<div class="card"><svg viewBox="0 0 24 24"><path d="M4 19V5l8 6 8-6v14"/></svg><h3>Editorial &amp; Art Direction</h3><p>Print, photography direction and the long-form pieces that give a brand a voice.</p></div>
</div></div></section>
</main>
H
  echo "$FTR"
} > "$WEBROOT/index.html"

{ emit_head "Studio — $DISPLAY" "About $DISPLAY, an independent design studio in $CITY." "studio.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><p class="label">Studio</p>
<h1>A small studio, by design.</h1>
<div class="prose">
<p>$DISPLAY is a two-person practice that has worked quietly since $YEAR. We take on a handful of engagements each year so that each one gets the attention it needs.</p>
<p>We work best with founders who care about the details and are prepared to make decisions. Most of our work arrives by referral, which suits us — it means we usually know a little about a project before it begins.</p>
<p>Our approach is unhurried. We research, we draw, we throw most of it away, and what remains is usually simpler than where we started.</p>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/studio.html"

{ emit_head "Work — $DISPLAY" "Selected work by $DISPLAY." "work.html"
  echo "$HDR"
cat <<H
<main><section class="rows"><div class="wrap"><p class="label">Selected work</p><div>
<a href="/contact.html"><span class="name">Marbury</span><span class="cat">Identity, Packaging</span><span class="yr">2024</span></a>
<a href="/contact.html"><span class="name">Harbon</span><span class="cat">Brand, Web</span><span class="yr">2023</span></a>
<a href="/contact.html"><span class="name">Field Atlas</span><span class="cat">Editorial, Art Direction</span><span class="yr">2023</span></a>
<a href="/contact.html"><span class="name">Sable</span><span class="cat">Identity, Digital</span><span class="yr">2022</span></a>
<a href="/contact.html"><span class="name">Quill Press</span><span class="cat">Naming, Brand System</span><span class="yr">2021</span></a>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/work.html"

{ emit_head "Contact — $DISPLAY" "Get in touch with $DISPLAY." "contact.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap contact">
<h2>Have something<br>worth making well?</h2>
<a class="email" href="mailto:hello@$DOMAIN">hello@$DOMAIN</a>
</div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/contact.html"

SITEMAP_PATHS=( "" "studio.html" "work.html" "contact.html" )
}

# =============================================================================
#  THEME 2 — Coffee shop (warm, menu)
# =============================================================================
gen_coffee() {
DISPLAY="$BRAND Coffee"
cat > "$WEBROOT/style.css" <<CSS
:root{--bg:$BG;--ink:$INK;--muted:#7c6f60;--line:#e6ddcd;--accent:$ACCENT;--card:#fffaf2;--max:1040px;
 --sans:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
*{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg);color:var(--ink);line-height:1.65}
.wrap{max-width:var(--max);margin:0 auto;padding:0 1.5rem}a{color:inherit}
.bar{display:flex;align-items:center;justify-content:space-between}
.site-header{padding:1.4rem 0;position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);z-index:5}
.brand{font-weight:800;font-size:1.25rem;letter-spacing:-.02em;text-decoration:none;color:var(--accent)}
nav ul{list-style:none;display:flex;gap:1.6rem}
nav a{text-decoration:none;color:var(--muted);font-size:.92rem;font-weight:600}
nav a:hover{color:var(--ink)}
.hero{padding:5rem 0;text-align:center}
.hero .badge{display:inline-block;padding:.35rem 1rem;border-radius:50px;background:var(--card);border:1px solid var(--line);color:var(--accent);font-size:.78rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:1.6rem}
h1{font-size:clamp(2.4rem,7vw,4rem);line-height:1.06;font-weight:800;letter-spacing:-.02em;max-width:16ch;margin:0 auto}
.lead{margin:1.4rem auto 0;max-width:48ch;color:var(--muted);font-size:1.1rem}
.hours{margin-top:2rem;display:inline-flex;gap:1.6rem;flex-wrap:wrap;justify-content:center;color:var(--muted);font-size:.92rem}
.hours b{color:var(--ink)}
section{padding:3.5rem 0;border-top:1px solid var(--line)}
h2{font-size:1.7rem;font-weight:800;letter-spacing:-.01em;margin-bottom:1.6rem}
.menu{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:2rem 3rem}
.menu h3{font-size:.82rem;text-transform:uppercase;letter-spacing:.12em;color:var(--accent);margin-bottom:.8rem}
.item{display:flex;justify-content:space-between;gap:1rem;padding:.55rem 0;border-bottom:1px dotted var(--line)}
.item .p{color:var(--muted);font-variant-numeric:tabular-nums}
.prose p{max-width:60ch;color:var(--muted);margin-top:1rem}
.email{color:var(--accent);text-decoration:none;font-weight:700}
.site-footer{padding:2.2rem 0;color:var(--muted);font-size:.84rem;border-top:1px solid var(--line)}
@media(max-width:640px){nav{display:none}.hero{padding:3.2rem 0}}
CSS

local HDR FTR
HDR=$(cat <<H
<header class="site-header"><div class="wrap bar">
<a class="brand" href="/">$DISPLAY</a>
<nav aria-label="Primary"><ul><li><a href="/menu.html">Menu</a></li><li><a href="/about.html">About</a></li><li><a href="/visit.html">Visit</a></li></ul></nav>
</div></header>
H
)
FTR=$(cat <<F
<footer class="site-footer"><div class="wrap bar"><span>&copy; $YEAR $DISPLAY · $CITY</span><span>Open daily from 7:30</span></div></footer></body></html>
F
)

{ emit_head "$DISPLAY — neighbourhood coffee in $CITY" "$DISPLAY is a small specialty coffee bar in $CITY. House-roasted beans, simple food, no rush." ""
  echo "$HDR"
cat <<H
<main>
<div class="hero"><div class="wrap">
<span class="badge">Since $YEAR · $CITY</span>
<h1>Good coffee, made slowly.</h1>
<p class="lead">A small corner bar roasting in-house, pulling honest shots and keeping the playlist quiet. Pop in, stay a while.</p>
<div class="hours"><span>Mon–Fri <b>7:30 – 18:00</b></span><span>Sat–Sun <b>8:30 – 17:00</b></span></div>
</div></div>
<section><div class="wrap">
<h2>A few of our regulars</h2>
<div class="menu">
<div><h3>Espresso</h3>
<div class="item"><span>Espresso</span><span class="p">€2.60</span></div>
<div class="item"><span>Flat white</span><span class="p">€3.40</span></div>
<div class="item"><span>Cortado</span><span class="p">€3.10</span></div>
</div>
<div><h3>Filter</h3>
<div class="item"><span>Batch brew</span><span class="p">€3.00</span></div>
<div class="item"><span>Pour-over (single origin)</span><span class="p">€4.20</span></div>
</div>
</div></div></section>
</main>
H
  echo "$FTR"
} > "$WEBROOT/index.html"

{ emit_head "Menu — $DISPLAY" "The full menu at $DISPLAY in $CITY." "menu.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>Menu</h2>
<div class="menu">
<div><h3>Coffee</h3>
<div class="item"><span>Espresso</span><span class="p">€2.60</span></div>
<div class="item"><span>Macchiato</span><span class="p">€2.90</span></div>
<div class="item"><span>Cortado</span><span class="p">€3.10</span></div>
<div class="item"><span>Flat white</span><span class="p">€3.40</span></div>
<div class="item"><span>Latte</span><span class="p">€3.60</span></div>
<div class="item"><span>Batch filter</span><span class="p">€3.00</span></div>
<div class="item"><span>Pour-over</span><span class="p">€4.20</span></div>
</div>
<div><h3>Not coffee</h3>
<div class="item"><span>Tea (loose leaf)</span><span class="p">€3.00</span></div>
<div class="item"><span>Hot chocolate</span><span class="p">€3.80</span></div>
<div class="item"><span>Sparkling water</span><span class="p">€2.40</span></div>
</div>
<div><h3>Kitchen</h3>
<div class="item"><span>Sourdough toast &amp; jam</span><span class="p">€4.50</span></div>
<div class="item"><span>Banana bread</span><span class="p">€3.50</span></div>
<div class="item"><span>Cheese toastie</span><span class="p">€6.50</span></div>
</div>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/menu.html"

{ emit_head "About — $DISPLAY" "The story behind $DISPLAY in $CITY." "about.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>About</h2><div class="prose">
<p>$DISPLAY opened on a quiet corner in $CITY in $YEAR with one machine, a borrowed grinder and a short list of suppliers we still use today.</p>
<p>We roast in small batches a few mornings a week, which means the menu shifts a little with the seasons. If you ask what's good, we'll actually tell you.</p>
<p>It's a small room. We like it that way.</p>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/about.html"

{ emit_head "Visit — $DISPLAY" "Find $DISPLAY in $CITY: hours and location." "visit.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>Visit</h2><div class="prose">
<p><b>Hours</b><br>Monday to Friday, 7:30 – 18:00<br>Weekends, 8:30 – 17:00</p>
<p><b>Where</b><br>A short walk from the old market, $CITY. Look for the green door.</p>
<p><b>Hello</b><br><a class="email" href="mailto:hello@$DOMAIN">hello@$DOMAIN</a></p>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/visit.html"

SITEMAP_PATHS=( "" "menu.html" "about.html" "visit.html" )
}

# =============================================================================
#  THEME 3 — Law firm (formal, serif)
# =============================================================================
gen_law() {
DISPLAY="$BRAND &amp; Partners"
cat > "$WEBROOT/style.css" <<CSS
:root{--bg:$BG;--ink:$INK;--muted:#566573;--line:#e3e7ec;--accent:$ACCENT;--soft:#f5f7f9;--max:1080px;
 --serif:ui-serif,Georgia,'Times New Roman',serif;--sans:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
*{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg);color:var(--ink);line-height:1.7}
.wrap{max-width:var(--max);margin:0 auto;padding:0 1.6rem}a{color:inherit}
.bar{display:flex;align-items:center;justify-content:space-between}
.site-header{padding:1.5rem 0;border-bottom:1px solid var(--line)}
.brand{font-family:var(--serif);font-size:1.3rem;font-weight:600;letter-spacing:.01em;text-decoration:none}
nav ul{list-style:none;display:flex;gap:1.8rem}
nav a{text-decoration:none;color:var(--muted);font-size:.88rem;letter-spacing:.03em;text-transform:uppercase}
nav a:hover{color:var(--accent)}
.hero{padding:5.5rem 0;border-bottom:1px solid var(--line)}
.kicker{font-size:.78rem;letter-spacing:.2em;text-transform:uppercase;color:var(--accent);margin-bottom:1.4rem}
h1{font-family:var(--serif);font-weight:600;font-size:clamp(2.2rem,5.4vw,3.6rem);line-height:1.12;max-width:18ch}
.lead{margin-top:1.5rem;max-width:60ch;color:var(--muted);font-size:1.1rem}
section{padding:4rem 0;border-bottom:1px solid var(--line)}
h2{font-family:var(--serif);font-weight:600;font-size:1.8rem;margin-bottom:1.6rem}
.label{font-size:.78rem;letter-spacing:.18em;text-transform:uppercase;color:var(--muted);margin-bottom:2rem}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:2.4rem}
.col h3{font-family:var(--serif);font-weight:600;font-size:1.2rem;margin-bottom:.5rem}
.col p{color:var(--muted);font-size:.95rem}
.people{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:2rem}
.person{padding:1.4rem;background:var(--soft);border:1px solid var(--line);border-radius:6px}
.person .n{font-family:var(--serif);font-size:1.15rem}
.person .r{color:var(--muted);font-size:.88rem;margin-top:.2rem}
.prose p{max-width:62ch;color:var(--muted);margin-top:1rem}
.email{color:var(--accent);text-decoration:none;font-weight:600}
.site-footer{padding:2.2rem 0;color:var(--muted);font-size:.82rem}
@media(max-width:640px){nav{display:none}.hero{padding:3.6rem 0}}
CSS

local HDR FTR
HDR=$(cat <<H
<header class="site-header"><div class="wrap bar">
<a class="brand" href="/">$DISPLAY</a>
<nav aria-label="Primary"><ul><li><a href="/practice.html">Practice</a></li><li><a href="/people.html">People</a></li><li><a href="/contact.html">Contact</a></li></ul></nav>
</div></header>
H
)
FTR=$(cat <<F
<footer class="site-footer"><div class="wrap bar"><span>&copy; $YEAR $DISPLAY</span><span>$CITY &middot; Regulated practice</span></div></footer></body></html>
F
)

{ emit_head "$DISPLAY — Solicitors in $CITY" "$DISPLAY is a $CITY law practice advising private clients and owner-managed businesses since $YEAR." ""
  echo "$HDR"
cat <<H
<main>
<div class="hero"><div class="wrap">
<p class="kicker">Established $YEAR · $CITY</p>
<h1>Considered legal counsel for private clients and businesses.</h1>
<p class="lead">A small practice with a long view. We advise individuals, families and owner-managed companies — clearly, and without unnecessary correspondence.</p>
</div></div>
<section><div class="wrap"><p class="label">Areas of practice</p><div class="cols">
<div class="col"><h3>Private Client</h3><p>Wills, trusts, probate and the careful planning that keeps matters out of dispute.</p></div>
<div class="col"><h3>Commercial</h3><p>Contracts, shareholder arrangements and the day-to-day questions that growing companies face.</p></div>
<div class="col"><h3>Property</h3><p>Residential and commercial conveyancing handled with attention to the detail that matters.</p></div>
</div></div></section>
</main>
H
  echo "$FTR"
} > "$WEBROOT/index.html"

{ emit_head "Practice — $DISPLAY" "Areas of practice at $DISPLAY." "practice.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>Practice</h2><div class="prose">
<p>We keep a deliberately narrow practice so that the people advising you are the people who know your matter.</p>
<p><b>Private client.</b> Wills, lasting powers of attorney, estate administration and trusts, with an eye to the long term.</p>
<p><b>Commercial.</b> Company formation, shareholder and partnership agreements, terms of business and general commercial advice for owner-managed companies.</p>
<p><b>Property.</b> Sales, purchases, leases and the occasional boundary dispute, conducted at a sensible pace.</p>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/practice.html"

{ emit_head "People — $DISPLAY" "The people of $DISPLAY." "people.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>People</h2><div class="people">
<div class="person"><div class="n">$BRAND</div><div class="r">Principal · Private Client</div></div>
<div class="person"><div class="n">A. Reyes</div><div class="r">Partner · Commercial</div></div>
<div class="person"><div class="n">H. Lindqvist</div><div class="r">Associate · Property</div></div>
<div class="person"><div class="n">M. Okonkwo</div><div class="r">Practice Manager</div></div>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/people.html"

{ emit_head "Contact — $DISPLAY" "Contact $DISPLAY in $CITY." "contact.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>Contact</h2><div class="prose">
<p>New enquiries are welcome by email and we aim to reply within two working days.</p>
<p><a class="email" href="mailto:enquiries@$DOMAIN">enquiries@$DOMAIN</a></p>
<p>$DISPLAY, $CITY. By appointment.</p>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/contact.html"

SITEMAP_PATHS=( "" "practice.html" "people.html" "contact.html" )
}

# =============================================================================
#  THEME 4 — Contractor (industrial, bold)
# =============================================================================
gen_contractor() {
DISPLAY="$BRAND Construction"
cat > "$WEBROOT/style.css" <<CSS
:root{--bg:$BG;--ink:$INK;--muted:#5b6168;--line:#dcdbd6;--accent:$ACCENT;--dark:#1b1d20;--max:1100px;
 --sans:system-ui,-apple-system,'Segoe UI',Helvetica,Arial,sans-serif}
*{margin:0;padding:0;box-sizing:border-box}html{scroll-behavior:smooth}
body{font-family:var(--sans);background:var(--bg);color:var(--ink);line-height:1.6}
.wrap{max-width:var(--max);margin:0 auto;padding:0 1.6rem}a{color:inherit}
.bar{display:flex;align-items:center;justify-content:space-between}
.site-header{padding:1.3rem 0;border-bottom:2px solid var(--ink)}
.brand{font-weight:800;font-size:1.2rem;letter-spacing:.02em;text-transform:uppercase;text-decoration:none}
.brand span{color:var(--accent)}
nav ul{list-style:none;display:flex;gap:1.6rem}
nav a{text-decoration:none;color:var(--muted);font-size:.86rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
nav a:hover{color:var(--accent)}
.hero{padding:5rem 0;border-bottom:1px solid var(--line)}
.tag{display:inline-block;background:var(--accent);color:#fff;font-size:.74rem;font-weight:800;letter-spacing:.1em;text-transform:uppercase;padding:.35rem .8rem;margin-bottom:1.5rem}
h1{font-size:clamp(2.4rem,6.5vw,4.2rem);line-height:1.02;font-weight:800;letter-spacing:-.02em;text-transform:uppercase;max-width:16ch}
.lead{margin-top:1.5rem;max-width:54ch;color:var(--muted);font-size:1.12rem}
.stats{margin-top:2.6rem;display:flex;gap:3rem;flex-wrap:wrap}
.stat .n{font-size:2rem;font-weight:800;color:var(--accent)}
.stat .l{font-size:.85rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
section{padding:4rem 0;border-bottom:1px solid var(--line)}
h2{font-size:1.7rem;font-weight:800;text-transform:uppercase;letter-spacing:-.01em;margin-bottom:1.6rem}
.svc{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.4rem}
.box{border:1px solid var(--line);border-top:3px solid var(--accent);padding:1.6rem;background:#fff}
.box h3{font-size:1.1rem;font-weight:800;text-transform:uppercase;margin-bottom:.5rem}
.box p{color:var(--muted);font-size:.94rem}
.proj{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:1.2rem}
.proj .p{border:1px solid var(--line);padding:1.3rem;background:#fff}
.proj .p .t{font-weight:800}
.proj .p .m{color:var(--muted);font-size:.88rem;margin-top:.2rem}
.prose p{max-width:60ch;color:var(--muted);margin-top:1rem}
.email{color:var(--accent);text-decoration:none;font-weight:800}
.site-footer{padding:2.2rem 0;color:var(--muted);font-size:.84rem;border-top:2px solid var(--ink)}
@media(max-width:640px){nav{display:none}.hero{padding:3.4rem 0}}
CSS

local HDR FTR YEARS
YEARS=$(( 2026 - YEAR ))
HDR=$(cat <<H
<header class="site-header"><div class="wrap bar">
<a class="brand" href="/">$BRAND <span>Construction</span></a>
<nav aria-label="Primary"><ul><li><a href="/services.html">Services</a></li><li><a href="/projects.html">Projects</a></li><li><a href="/contact.html">Contact</a></li></ul></nav>
</div></header>
H
)
FTR=$(cat <<F
<footer class="site-footer"><div class="wrap bar"><span>&copy; $YEAR $DISPLAY · $CITY</span><span>Fully insured &middot; Est. $YEAR</span></div></footer></body></html>
F
)

{ emit_head "$DISPLAY — Building &amp; renovation in $CITY" "$DISPLAY is a $CITY building contractor delivering extensions, renovations and commercial fit-outs since $YEAR." ""
  echo "$HDR"
cat <<H
<main>
<div class="hero"><div class="wrap">
<span class="tag">Building &amp; Renovation · $CITY</span>
<h1>Built properly, the first time.</h1>
<p class="lead">A $CITY contractor handling extensions, full renovations and commercial fit-outs — on schedule, on budget, and tidy when we leave.</p>
<div class="stats"><div class="stat"><div class="n">${YEARS}+</div><div class="l">Years trading</div></div><div class="stat"><div class="n">200+</div><div class="l">Projects delivered</div></div><div class="stat"><div class="n">100%</div><div class="l">Fully insured</div></div></div>
</div></div>
<section><div class="wrap"><h2>What we do</h2><div class="svc">
<div class="box"><h3>Extensions</h3><p>Single and double-storey extensions from groundworks to finish, with one team throughout.</p></div>
<div class="box"><h3>Renovations</h3><p>Full property refurbishments, structural work and conversions, managed end to end.</p></div>
<div class="box"><h3>Commercial</h3><p>Shop and office fit-outs delivered around your trading hours where needed.</p></div>
</div></div></section>
</main>
H
  echo "$FTR"
} > "$WEBROOT/index.html"

{ emit_head "Services — $DISPLAY" "Building services from $DISPLAY in $CITY." "services.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>Services</h2><div class="prose">
<p>We work as a single point of responsibility — one contract, one team, one site manager — so you always know who to call.</p>
<p><b>Extensions.</b> Design coordination, building control, groundworks, structure and finishes.</p>
<p><b>Renovations.</b> Whole-house refurbishment, kitchens and bathrooms, structural alterations and loft conversions.</p>
<p><b>Commercial.</b> Office and retail fit-out, partitions, services and reinstatement.</p>
<p>All work is fully insured and carried out to current building regulations.</p>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/services.html"

{ emit_head "Projects — $DISPLAY" "Recent projects by $DISPLAY." "projects.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>Recent projects</h2><div class="proj">
<div class="p"><div class="t">Victorian rear extension</div><div class="m">$CITY · 2024</div></div>
<div class="p"><div class="t">Two-storey side return</div><div class="m">$CITY · 2023</div></div>
<div class="p"><div class="t">Café fit-out</div><div class="m">$CITY · 2023</div></div>
<div class="p"><div class="t">Full house renovation</div><div class="m">$CITY · 2022</div></div>
<div class="p"><div class="t">Loft conversion</div><div class="m">$CITY · 2022</div></div>
<div class="p"><div class="t">Office refurbishment</div><div class="m">$CITY · 2021</div></div>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/projects.html"

{ emit_head "Contact — $DISPLAY" "Get a quote from $DISPLAY in $CITY." "contact.html"
  echo "$HDR"
cat <<H
<main><section><div class="wrap"><h2>Contact</h2><div class="prose">
<p>For a site visit and quote, send a few details and we'll get back within two working days.</p>
<p><a class="email" href="mailto:office@$DOMAIN">office@$DOMAIN</a></p>
<p>$DISPLAY · $CITY · Mon–Fri, 8:00 – 17:00</p>
</div></div></section></main>
H
  echo "$FTR"
} > "$WEBROOT/contact.html"

SITEMAP_PATHS=( "" "services.html" "projects.html" "contact.html" )
}

# ---- run the selected generator ----
echo -e "${CYAN}[*] Generating site (${STUB_THEME})...${NC}"
case "$STUB_THEME" in
    studio)     gen_studio ;;
    coffee)     gen_coffee ;;
    law)        gen_law ;;
    contractor) gen_contractor ;;
esac

# ---- 404 page (theme-agnostic, uses /style.css) ----
{ emit_head "Page not found" "" "404.html"
cat <<H
<main><section><div class="wrap" style="padding:4rem 0;text-align:center">
<h1 style="max-width:none">404</h1>
<p class="lead" style="margin-left:auto;margin-right:auto">We couldn&rsquo;t find that page.</p>
<p style="margin-top:1.4rem"><a class="email" href="/">Return home</a></p>
</div></section></main></body></html>
H
} > "$WEBROOT/404.html"

# ---- robots.txt ----
cat > "$WEBROOT/robots.txt" <<ROBOTS
User-agent: *
Allow: /
Sitemap: https://$DOMAIN/sitemap.xml
ROBOTS

# ---- sitemap.xml ----
TODAY=$(date -u +%Y-%m-%d)
{
  echo '<?xml version="1.0" encoding="UTF-8"?>'
  echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
  for p in "${SITEMAP_PATHS[@]}"; do
    echo "  <url><loc>https://$DOMAIN/$p</loc><lastmod>$TODAY</lastmod></url>"
  done
  echo '</urlset>'
} > "$WEBROOT/sitemap.xml"

# ---- security.txt ----
EXPIRES=$(date -u -d "+365 days" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u +%Y-%m-%dT%H:%M:%SZ)
cat > "$WEBROOT/.well-known/security.txt" <<SEC
Contact: mailto:security@$DOMAIN
Expires: $EXPIRES
Preferred-Languages: en
SEC

echo -e "${GREEN}[✓] Site generated: $(ls -1 "$WEBROOT" | wc -l) files + .well-known/security.txt${NC}"

# =============================================================================
#  Caddy config (hardened)
# =============================================================================
echo -e "${CYAN}[*] Writing Caddy config...${NC}"
mkdir -p "$(dirname "$CADDYFILE")"
[[ -f "$CADDYFILE" ]] && cp "$CADDYFILE" "${CADDYFILE}.bak.$(date +%s)"

cat > "$CADDYFILE" <<CADDY
{
    admin off
    http_port 80
    https_port 8443
    servers {
        protocols h1 h2
    }
}

# HTTP :80 — ACME challenge; everything else redirected to plain https
# (port 443). The public surface looks like an ordinary site on 443;
# Xray Reality fronts this backend for probes. No :8443 in Location.
$DOMAIN:80 {
    redir https://$DOMAIN{uri} permanent
}

# HTTPS backend on 127.0.0.1:8443 — what Reality proxies probes to.
$DOMAIN:8443 {
    root * $WEBROOT
    encode zstd gzip

    header {
        -Server
        -Alt-Svc
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
        Referrer-Policy "strict-origin-when-cross-origin"
        Cache-Control "public, max-age=600"
    }

    # Real sites 404 on unknown paths. Serve the on-brand 404 page but
    # KEEP the real status code (no blanket 200 / SPA fallback).
    handle_errors {
        rewrite * /404.html
        file_server {
            status {err.status_code}
        }
    }

    file_server
}
CADDY

if [[ "$DRY_RUN" == "1" ]]; then
    command -v caddy &>/dev/null && caddy fmt --overwrite "$CADDYFILE" >/dev/null 2>&1 || true
    echo -e "${GREEN}[✓] DRY_RUN: files in ${WEBROOT}, config at ${CADDYFILE}${NC}"
    exit 0
fi

caddy fmt --overwrite "$CADDYFILE" >/dev/null 2>&1 || true
if caddy validate --config "$CADDYFILE" >/dev/null 2>&1; then
    echo -e "${GREEN}[✓] Caddyfile validated${NC}"
else
    echo -e "${YELLOW}[!] caddy validate reported issues — check ${CADDYFILE}${NC}"
fi

# ---- firewall ----
echo -e "${CYAN}[*] Configuring firewall...${NC}"
if command -v ufw &>/dev/null; then
    ufw allow 80/tcp  >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw delete allow 8443/tcp >/dev/null 2>&1 || true
    echo -e "${GREEN}[✓] UFW: 80,443 open · 8443 internal only${NC}"
else
    echo -e "${YELLOW}[!] UFW not found — ensure only 80 and 443 are publicly open${NC}"
fi

# ---- start ----
echo -e "${CYAN}[*] Starting Caddy...${NC}"
systemctl enable caddy >/dev/null 2>&1
systemctl restart caddy
sleep 5
if systemctl is-active --quiet caddy; then
    echo -e "${GREEN}[✓] Caddy is running${NC}"
else
    echo -e "${RED}[✗] Caddy failed to start — journalctl -u caddy --no-pager -n 20${NC}"
    exit 1
fi

# ---- verify ----
ROOT_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DOMAIN:8443/" 2>/dev/null || echo 000)
NF_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://$DOMAIN:8443/nope-$RANDOM" 2>/dev/null || echo 000)
[[ "$ROOT_CODE" == "200" ]] && echo -e "${GREEN}[✓] Homepage → 200${NC}" \
    || echo -e "${YELLOW}[!] Homepage → ${ROOT_CODE} (cert may still be issuing)${NC}"
[[ "$NF_CODE" == "404" ]] && echo -e "${GREEN}[✓] Unknown path → 404${NC}" \
    || echo -e "${YELLOW}[!] Unknown path → ${NF_CODE} (expected 404)${NC}"

# ---- summary ----
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✓ Installation Complete              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Domain:${NC}  ${CYAN}${DOMAIN}${NC}"
echo -e "  ${BOLD}Site:${NC}    ${CYAN}${STUB_THEME} · ${BRAND} · ${CITY} · est. ${YEAR}${NC}"
echo -e "  ${BOLD}Backend:${NC} ${CYAN}https://127.0.0.1:8443${NC} (local only)"
echo ""
echo -e "  ${YELLOW}━━━ Update Xray / Remnawave node config ━━━${NC}"
echo -e "    \"target\":      ${GREEN}\"127.0.0.1:8443\"${NC}"
echo -e "    \"serverNames\": ${GREEN}[\"${DOMAIN}\"]${NC}"
echo ""
echo -e "  ${BOLD}Public ports:${NC} 80 (cert+redirect), 443 (Xray Reality)"
echo -e "  ${BOLD}Internal:${NC}     8443 (Caddy, localhost)"
echo -e "  ${DIM}HTTP/3 off · admin off · Server hidden · honest 404s${NC}"
echo -e "  ${DIM}Note: 'admin off' disables 'systemctl reload caddy' — use restart.${NC}"
echo ""
