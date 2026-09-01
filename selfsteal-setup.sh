#!/usr/bin/env bash
# =============================================================================
#  SelfstealCaddy — technical web service generator for Reality self-steal
#
#  Interface (unchanged from 1.x):
#     bash selfsteal-setup.sh                                  # interactive
#     DOMAIN=ex.com STUB_THEME=random bash selfsteal-setup.sh  # non-interactive
#     DRY_RUN=1 DOMAIN=ex.com STUB_THEME=cdn WEBROOT=/tmp/site \
#         CADDYFILE=/tmp/Caddyfile bash selfsteal-setup.sh     # preview only
#
#  New, all optional:
#     STUB_SEED=...     pin or rotate the installation identity
#     HTTPS_PORT=8443   local backend port Reality points at
#     DEBUG=1           shell trace and full error output
#     ASSUME_YES=1      never prompt
#     BIND_ADDR=127.0.0.1  interface the backend listens on ("" = all)
#     UNINSTALL=1       remove generated files and restore the Caddy config
#
#  Requirements: Debian 12/13 or Ubuntu LTS, python3 (stdlib only), root.
# =============================================================================

set -Eeuo pipefail

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'
CYAN=$'\033[0;36m'; BOLD=$'\033[1m'; DIM=$'\033[2m'; NC=$'\033[0m'

WEBROOT="${WEBROOT:-/var/www/html}"
CADDYFILE="${CADDYFILE:-/etc/caddy/Caddyfile}"
DRY_RUN="${DRY_RUN:-0}"
DEBUG="${DEBUG:-0}"
ASSUME_YES="${ASSUME_YES:-0}"
UNINSTALL="${UNINSTALL:-0}"
HTTPS_PORT="${HTTPS_PORT:-8443}"
BIND_ADDR="${BIND_ADDR:-127.0.0.1}"
ADMIN_SOCKET="${ADMIN_SOCKET:-/run/caddy/admin.sock}"
STUB_SEED="${STUB_SEED:-}"

[[ "$DEBUG" == "1" ]] && set -x

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR=""
TMP_PKG=""
STAGE=""

log()  { printf '%s[*]%s %s\n' "$CYAN" "$NC" "$*"; }
ok()   { printf '%s[✓]%s %s\n' "$GREEN" "$NC" "$*"; }
warn() { printf '%s[!]%s %s\n' "$YELLOW" "$NC" "$*" >&2; }
die()  { printf '%s[✗]%s %s\n' "$RED" "$NC" "$*" >&2; exit 1; }

on_error() {
    local code=$? line=${BASH_LINENO[0]}
    if [[ "$DEBUG" == "1" ]]; then
        printf '%s[✗]%s failed at line %s (exit %s)\n' "$RED" "$NC" "$line" "$code" >&2
    else
        printf '%s[✗]%s Установка прервана. Запустите с DEBUG=1 для подробностей.\n' \
            "$RED" "$NC" >&2
    fi
    exit "$code"
}
trap on_error ERR
trap '[[ -n "$TMP_PKG" ]] && rm -rf "$TMP_PKG"; [[ -n "$STAGE" ]] && rm -f "$STAGE"' EXIT

ask() {
    # Returns 0 on yes. Honours ASSUME_YES and a non-interactive stdin, so the
    # script never blocks forever inside an automation pipeline.
    [[ "$ASSUME_YES" == "1" ]] && return 0
    [[ -t 0 ]] || return 1
    local reply
    read -rp "${YELLOW}[?] $1 (y/n): ${NC}" reply
    [[ "$reply" == "y" || "$reply" == "Y" ]]
}

banner() {
    printf '%s' "$CYAN"
    cat <<'BANNER'
 ╔═══════════════════════════════════════════════════╗
 ║   SelfstealCaddy · technical service generator    ║
 ║   deterministic · unique per node · DPI-hardened  ║
 ╚═══════════════════════════════════════════════════╝
BANNER
    printf '%s\n' "$NC"
}

