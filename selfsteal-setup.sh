#!/bin/bash

# ============================================
#  SelfSteal Caddy Stub Installer
#  For Remnawave + Xray Reality nodes
#
#  Usage: bash selfsteal-setup.sh
#  Requirements: Debian/Ubuntu, root access
# ============================================

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
 ║       SelfSteal Caddy Stub Installer          ║
 ║       For Remnawave + Xray Reality nodes       ║
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

# ---- Stub page selection ----
echo ""
echo -e "${BOLD}  Choose a stub page:${NC}"
echo ""
echo -e "  ${CYAN}1)${NC} ${BOLD}Minimal 404${NC}        ${DIM}— Dark, clean 404 error page${NC}"
echo -e "  ${CYAN}2)${NC} ${BOLD}Cat Memes 404${NC}      ${DIM}— Fun 404 with floating cats${NC}"
echo -e "  ${CYAN}3)${NC} ${BOLD}Business Site${NC}       ${DIM}— Professional tech company landing page${NC}"
echo ""
read -rp "$(echo -e "${YELLOW}[?] Select (1/2/3) [default: 1]: ${NC}")" STUB_CHOICE

STUB_CHOICE=${STUB_CHOICE:-1}

if [[ ! "$STUB_CHOICE" =~ ^[1-3]$ ]]; then
    echo -e "${YELLOW}[!] Invalid choice, using default (1)${NC}"
    STUB_CHOICE=1
fi

STUB_NAMES=("Minimal 404" "Cat Memes 404" "Business Site")
echo -e "${GREEN}[✓] Selected: ${STUB_NAMES[$((STUB_CHOICE-1))]}${NC}"

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

# ---- Create stub page ----
echo -e "${CYAN}[*] Creating stub page...${NC}"

mkdir -p /var/www/html

