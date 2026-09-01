# SelfstealCaddy

Генератор правдоподобных технических веб-сервисов для self-steal Reality.

Одной командой на чистом Linux VPS поднимается уникальный статический сервис на
Caddy — API-портал, CDN-панель, storage-платформа или обычный сайт — который в
браузере выглядит как настоящий продукт, а под `curl` ведёт себя как настоящий
HTTP-сервис. Xray Reality использует его как `dest`, поэтому активное
зондирование ноды упирается в связный работающий сайт, а не в заглушку.

```bash
git clone https://github.com/SkunkBG/SelfstealCaddy.git
cd SelfstealCaddy
DOMAIN=example.com STUB_THEME=random bash selfsteal-setup.sh
```

Или одним файлом из релиза:

```bash
bash <(curl -sL https://github.com/SkunkBG/SelfstealCaddy/releases/latest/download/selfsteal-setup.sh)
```

---

## Как это работает

```
Интернет ──443/TCP──▶ Xray (VLESS+Reality)
                          │
                          ├─ валидный клиент ──▶ проксирование трафика
                          └─ зонд / сканер   ──▶ 127.0.0.1:8443 ──▶ Caddy ──▶ сайт

Интернет ──80/TCP───▶ Caddy ──▶ ACME HTTP-01 + редирект на https://domain
```

Caddy слушает только `127.0.0.1:8443`. Наружу открыты 80 и 443. Сертификат
выпускается по HTTP-01 на порту 80, поэтому домен должен резолвиться на IP
сервера (или на CDN, который проксирует 80).

Конфигурация ноды Xray после установки:

```json
"target":      "127.0.0.1:8443",
"serverNames": ["example.com"]
```

---

## Архитектура

Проект разделён на генератор (Python 3, только стандартная библиотека) и
установщик (bash). На ноде нет рантайма: генератор один раз пишет статические
файлы, после чего работает только Caddy.

```
selfsteal-setup.sh        установщик: система, зависимости, Caddy, firewall
selfsteal/
  rng.py                  детерминированный ГПСЧ на sha256-потоке
  profile.py              ServiceProfile — всё разрешается из одного seed
  registry.py             реестр тем: theme → variant → builder
  branding.py             генерация брендов
  data.py                 словари: регионы, палитры, шрифтовые стеки
  render.py               NameMangler, DocumentStyle, сборка HTML
  css.py                  генератор стилей
  favicon.py              SVG и настоящий ICO, рисуется попиксельно
  payloads.py             фабрики JSON
  assets.py               sitemap.xml, robots.txt, security.txt
  caddyfile.py            сборка Caddyfile + валидация ввода
  generator.py            оркестратор, манифест, очистка устаревших файлов
  validate.py             офлайн-проверки дерева + живые HTTP-пробы
  themes/
    base.py               Endpoint, Page, Site, ThemeSpec
    catalog.py            11 технических архетипов как данные
    technical.py          движок технических тем + 6 вариантов вёрстки
    classic.py            4 обычных сайта
scripts/
  live-check.sh           поднимает Caddy и проверяет HTTP-контракт
  sweep.sh                то же по всем темам
  bundle.sh               сборка однофайлового релиза
tests/test_generator.py   офлайн-тесты
```

Границы разделения: установщик — системная часть, генератор — контент,
`caddyfile.py` — конфигурация, `validate.py` — проверка. Ни одна часть не знает
деталей другой.

---

## Темы

| Тема | Тип | Описание | Страницы | API |
|---|---|---|---|---|
| `media-api` | техническая | Приём, обработка и доставка медиа | `/` `/docs` `/docs/api` `/status` `+/docs/api/*` | `media` `assets` `formats` `renditions` |
| `data-api` | техническая | Коллекции, схемы, записи | те же | `collections` `records` `schema` `limits` |
| `developer-api` | техническая | Приложения, scopes, потребление | те же | `applications` `scopes` `usage` `limits` |
| `cdn` | техническая | Edge-кэш и доставка ассетов | те же | `regions` `cache` `assets` `limits` |
| `storage` | техническая | Объектное хранилище | те же | `buckets` `objects` `regions` `usage` |
| `image-api` | техническая | Трансформация изображений | те же | `images` `transforms` `formats` `presets` |
| `file-api` | техническая | Загрузка и выдача файлов | те же | `files` `types` `quota` `limits` |
| `analytics` | техническая | Приём событий и отчёты | те же | `events` `metrics` `dimensions` `usage` |
| `platform` | техническая | Деплой сервисов и окружения | те же | `services` `environments` `regions` `limits` |
| `status` | техническая | Статус компонентов и инциденты | те же | `components` `incidents` `uptime` `regions` |
| `edge-network` | техническая | Anycast-узлы и маршрутизация | те же | `nodes` `regions` `routes` `limits` |
| `studio` | обычная | Дизайн-студия | `/` `/studio.html` `/work.html` `/contact.html` | нет |
| `coffee` | обычная | Кофейня | `/` `/menu.html` `/about.html` `/visit.html` | нет |
| `law` | обычная | Юридическая фирма | `/` `/practice.html` `/people.html` `/contact.html` | нет |
| `contractor` | обычная | Строительный подрядчик | `/` `/services.html` `/projects.html` `/contact.html` | нет |