# ---------------------------------------------------------------------------
#  Locate the Python package
# ---------------------------------------------------------------------------
locate_package() {
    if [[ -f "$SCRIPT_DIR/selfsteal/__main__.py" ]]; then
        PKG_DIR="$SCRIPT_DIR"
        return
    fi
    # Bundled single-file release: the payload is appended after the marker.
    if grep -q '^#__SELFSTEAL_PAYLOAD__$' "${BASH_SOURCE[0]}" 2>/dev/null; then
        TMP_PKG="$(mktemp -d)"
        sed -n '/^#__SELFSTEAL_PAYLOAD__$/,$p' "${BASH_SOURCE[0]}" \
            | tail -n +2 | base64 -d | tar xz -C "$TMP_PKG"
        PKG_DIR="$TMP_PKG"
        return
    fi
    die "Не найден пакет selfsteal/. Запускайте скрипт из каталога репозитория
    либо используйте однофайловую сборку из релиза."
}

run_gen() { ( cd "$PKG_DIR" && python3 -m selfsteal "$@" ); }

# ---------------------------------------------------------------------------
#  Preconditions
# ---------------------------------------------------------------------------
require_root() {
    [[ "$DRY_RUN" == "1" ]] && return 0
    [[ $EUID -eq 0 ]] || die "Требуются права root: sudo bash $0"
}

require_python() {
    command -v python3 >/dev/null 2>&1 && return 0
    [[ "$DRY_RUN" == "1" ]] && die "python3 не найден (нужен даже для DRY_RUN)"
    log "Устанавливаю python3..."
    apt-get update -qq
    apt-get install -y --no-install-recommends python3 >/dev/null
    command -v python3 >/dev/null 2>&1 || die "не удалось установить python3"
}