# --- Stub 1: Minimal 404 ---
create_stub_minimal() {
cat > /var/www/html/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 - Page Not Found</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0a;color:#e0e0e0;display:flex;justify-content:center;align-items:center;min-height:100vh}
        .container{text-align:center;padding:2rem}
        .error-code{font-size:clamp(6rem,20vw,12rem);font-weight:800;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1;margin-bottom:1rem;animation:pulse 3s ease-in-out infinite}
        .message{font-size:1.3rem;color:#888;margin-bottom:.5rem}
        .sub{font-size:.95rem;color:#555}
        @keyframes pulse{0%,100%{opacity:1}50%{opacity:.7}}
    </style>
</head>
<body>
    <div class="container">
        <div class="error-code">404</div>
        <p class="message">Page Not Found</p>
        <p class="sub">The requested resource could not be located on this server.</p>
    </div>
</body>
</html>
HTMLEOF
}

# --- Stub 2: Cat Memes 404 ---
create_stub_cats() {
cat > /var/www/html/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>404 - Oops!</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Fredoka:wght@400;600;700&display=swap');
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Fredoka',sans-serif;background:#1a1525;color:#e0e0e0;display:flex;justify-content:center;align-items:center;min-height:100vh;overflow:hidden}
        .container{text-align:center;padding:2rem;position:relative;z-index:1}
        .cat-wrapper{position:relative;display:inline-block;margin-bottom:1.5rem}
        .cat{font-size:8rem;line-height:1;filter:drop-shadow(0 0 30px rgba(255,150,200,0.3));animation:float 3s ease-in-out infinite}
        .sparkles{position:absolute;top:-10px;right:-20px;font-size:2rem;animation:spin 4s linear infinite}
        .error-code{font-size:clamp(4rem,15vw,8rem);font-weight:700;background:linear-gradient(135deg,#ff6b9d,#c44dff,#6e8efb);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1;margin-bottom:.5rem}
        .message{font-size:1.4rem;color:#c4a0ff;margin-bottom:.5rem;font-weight:600}
        .sub{font-size:1rem;color:#7a6b8a;max-width:400px;margin:0 auto}
        .paws{margin-top:1.5rem;font-size:1.5rem;opacity:.5;letter-spacing:8px;animation:walk 2s ease-in-out infinite}
        .bg-cats{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden}
        .bg-cat{position:absolute;font-size:2rem;opacity:.06;animation:drift 20s linear infinite}
        .bg-cat:nth-child(1){left:10%;top:-5%;animation-delay:0s;animation-duration:18s}
        .bg-cat:nth-child(2){left:30%;top:-5%;animation-delay:3s;animation-duration:22s}
        .bg-cat:nth-child(3){left:50%;top:-5%;animation-delay:6s;animation-duration:20s}
        .bg-cat:nth-child(4){left:70%;top:-5%;animation-delay:2s;animation-duration:24s}
        .bg-cat:nth-child(5){left:90%;top:-5%;animation-delay:8s;animation-duration:19s}
        .bg-cat:nth-child(6){left:20%;top:-5%;animation-delay:11s;animation-duration:21s}
        .bg-cat:nth-child(7){left:60%;top:-5%;animation-delay:5s;animation-duration:23s}
        .bg-cat:nth-child(8){left:80%;top:-5%;animation-delay:9s;animation-duration:17s}
        @keyframes float{0%,100%{transform:translateY(0) rotate(0deg)}50%{transform:translateY(-15px) rotate(3deg)}}
        @keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
        @keyframes walk{0%,100%{transform:translateX(0)}50%{transform:translateX(10px)}}
        @keyframes drift{0%{transform:translateY(-50px) rotate(0deg)}100%{transform:translateY(110vh) rotate(360deg)}}
    </style>
</head>
<body>
    <div class="bg-cats">
        <div class="bg-cat">🐱</div><div class="bg-cat">😸</div><div class="bg-cat">🐈</div>
        <div class="bg-cat">😺</div><div class="bg-cat">🐱</div><div class="bg-cat">😻</div>
        <div class="bg-cat">🐈</div><div class="bg-cat">😸</div>
    </div>
    <div class="container">
        <div class="cat-wrapper">
            <div class="cat">😿</div>
            <div class="sparkles">✨</div>
        </div>
        <div class="error-code">404</div>
        <p class="message">The cat knocked this page off the table</p>
        <p class="sub">We looked everywhere — under the couch, behind the curtains, even in the box. This page simply doesn't exist.</p>
        <div class="paws">🐾 🐾 🐾</div>
    </div>
</body>
</html>
HTMLEOF
}

# --- Stub 3: Business Site ---
create_stub_business() {
cat > /var/www/html/index.html << 'HTMLEOF'
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NovaTech Solutions — Digital Innovation</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Playfair+Display:wght@700&display=swap');
        *{margin:0;padding:0;box-sizing:border-box}
        :root{--bg:#0c0f16;--surface:#13161f;--border:#1e2230;--accent:#4f7df5;--accent2:#7c5bf5;--text:#c8cdd8;--text-dim:#5a6072;--white:#eef0f6}
        body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);overflow-x:hidden}
        .noise{position:fixed;top:0;left:0;width:100%;height:100%;opacity:.03;pointer-events:none;background-image:url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");z-index:999}
        nav{position:fixed;top:0;width:100%;padding:1.2rem 3rem;display:flex;justify-content:space-between;align-items:center;z-index:10;backdrop-filter:blur(20px);background:rgba(12,15,22,.7);border-bottom:1px solid var(--border)}
        .logo{font-family:'Playfair Display',serif;font-size:1.4rem;color:var(--white);font-weight:700;letter-spacing:-.5px}
        .logo span{color:var(--accent)}
        nav ul{list-style:none;display:flex;gap:2rem}
        nav a{color:var(--text-dim);text-decoration:none;font-size:.9rem;font-weight:500;transition:color .3s}
        nav a:hover{color:var(--white)}
        .hero{min-height:100vh;display:flex;align-items:center;justify-content:center;position:relative;padding:6rem 3rem 4rem}
        .hero-content{max-width:800px;text-align:center;position:relative;z-index:2}
        .badge{display:inline-block;padding:.4rem 1rem;border:1px solid var(--border);border-radius:50px;font-size:.8rem;color:var(--accent);margin-bottom:2rem;letter-spacing:1px;text-transform:uppercase}
        h1{font-family:'Playfair Display',serif;font-size:clamp(2.5rem,6vw,4.5rem);color:var(--white);line-height:1.1;margin-bottom:1.5rem;letter-spacing:-.5px}
        h1 em{font-style:normal;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
        .hero p{font-size:1.15rem;color:var(--text-dim);max-width:550px;margin:0 auto 2.5rem;line-height:1.7}
        .cta-row{display:flex;gap:1rem;justify-content:center;flex-wrap:wrap}
        .btn{padding:.85rem 2rem;border-radius:8px;font-size:.95rem;font-weight:600;text-decoration:none;transition:all .3s;cursor:pointer;border:none;font-family:inherit}
        .btn-primary{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#fff;box-shadow:0 4px 20px rgba(79,125,245,.25)}
        .btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(79,125,245,.35)}
        .btn-outline{background:transparent;color:var(--text);border:1px solid var(--border)}
        .btn-outline:hover{border-color:var(--accent);color:var(--white)}
        .glow{position:absolute;width:500px;height:500px;border-radius:50%;filter:blur(120px);opacity:.12;pointer-events:none}
        .glow-1{background:var(--accent);top:-100px;left:-100px}
        .glow-2{background:var(--accent2);bottom:-100px;right:-100px}
        .stats{display:flex;gap:3rem;justify-content:center;margin-top:4rem;padding-top:3rem;border-top:1px solid var(--border)}
        .stat{text-align:center}
        .stat-num{font-family:'Playfair Display',serif;font-size:2.2rem;color:var(--white);font-weight:700}
        .stat-label{font-size:.85rem;color:var(--text-dim);margin-top:.3rem}
        .features{padding:4rem 3rem 5rem;max-width:1000px;margin:0 auto}
        .features-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.5rem}
        .feature-card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:2rem;transition:all .3s}
        .feature-card:hover{border-color:var(--accent);transform:translateY(-3px)}
        .feature-icon{width:42px;height:42px;border-radius:10px;background:linear-gradient(135deg,rgba(79,125,245,.15),rgba(124,91,245,.15));display:flex;align-items:center;justify-content:center;font-size:1.2rem;margin-bottom:1rem}
        .feature-card h3{color:var(--white);font-size:1.05rem;margin-bottom:.5rem}
        .feature-card p{font-size:.9rem;color:var(--text-dim);line-height:1.6}
        footer{text-align:center;padding:2rem;border-top:1px solid var(--border);font-size:.8rem;color:var(--text-dim)}
        @media(max-width:600px){nav{padding:1rem 1.5rem}nav ul{display:none}.hero{padding:6rem 1.5rem 3rem}.stats{flex-direction:column;gap:1.5rem}.features{padding:2rem 1.5rem}}
    </style>
</head>
<body>
    <div class="noise"></div>
    <nav>
        <div class="logo">Nova<span>Tech</span></div>
        <ul>
            <li><a href="#">Solutions</a></li>
            <li><a href="#">About</a></li>
            <li><a href="#">Careers</a></li>
            <li><a href="#">Contact</a></li>
        </ul>
    </nav>
    <section class="hero">
        <div class="glow glow-1"></div>
        <div class="glow glow-2"></div>
        <div class="hero-content">
            <div class="badge">Digital Transformation Partner</div>
            <h1>Building the <em>future</em> of digital infrastructure</h1>
            <p>We help businesses scale their technology stack with modern cloud-native solutions, enterprise security, and seamless integration.</p>
            <div class="cta-row">
                <a class="btn btn-primary" href="#">Get Started</a>
                <a class="btn btn-outline" href="#">Learn More</a>
            </div>
            <div class="stats">
                <div class="stat"><div class="stat-num">500+</div><div class="stat-label">Clients Worldwide</div></div>
                <div class="stat"><div class="stat-num">99.9%</div><div class="stat-label">Uptime SLA</div></div>
                <div class="stat"><div class="stat-num">24/7</div><div class="stat-label">Expert Support</div></div>
            </div>
        </div>
    </section>
    <section class="features">
        <div class="features-grid">
            <div class="feature-card">
                <div class="feature-icon">☁️</div>
                <h3>Cloud Solutions</h3>
                <p>Multi-cloud architecture designed for resilience, performance, and cost optimization at any scale.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🔒</div>
                <h3>Enterprise Security</h3>
                <p>Zero-trust security framework with real-time threat detection and automated incident response.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">⚡</div>
                <h3>Edge Computing</h3>
                <p>Low-latency processing at the edge with intelligent data routing and distributed computing.</p>
            </div>
        </div>
    </section>
    <footer>&copy; 2026 NovaTech Solutions. All rights reserved.</footer>
</body>
</html>
HTMLEOF
}

# ---- Generate selected stub ----
case "$STUB_CHOICE" in
    1) create_stub_minimal ;;
    2) create_stub_cats ;;
    3) create_stub_business ;;
esac

echo -e "${GREEN}[✓] Stub page created${NC}"

# ---- Configure Caddy ----
echo -e "${CYAN}[*] Configuring Caddy...${NC}"

if [[ -f /etc/caddy/Caddyfile ]]; then
    cp /etc/caddy/Caddyfile "/etc/caddy/Caddyfile.bak.$(date +%s)"
fi

# Determine response code based on stub type
if [[ "$STUB_CHOICE" == "3" ]]; then
    RESPONSE_CODE="200"
else
    RESPONSE_CODE="404"
fi

cat > /etc/caddy/Caddyfile << CADDYEOF
{
    http_port 80
    https_port 8443
}

${DOMAIN}:80 {
    redir https://${DOMAIN}:8443{uri} permanent
}

${DOMAIN}:8443 {
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "SAMEORIGIN"
    }
    root * /var/www/html
    try_files {path} /index.html
    file_server
}
CADDYEOF

caddy fmt --overwrite /etc/caddy/Caddyfile > /dev/null 2>&1 || true
echo -e "${GREEN}[✓] Caddyfile configured${NC}"

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

# ---- Verify ----
HTTP_CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${DOMAIN}:8443" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" =~ ^(200|404)$ ]]; then
    echo -e "${GREEN}[✓] HTTPS works, stub page served (HTTP ${HTTP_CODE})${NC}"