Мета-значения `STUB_THEME`: `random` (смесь 65/35 технических и обычных),
`technical`, `classic`.

Обычные темы намеренно **не** имеют API и health-эндпоинтов. Кофейня,
отвечающая на `/healthz`, — более сильный сигнал, чем отсутствие заглушки.

### Варианты вёрстки

Каждая техническая тема имеет 6 структурно разных вариантов: `portal`,
`minimal`, `console`, `docsfirst`, `platform`, `reference`. Они отличаются не
цветом, а DOM: составом секций, навигацией, наличием сайдбара, подачей
эндпоинтов (карточки / таблица / список), набором вторичных страниц.

---

## Детерминированная генерация

Всё выводится из одного seed:

```
seed = sha256(STUB_SEED или DOMAIN)  →  тема → вариант → бренд → палитра →
       шрифты → имена CSS-классов → порядок тегов в <head> → эндпоинты →
       JSON → favicon
```

Каждая подсистема берёт данные из именованного подпотока (`derive("brand")`,
`derive("favicon")`), поэтому добавление нового обращения в одном месте не
сдвигает всё остальное.

Следствия:

* повторная установка на том же домене воспроизводит **тот же сайт побайтово**;
* `STUB_SEED=<строка>` меняет личность ноды целиком и предсказуемо;
* время установки в контент не попадает. Единственное исключение — `Expires`
  в `security.txt`, где будущая дата обязательна по RFC 9116; она привязана к
  границе месяца плюс сдвиг из seed, поэтому дату установки не выдаёт.

Вместо `random.Random` используется собственный ГПСЧ на sha256-счётчике:
поведение Mersenne Twister не гарантировано между версиями Python, а
воспроизводимость здесь — требование, а не удобство.

---

## Уникальность между нодами

Главная угроза для флота — не то, что одна нода выглядит подозрительно, а то,
что тридцать нод выглядят **одинаково**. Один хэш `/favicon.ico` или общий
`<head>` кластеризует весь парк за один проход сканера.

Замер на 60 независимых установках в режиме `random`:

| Артефакт | Уникальных |
|---|---|
| `index.html` | 60 / 60 |
| `style.css` | 60 / 60 |
| `favicon.ico` | 60 / 60 |
| `404.html` | 60 / 60 |
| `robots.txt` | 60 / 60 |
| DOM-скелет (только последовательность тегов) | 60 / 60 |
| `<head>` | 60 / 60 |
| Бренд | 59 / 60 |

Уровни рандомизации: бренд → палитра и типографика → контент → набор страниц →
имена CSS-классов и порядок тегов → набор эндпоинтов → структуры JSON →
метаданные. Рандомизация никогда не нарушает внутреннюю согласованность: если
сервис называется `FrameLayer` и версия `v1`, это одинаково во всех заголовках,
документации, JSON, метаданных и favicon.

---

## API

Технические темы отдают настоящие JSON-ответы с честной HTTP-семантикой. Файлы
лежат в недоступном снаружи дереве `_api/`, роутинг делает Caddy — процессов и
рантайма нет.

```
GET     /                        200  text/html
GET     /docs                    200  text/html
GET     /docs/api                200  text/html
GET     /docs/api/v1/media       200  text/html
GET     /status                  200  text/html
GET     /status.json             200  application/json   no-store
GET     /api                     200  application/json   max-age=3600
GET     /api/v1                  200  application/json   max-age=300
GET     /api/v1/media            200  application/json   max-age=60
GET     /api/v1/formats          200  application/json   max-age=3600
GET     /api/v1/status           200  application/json   no-store
GET     /health  /healthz        200  application/json   no-store
GET     /ready   /readyz         200  application/json   no-store
GET     /api/v1/unknown          404  application/json
GET     /random-nonsense         404  text/html
GET     /api/v1/index.json       404  application/json
GET     /.env    /.git/HEAD      404
HEAD    /                        200  без тела
OPTIONS /api/v1                  204  Allow: GET, HEAD, OPTIONS
POST    /api/v1                  405  application/json + Allow
```