install_deps() {
    [[ "$DRY_RUN" == "1" ]] && return 0
    local missing=()
    command -v curl >/dev/null 2>&1 || missing+=(curl)
    command -v dig  >/dev/null 2>&1 || missing+=(dnsutils)
    command -v gpg  >/dev/null 2>&1 || missing+=(gnupg)
    ((${#missing[@]})) || return 0
    # 1.x ran the DNS check *before* installing dnsutils, so dig was missing
    # exactly when it was first needed and every domain looked unresolvable.
    log "Устанавливаю зависимости: ${missing[*]}"
    apt-get update -qq
    apt-get install -y --no-install-recommends "${missing[@]}" >/dev/null
}

install_caddy() {
    [[ "$DRY_RUN" == "1" ]] && return 0
    if command -v caddy >/dev/null 2>&1; then
        ok "Caddy уже установлен ($(caddy version 2>/dev/null | awk '{print $1}'))"
        return 0
    fi
    log "Устанавливаю Caddy..."
    apt-get install -y --no-install-recommends \
        debian-keyring debian-archive-keyring apt-transport-https ca-certificates >/dev/null
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y caddy >/dev/null
    command -v caddy >/dev/null 2>&1 || die "не удалось установить Caddy"
    ok "Caddy установлен"
}

configure_runtime_dir() {
    # The admin endpoint is a unix socket, which needs /run/caddy to exist and
    # to be recreated on boot. A drop-in is idempotent and leaves the packaged
    # unit file untouched.
    [[ "$DRY_RUN" == "1" ]] && return 0
    local dir="/etc/systemd/system/caddy.service.d"
    local file="$dir/10-selfsteal-runtime.conf"
    local want="[Service]
RuntimeDirectory=caddy
RuntimeDirectoryMode=0750
"
    mkdir -p "$dir"
    if [[ ! -f "$file" ]] || [[ "$(cat "$file")" != "$want" ]]; then
        printf '%s' "$want" > "$file"
        systemctl daemon-reload
        ok "systemd drop-in: RuntimeDirectory=caddy"
    fi
}

# ---------------------------------------------------------------------------
#  Domain and DNS
# ---------------------------------------------------------------------------
resolve_server_ip() {
    # Prefer the local routing table over a third-party echo service: one fewer
    # outbound request from the node, and no dependency on someone else's API.
    local ip
    ip="$(ip -4 route get 1.1.1.1 2>/dev/null \
          | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -1)"
    [[ -n "$ip" ]] || ip="$(curl -s4 --max-time 5 https://api.ipify.org 2>/dev/null || true)"
    printf '%s' "${ip:-unknown}"
}

check_dns() {
    [[ "$DRY_RUN" == "1" ]] && return 0
    log "Проверяю DNS для ${DOMAIN}..."
    local server_ip a_records aaaa_records
    server_ip="$(resolve_server_ip)"
    a_records="$(dig +short "$DOMAIN" A 2>/dev/null | grep -E '^[0-9.]+$' || true)"
    aaaa_records="$(dig +short "$DOMAIN" AAAA 2>/dev/null | grep -E '^[0-9a-f:]+$' || true)"

    if [[ -z "$a_records$aaaa_records" ]]; then
        warn "${DOMAIN} не резолвится. A-запись должна указывать на ${server_ip}"
        ask "Продолжить?" || die "прервано пользователем"
        return 0
    fi
    if grep -qx "$server_ip" <<<"$a_records"; then
        ok "DNS: ${DOMAIN} → ${server_ip}"
        return 0
    fi
    if [[ -n "$aaaa_records" && -z "$a_records" ]]; then
        ok "DNS: ${DOMAIN} → только AAAA (${aaaa_records//$'\n'/, })"
        return 0
    fi
    warn "${DOMAIN} → ${a_records//$'\n'/, }, IP сервера ${server_ip}"
    warn "Если домен за CDN — это ожидаемо. Иначе ACME не выпустит сертификат."
    ask "Продолжить?" || die "прервано пользователем"
}

# ---------------------------------------------------------------------------
#  Caddy config lifecycle
# ---------------------------------------------------------------------------
apply_caddy_config() {
    local candidate="$1" backup=""

    if ! caddy validate --adapter caddyfile --config "$candidate" >/dev/null 2>&1; then
        caddy validate --adapter caddyfile --config "$candidate" 2>&1 | tail -20 >&2
        die "Сгенерированный Caddyfile невалиден. Рабочая конфигурация НЕ тронута."
    fi
    ok "Caddyfile прошёл валидацию"

    if [[ -f "$CADDYFILE" ]]; then
        backup="${CADDYFILE}.bak.$(date -u +%Y%m%dT%H%M%SZ)"
        cp -a "$CADDYFILE" "$backup"
        # Keep five backups; 1.x accumulated one per run indefinitely.
        ls -1t "${CADDYFILE}".bak.* 2>/dev/null | tail -n +6 | xargs -r rm -f
    fi

    install -m 0644 "$candidate" "$CADDYFILE"
    caddy fmt --overwrite "$CADDYFILE" >/dev/null 2>&1 || true

    systemctl enable caddy >/dev/null 2>&1 || true
    if systemctl is-active --quiet caddy; then
        # A reload keeps the Reality dest answering throughout. This is the
        # reason the admin endpoint moved from `off` to a unix socket: a
        # restart leaves a window where probes get connection refused.
        if caddy reload --adapter caddyfile --config "$CADDYFILE" >/dev/null 2>&1; then
            ok "Caddy перезагружен без простоя"
        else
            # Expected exactly once, when upgrading from a configuration that
            # had `admin off`: the *running* process has no admin endpoint to
            # reload through. Subsequent runs reload cleanly.
            warn "reload недоступен у запущенного процесса — выполняю restart"
            warn "(ожидаемо при первом обновлении со старого конфига; далее reload заработает)"
            systemctl restart caddy
        fi
    else
        systemctl restart caddy
    fi

    sleep 2
    if ! systemctl is-active --quiet caddy; then
        if [[ -n "$backup" ]]; then
            warn "Caddy не поднялся — откатываю на ${backup}"
            install -m 0644 "$backup" "$CADDYFILE"
            systemctl restart caddy || true
            sleep 2
            if systemctl is-active --quiet caddy; then
                warn "Откат выполнен, работает предыдущая конфигурация"
            else
                warn "Откат не помог: journalctl -u caddy -n 40 --no-pager"
            fi
        fi
        die "Caddy не запустился. journalctl -u caddy -n 40 --no-pager"
    fi
    ok "Caddy работает"
}

verify_live() {
    log "Проверяю поведение сервиса..."
    # The backend is a name-based vhost on loopback: the probe has to dial
    # 127.0.0.1 but present the real hostname, or the TLS handshake has no
    # site to match and fails before a single request is sent.
    if run_gen validate --webroot "$WEBROOT" --domain "$DOMAIN" \
            --base-url "https://${DOMAIN}:${HTTPS_PORT}" \
            --connect "${BIND_ADDR:-127.0.0.1}"; then
        ok "Все проверки пройдены"
    else
        warn "Часть проверок не пройдена (см. выше). Сайт при этом отдаётся."
    fi
}

do_uninstall() {
    log "Удаляю сгенерированные файлы..."
    local manifest="$WEBROOT/.selfsteal-manifest.json"
    if [[ -f "$manifest" ]]; then
        # Only files this tool recorded are removed. Nothing is deleted by glob.
        python3 - "$WEBROOT" "$manifest" <<'PY'
import json, os, sys
root, manifest = sys.argv[1], sys.argv[2]
for name in json.load(open(manifest)).get("files", []):
    try:
        os.remove(os.path.join(root, name))
    except OSError:
        pass
PY
        rm -f "$manifest" "$WEBROOT/.selfsteal-profile.json"
        find "$WEBROOT" -mindepth 1 -type d -empty -delete 2>/dev/null || true
        ok "Файлы сайта удалены"
    else
        warn "Манифест не найден — из ${WEBROOT} ничего не удаляю"
    fi
    if [[ -f "$CADDYFILE" ]]; then
        local last
        last="$(ls -1t "${CADDYFILE}".bak.* 2>/dev/null | head -1 || true)"
        if [[ -n "$last" ]]; then
            install -m 0644 "$last" "$CADDYFILE"
            systemctl reload-or-restart caddy 2>/dev/null || true
            ok "Caddyfile восстановлен из ${last}"
        else
            warn "Бэкап Caddyfile не найден — ${CADDYFILE} оставлен как есть"
        fi
    fi
    rm -f /etc/systemd/system/caddy.service.d/10-selfsteal-runtime.conf
    systemctl daemon-reload 2>/dev/null || true
    ok "Готово"
    exit 0
}

# ---------------------------------------------------------------------------
#  Interactive selection
# ---------------------------------------------------------------------------
choose_theme_interactive() {
    echo
    printf '%s  Выберите тип сайта-заглушки:%s\n\n' "$BOLD" "$NC"
    printf '  %s1)%s %sСлучайно%s      %s— смесь технических и обычных (рекомендуется)%s\n' \
        "$CYAN" "$NC" "$BOLD" "$NC" "$DIM" "$NC"
    printf '  %s2)%s %sТехнический%s   %s— случайный API / CDN / storage сервис%s\n' \
        "$CYAN" "$NC" "$BOLD" "$NC" "$DIM" "$NC"
    printf '  %s3)%s %sОбычный сайт%s  %s— студия / кофейня / юрфирма / подрядчик%s\n' \
        "$CYAN" "$NC" "$BOLD" "$NC" "$DIM" "$NC"
    printf '  %s4)%s %sВыбрать тему%s  %s— полный список%s\n\n' \
        "$CYAN" "$NC" "$BOLD" "$NC" "$DIM" "$NC"
    local choice
    read -rp "${YELLOW}[?] Выбор (1-4) [1]: ${NC}" choice
    case "${choice:-1}" in
        2) STUB_THEME=technical ;;
        3) STUB_THEME=classic ;;
        4)
            echo
            run_gen themes | sed 's/^/  /'
            echo
            read -rp "${YELLOW}[?] Имя темы [random]: ${NC}" STUB_THEME
            STUB_THEME="${STUB_THEME:-random}"
            ;;
        *) STUB_THEME=random ;;
    esac
}