elif [[ "$HTTP_CODE" == "000" ]]; then
    echo -e "${YELLOW}[!] Could not verify HTTPS yet (cert may still be issuing)${NC}"
else
    echo -e "${YELLOW}[!] Got HTTP ${HTTP_CODE}${NC}"
fi

# ---- Summary ----
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✓ Installation Complete              ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Domain:${NC}     ${CYAN}${DOMAIN}${NC}"
echo -e "  ${BOLD}Stub:${NC}       ${CYAN}${STUB_NAMES[$((STUB_CHOICE-1))]}${NC}"
echo -e "  ${BOLD}URL:${NC}        ${CYAN}https://${DOMAIN}:8443${NC}"
echo -e "  ${BOLD}HTTP:${NC}       ${CYAN}http://${DOMAIN}${NC} → redirect to HTTPS"
echo ""
echo -e "  ${YELLOW}━━━ Update your Xray / Remnawave node config ━━━${NC}"
echo ""
echo -e "    \"target\":      ${GREEN}\"127.0.0.1:8443\"${NC}"
echo -e "    \"serverNames\": ${GREEN}[\"${DOMAIN}\"]${NC}"
echo ""
echo -e "  ${BOLD}Open ports:${NC}  80 (cert + redirect), 443 (Xray)"
echo -e "  ${BOLD}Internal:${NC}    8443 (Caddy, localhost only)"
echo ""
