# SelfSteal Caddy Stub

Скрипт автоматической установки **SelfSteal** заглушки для нод [Remnawave](https://github.com/remnawave) + Xray Reality.

Устанавливает [Caddy](https://caddyserver.com/) как локальный HTTPS-бэкенд с заглушкой, чтобы ваша Reality нода использовала **собственный домен** с валидным TLS-сертификатом вместо маскировки под чужой сайт.

## Как это работает

```
Клиент (SNI: your-domain.com)
        │
        ▼
  Xray Reality (:443)
        │
        ├── VPN клиент? ──► VPN туннель
        │
        └── Зонд/сканер? ──► проксирует на 127.0.0.1:8443
                                        │
                                        ▼
                               Caddy (валидный TLS-сертификат
                               для your-domain.com)
                                        │
                                        ▼
                                  Страница-заглушка
```

DPI или активное зондирование видит легитимный TLS-сертификат, совпадающий с SNI — ничего подозрительного.

## Варианты заглушек

Установщик включает **3 встроенные страницы** на выбор:

| # | Название | Описание |
|---|----------|----------|
| 1 | **Minimal 404** | Тёмная, минималистичная страница 404 с градиентной анимацией |
| 2 | **Cat Memes 404** | Весёлая 404 с летающими котиками и игривым дизайном |
| 3 | **Business Site** | Профессиональный лендинг IT-компании (NovaTech) |

После установки можно заменить заглушку на любой свой HTML.

## Требования

- Сервер на Debian / Ubuntu
- Root-доступ
- Домен с DNS A-записью, указывающей на IP сервера
- Нода Xray Reality (Remnawave или standalone)

## Установка

**Одной командой:**

```bash
bash <(curl -Ls https://raw.githubusercontent.com/SkunkBG/SelfstealCaddy/main/selfsteal-setup.sh)
```

**Или вручную:**

```bash
curl -Lo selfsteal-setup.sh https://raw.githubusercontent.com/SkunkBG/SelfstealCaddy/main/selfsteal-setup.sh
bash selfsteal-setup.sh
```

Скрипт запросит домен и предложит выбрать заглушку.

## Что делает скрипт

1. Запрашивает домен и выбор заглушки
2. Проверяет DNS-резолв
3. Устанавливает Caddy (если ещё не установлен)
4. Создаёт выбранную страницу в `/var/www/html/index.html`
5. Настраивает Caddy:
   - Порт `80` — получение сертификата Let's Encrypt + редирект HTTP → HTTPS
   - Порт `8443` — HTTPS с валидным сертификатом, отдаёт заглушку
6. Настраивает UFW (открывает `80`, `443`, закрывает `8443`)
7. Запускает Caddy и проверяет сертификат

## После установки

Обновите конфиг Xray / Remnawave ноды — измените два поля в `realitySettings`:

```json
"realitySettings": {
    "target": "127.0.0.1:8443",
    "serverNames": ["your-domain.com"]
}
```

| Было | Стало |
|------|-------|
| `"target": "www.google.com:443"` | `"target": "127.0.0.1:8443"` |
| `"serverNames": ["google.com"]` | `"serverNames": ["your-domain.com"]` |

Всё остальное в конфиге (`shortIds`, `privateKey`, routing, outbounds) остаётся без изменений.

## Порты

| Порт | Сервис | Доступ |
|------|--------|--------|
| `443` | Xray Reality | Публичный — VPN-подключения |
| `80` | Caddy | Публичный — обновление сертификата + редирект |
| `8443` | Caddy HTTPS | **Только локальный** (`127.0.0.1`) |

## Расположение файлов

| Файл | Путь |
|------|------|
| Страница-заглушка | `/var/www/html/index.html` |
| Конфиг Caddy | `/etc/caddy/Caddyfile` |
| Бэкап конфига | `/etc/caddy/Caddyfile.bak.*` |

## Кастомизация

Замените заглушку на любой свой HTML:

```bash
nano /var/www/html/index.html
systemctl restart caddy
```

Или перезапустите скрипт для выбора другой заглушки:

```bash
bash selfsteal-setup.sh
```

## Удаление

```bash
systemctl stop caddy
systemctl disable caddy
apt remove caddy -y
rm -rf /var/www/html
rm -f /etc/apt/sources.list.d/caddy-stable.list
rm -f /usr/share/keyrings/caddy-stable-archive-keyring.gpg
```

## Решение проблем

**Caddy не запускается:**
```bash
journalctl -u caddy --no-pager -n 30
```

**Сертификат не выдаётся:**
- Убедитесь что порт `80` открыт и DNS A-запись указывает на сервер
- Проверьте: `curl -I http://your-domain.com`

**Проверка HTTPS вручную:**
```bash
curl -I https://your-domain.com:8443
```

## Лицензия

MIT