# ---------------------------------------------------------------------------
#  Main
# ---------------------------------------------------------------------------
banner
locate_package
require_root
require_python

[[ "$UNINSTALL" == "1" ]] && do_uninstall

if [[ -z "${DOMAIN:-}" ]]; then
    [[ -t 0 ]] || die "DOMAIN не задан, а интерактивного ввода нет"
    read -rp "${YELLOW}[?] Домен: ${NC}" DOMAIN
fi
DOMAIN="$(tr -d '[:space:]' <<<"${DOMAIN,,}")"
DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN%%/*}"
[[ -n "$DOMAIN" ]] || die "Домен не может быть пустым"

if [[ -z "${STUB_THEME:-}" ]]; then
    if [[ -t 0 ]]; then choose_theme_interactive; else STUB_THEME=random; fi
fi

install_deps
check_dns
install_caddy
configure_runtime_dir

# Generate into a staging Caddyfile: a bad config can never replace a good one.
STAGE="$(mktemp)"
GEN_ARGS=(generate --domain "$DOMAIN" --theme "$STUB_THEME"
          --webroot "$WEBROOT" --caddyfile "$STAGE"
          --https-port "$HTTPS_PORT" --admin-socket "$ADMIN_SOCKET"
          --bind "$BIND_ADDR")
[[ -n "$STUB_SEED" ]] && GEN_ARGS+=(--seed "$STUB_SEED")
[[ "$DRY_RUN" == "1" ]] && GEN_ARGS+=(--dry-run)

log "Генерирую сервис..."
SUMMARY="$(run_gen "${GEN_ARGS[@]}")" || die "генерация не удалась"
echo
printf '%s\n' "$SUMMARY" \
    | sed -e "s#^Caddyfile:.*#Caddyfile:   ${CADDYFILE}#" -e 's/^/  /' 
echo

log "Проверяю сгенерированное дерево..."
run_gen validate --webroot "$WEBROOT" --domain "$DOMAIN" \
    || warn "офлайн-валидация нашла замечания (см. выше)"

if [[ "$DRY_RUN" == "1" ]]; then
    install -m 0644 "$STAGE" "$CADDYFILE"
    ok "DRY_RUN: файлы в ${WEBROOT}, конфиг в ${CADDYFILE}. Система не изменена."
    exit 0
fi

chown -R root:root "$WEBROOT"
find "$WEBROOT" -type d -exec chmod 755 {} + 2>/dev/null || true
find "$WEBROOT" -type f -exec chmod 644 {} + 2>/dev/null || true
chmod 600 "$WEBROOT/.selfsteal-manifest.json" \
          "$WEBROOT/.selfsteal-profile.json" 2>/dev/null || true

apply_caddy_config "$STAGE"

if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow 80/tcp  >/dev/null 2>&1 || true
    ufw allow 443/tcp >/dev/null 2>&1 || true
    ufw delete allow "${HTTPS_PORT}/tcp" >/dev/null 2>&1 || true
    ok "UFW: 80,443 открыты · ${HTTPS_PORT} только локально"
else
    warn "UFW неактивен — убедитесь, что наружу открыты только 80 и 443"
fi

verify_live

echo
printf '%s╔═══════════════════════════════════════════════╗%s\n' "$GREEN" "$NC"
printf '%s║             Установка завершена               ║%s\n' "$GREEN" "$NC"
printf '%s╚═══════════════════════════════════════════════╝%s\n' "$GREEN" "$NC"
echo
printf '  %sДомен:%s   %s%s%s\n' "$BOLD" "$NC" "$CYAN" "$DOMAIN" "$NC"
printf '  %sБэкенд:%s  %shttps://%s:%s%s (слушает только %s)\n' \
    "$BOLD" "$NC" "$CYAN" "$DOMAIN" "$HTTPS_PORT" "$NC" "${BIND_ADDR:-все интерфейсы}"
echo
printf '  %s━━━ Конфигурация ноды Xray / Remnawave ━━━%s\n' "$YELLOW" "$NC"
printf '    "target":      %s"127.0.0.1:%s"%s\n' "$GREEN" "$HTTPS_PORT" "$NC"
printf '    "serverNames": %s["%s"]%s\n' "$GREEN" "$DOMAIN" "$NC"
echo
printf '  %sПорты:%s 80 (ACME + редирект), 443 (Xray Reality), %s (Caddy, localhost)\n' \
    "$BOLD" "$NC" "$HTTPS_PORT"
printf '  %sПовтор установки идемпотентен: тот же домен → тот же сайт.%s\n' "$DIM" "$NC"
printf '  %sСменить личность ноды: STUB_SEED=<строка> bash %s%s\n' "$DIM" "$0" "$NC"
echo