Ошибки под `/api/*` приходят в JSON, ошибки на HTML-путях — HTML-страницей.
Это content negotiation по префиксу пути, как у реального API-гейтвея.

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found."
  }
}
```

`Cache-Control` различается по классу ответа: статика — сутки, HTML — 5 минут,
справочники форматов — час, коллекции — минута, пробы и статус — `no-store`.

---

## Caddy

Каждая директива в сгенерированном конфиге имеет причину:

| Настройка | Причина |
|---|---|
| `admin unix//run/caddy/admin.sock` | TCP-листенера на `:2019` нет, но `caddy reload` работает. `admin off` заставлял делать `systemctl restart`, а рестарт создаёт окно, в котором `dest` для Reality отдаёт connection refused |
| `protocols h1 h2` | HTTP/3 выключен: Caddy слушает только TCP за Reality, реклама QUIC, которого нет на UDP/443, — это тель |
| `-Alt-Svc` | то же самое со стороны заголовков |
| `-Server` | убирает известный признак self-steal. Повторяется внутри `handle_errors`, иначе бэкенд представляется на каждом 404 |
| `@dotfiles → 404` | Caddy, в отличие от nginx, по умолчанию отдаёт скрытые файлы; случайный `.env` или `.git` в webroot был бы публичным |
| `@internal → 404` | деревья `_api/` и `_err/` недостижимы напрямую, поэтому `/api/v1/index.json` честно отдаёт 404 |
| `handle_errors` дублирует заголовки | они не наследуются из основного route |
| `try_files {path} {path}/index.html {path}.html` | одновременно поддерживает бесхвостовые URL технических тем и `.html` обычных |
| `redir` на `https://domain` без порта | `:8443` не должен утекать в `Location` |

Перед применением конфиг генерируется во временный файл, проходит
`caddy validate`, и только после этого заменяет рабочий. При провале старта
выполняется откат на последний бэкап и повторный запуск. Рабочий веб-сервер не
может быть сломан ошибкой генерации.

---

## Безопасность

* `$DOMAIN` и пути валидируются строгими регулярными выражениями до попадания в
  Caddyfile и HTML — инъекция конфигурации невозможна;
* скрытые файлы закрыты, `.well-known` открыт явным исключением;
* внутренние деревья `_api/` и `_err/` недоступны;
* никаких настоящих ключей, паролей и токенов; валидатор падает на
  credential-подобных строках в отдаваемом контенте;
* никаких внешних ресурсов: ни шрифтов, ни CDN, ни аналитики, ни счётчиков —
  проверяется автоматически;
* в контенте нет `localhost`, приватных IP и маркеров инфраструктуры
  (`selfsteal`, `xray`, `reality`, `remnawave`) — тоже проверяется;
* нет `Generated by ...` и любых других признаков генерации;
* файлы 644, каталоги 755, манифест и профиль — 600;
* `admin` не слушает TCP;
* бэкапы Caddyfile ограничены пятью последними.

---

## DRY_RUN

```bash
DRY_RUN=1 \
DOMAIN=example.com \
STUB_THEME=random \
WEBROOT=/tmp/site \
CADDYFILE=/tmp/Caddyfile \
bash selfsteal-setup.sh
```

Ничего в системе не меняется: ни apt, ни firewall, ни systemd, ни Caddy.
Выводится полный профиль:

```
Theme:       cdn (technical)
Variant:     reference
Service:     EdgeLoop CDN Platform
Company:     EdgeLoop Technologies BV
Brand:       EdgeLoop
API version: v1
Region:      Frankfurt (fra1, eu-central)
Palette:     #2f6feb on #ffffff
Seed:        3ade05207b689f92...
Pages:       10  / /about /docs /docs/api ...
Endpoints:   11  /api /api/v1 /api/v1/regions ...
Webroot:     /tmp/site
Caddyfile:   /tmp/Caddyfile
Files:       31 written, 0 removed
```

---

## Валидация и тесты

Офлайн-проверка сгенерированного дерева:

```bash
python3 -m selfsteal validate --webroot /var/www/html --domain example.com
```

Плюс живые HTTP-пробы против работающего Caddy:

```bash
python3 -m selfsteal validate --webroot /var/www/html --domain example.com \
    --base-url https://127.0.0.1:8443
```

Проверяется: коды ответов, `Content-Type`, валидность JSON и HTML, семантика
методов, отсутствие `Server` и `Alt-Svc`, недоступность dotfiles и внутренних
деревьев, соответствие sitemap реально существующим страницам, отсутствие
внешних ресурсов, приватных IP, секретов и маркеров, наличие favicon.

Полный локальный прогон:

```bash
bash scripts/sweep.sh              # нужен caddy в PATH или CADDY=./caddy
python3 -m unittest discover -s tests -v
shellcheck -S warning selfsteal-setup.sh scripts/*.sh
```

CI (`.github/workflows/ci.yml`) выполняет: ShellCheck, unit-тесты на Python
3.9–3.13, проверку отсутствия сторонних импортов, гейт детерминизма (два
прогона обязаны совпасть побайтово), живой HTTP-контракт по всем 15 темам и
сборку однофайлового релиза с самопроверкой.

---

## Повторная установка и обновление

Скрипт идемпотентен. Повторный запуск на том же домене:

* воспроизводит тот же сайт побайтово;
* удаляет файлы предыдущей темы по манифесту `.selfsteal-manifest.json` —
  только те, что записывал сам, никаких глобов;
* не трогает сертификаты;
* применяет конфиг через `reload`, без простоя;
* при невалидном конфиге не заменяет рабочий.

Смена личности ноды:

```bash
STUB_SEED=rotate-2026-09 DOMAIN=example.com bash selfsteal-setup.sh
```

Удаление:

```bash
UNINSTALL=1 WEBROOT=/var/www/html bash selfsteal-setup.sh
```

Удаляются только файлы из манифеста, Caddyfile восстанавливается из последнего
бэкапа, systemd drop-in снимается. Сам Caddy не трогается.

---

## Переменные окружения

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DOMAIN` | — | домен ноды (обязателен) |
| `STUB_THEME` | интерактивно / `random` | тема или мета-значение |
| `WEBROOT` | `/var/www/html` | корень сайта |
| `CADDYFILE` | `/etc/caddy/Caddyfile` | путь к конфигу |
| `DRY_RUN` | `0` | только генерация, без изменений системы |
| `STUB_SEED` | производный от `DOMAIN` | зафиксировать или сменить личность |
| `HTTPS_PORT` | `8443` | локальный порт бэкенда |
| `ADMIN_SOCKET` | `/run/caddy/admin.sock` | сокет admin API |
| `DEBUG` | `0` | трассировка и полный вывод ошибок |
| `ASSUME_YES` | `0` | не задавать вопросов |
| `UNINSTALL` | `0` | режим удаления |

---

## Как добавить новую тему

Техническая тема — это одна запись данных. Ни установщик, ни Caddyfile, ни
валидатор менять не нужно.

1. Добавьте `TechTheme` в `selfsteal/themes/catalog.py`: ключ, метку, описание,
   список `TechResource` и компоненты для страницы статуса.
2. Для каждого ресурса укажите фабрику payload из `selfsteal/payloads.py` —
   `collection`, `enumeration`, `regions`, `usage`, `limits`, `schema_doc` — или
   добавьте свою.
3. Ничего больше. Реестр подхватит тему; эндпоинты, документация, sitemap,
   маршруты Caddy и валидация построятся автоматически.
4. Прогоните `python3 -m unittest discover -s tests` и
   `bash scripts/live-check.sh <ключ>`.

Правило согласованности: ресурсы, компоненты и словарь темы должны принадлежать
одной предметной области. `Media API` с эндпоинтом `/api/v1/buckets` хуже, чем
отсутствие заглушки, — несогласованность замечают в первую очередь.

Обычная тема добавляется функцией-билдером в `selfsteal/themes/classic.py` и
записью в `CLASSIC_LABELS` реестра.

---

## Диагностика

| Симптом | Причина и что делать |
|---|---|
| `Caddyfile невалиден` | конфиг не применён, рабочий не тронут. Запустите с `DEBUG=1` |
| Caddy не стартует | выполнен откат на бэкап. `journalctl -u caddy -n 40 --no-pager` |
| Сертификат не выпускается | порт 80 закрыт или домен не резолвится на этот сервер |
| `reload не удался` | нет `/run/caddy` — проверьте drop-in `10-selfsteal-runtime.conf` |
| `python3 не найден` | `apt install python3`; на облачных образах он есть из-за cloud-init |
| Сайт отдаёт старые страницы | проверьте `.selfsteal-manifest.json` в webroot |
| `Server` появился в ответе | конфиг заменён вручную; заголовки должны быть и в `handle_errors` |

---

## Совместимость

Интерфейс 1.x сохранён полностью: те же имена тем, те же переменные окружения,
те же URL страниц обычных тем. Обновление с 1.x — просто запуск нового скрипта.

Целевые системы: Debian 12, Debian 13, Ubuntu LTS. Зависимости: `python3`
(только стандартная библиотека), `caddy`, `curl`, `dnsutils`. Ни баз данных, ни
Node.js, ни Docker, ни фоновых процессов кроме самого Caddy.

## Лицензия

MIT.
