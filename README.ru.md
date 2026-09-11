<p align="center">
  <img src="https://raw.githubusercontent.com/hteppl/remnawave-cloudflare-nodes/master/.github/images/logo.webp" alt="remnawave-cloudflare-nodes" width="800px">
</p>

## remnawave-cloudflare-nodes

<p align="left">
  <a href="https://github.com/hteppl/remnawave-cloudflare-nodes/releases/"><img src="https://img.shields.io/github/v/release/hteppl/remnawave-cloudflare-nodes.svg" alt="Release"></a>
  <a href="https://hub.docker.com/r/hteppl/remnawave-cloudflare-nodes/"><img src="https://img.shields.io/badge/DockerHub-remnawave--cloudflare--nodes-blue" alt="DockerHub"></a>
  <a href="https://github.com/hteppl/remnawave-cloudflare-nodes/actions"><img src="https://img.shields.io/github/actions/workflow/status/hteppl/remnawave-cloudflare-nodes/dockerhub-publish.yaml" alt="Build"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12"></a>
  <a href="https://opensource.org/licenses/GPL-3.0"><img src="https://img.shields.io/badge/license-GPLv3-green.svg" alt="License: GPL v3"></a>
</p>

[English](README.md) | Русский

> Настройки логирования, API и Telegram перенесены из `config.yml` в `.env`.
> См. [Гайд по миграции](docs/MIGRATION.md).

Сервис для автоматического управления DNS-записями Cloudflare в зависимости от состояния нод
Remnawave (https://docs.rw).

## Возможности

- **Мониторинг нод** - Отслеживание состояния нод через Remnawave API
- **Управление DNS** - Автоматическое добавление и удаление A-записей
- **Автоопределение зон** - Получение Zone ID по имени домена
- **Мультидоменность** - Поддержка нескольких доменов и зон
- **Telegram-уведомления** - Оповещения об изменении статуса нод, DNS и критических событиях
- **HTTP API** - Управление конфигурацией в реальном времени через защищенный REST API
- **Tailscale / Альтернативные адреса** - Маппинг публичных DNS IP на внутренние адреса нод (Tailscale, VPN, NAT)
- **Гибкая настройка** - Настраиваемые интервалы проверок
- **Docker** - Готовый образ для быстрого развертывания

## Требования

- **Remnawave Panel** с добавленными нодами
- **Remnawave API Token** - генерируется в настройках панели
- **Cloudflare** с настроенными DNS-зонами
- **Cloudflare API Token** - с правами на редактирование DNS

## Настройка

Скопируйте [`.env.example`](.env.example) в `.env`:

```env
# Remnawave
REMNAWAVE_API_URL=https://panel.example.com
REMNAWAVE_API_KEY=remnawave_api_key

# Cloudflare (токен с правами DNS Edit)
CLOUDFLARE_API_TOKEN=cloudflare_api_token

# API
API_ENABLED=false
API_TOKEN=  # Сгенерировать: openssl rand -hex 32
API_HOST=0.0.0.0
API_PORT=8741

# Telegram-уведомления
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=123456789
TELEGRAM_TOPIC_ID=  # ID топика (для форумов, иначе оставить пустым)

# Фильтры уведомлений
TELEGRAM_NOTIFY_NODE_CHANGES=true
TELEGRAM_NOTIFY_DNS_CHANGES=true
TELEGRAM_NOTIFY_ERRORS=true
TELEGRAM_NOTIFY_CRITICAL=true
TELEGRAM_NOTIFY_API_CHANGES=true

# Язык уведомлений (en, ru)
LANGUAGE=ru
# Часовой пояс и формат времени
TIMEZONE=UTC
TIME_FORMAT="%d.%m.%Y %H:%M:%S"
# Уровень логов (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO
```

Скопируйте [`config.example.yml`](config.example.yml) в `config.yml`:

```yaml
remnawave:
  check-interval: 30

domains:
  - domain: example1.com
    zones:
      - name: s1          # Создаёт s1.example1.com
        ttl: 60
        proxied: false
        ips:
          - 1.2.3.4
          - 5.6.7.8
      - name: "@"         # Создаёт корневую запись для example1.com
        ttl: 60
        proxied: false
        ips:
          - 1.2.3.4

  - domain: example2.com
    zones:
      - name: s2
        ttl: 60
        proxied: false
        ips:
          - 13.14.15.16
          - 17.18.19.20
```

### Корневые (apex) записи домена

Используйте `name: "@"`, чтобы создать A-запись для самого корневого домена (`example.com`), а не для поддомена:

```yaml
domains:
  - domain: example.com
    zones:
      - name: "@"       # A-запись для example.com
        ttl: 60
        proxied: false
        ips:
          - 1.2.3.4
      - name: sub       # A-запись для sub.example.com
        ttl: 60
        proxied: false
        ips:
          - 5.6.7.8
```

> **Важно:** При работе с apex-зонами через HTTP API необходимо URL-кодировать `@` как `%40` в пути запроса:
> ```
> PATCH /api/config/domains/example.com/zones/%40
> DELETE /api/config/domains/example.com/zones/%40
> ```

### Форматы нод

Зоны поддерживают два формата указания нод для мониторинга.

**`ips` — простой список IP**

```yaml
zones:
  - name: s1
    ttl: 60
    ips:
      - 1.2.3.4
      - 5.6.7.8
```

Каждый IP записывается в Cloudflare DNS и используется для поиска ноды в Remnawave.

**`nodes` — расширенный формат с отдельными адресами**

```yaml
zones:
  - name: s1
    ttl: 60
    nodes:
      - ip: 1.2.3.4
        address: 100.64.0.1  # Tailscale или внутренний адрес ноды в Remnawave
      - ip: 5.6.7.8
        address: 100.64.0.2
```

- `ip` — IP, записываемый в Cloudflare DNS.
- `address` — адрес ноды в Remnawave (`node.address`). Используется, если нода доступна через Tailscale, VPN или иной
  адрес, отличный от публичного IP. Если не указан, по умолчанию равен `ip`.

Оба формата можно смешивать внутри одной зоны и между разными зонами.

### Параметры

#### Переменные окружения (.env)

| Переменная                     | Описание                                         | По умолчанию        | Обязательно        |
|--------------------------------|--------------------------------------------------|---------------------|--------------------|
| `REMNAWAVE_API_URL`            | Адрес панели Remnawave                           | -                   | Да                 |
| `REMNAWAVE_API_KEY`            | API токен Remnawave                              | -                   | Да                 |
| `CLOUDFLARE_API_TOKEN`         | API токен Cloudflare (DNS Edit)                  | -                   | Да                 |
| `LOG_LEVEL`                    | Уровень логов (`DEBUG` `INFO` `WARNING` `ERROR`) | `INFO`              | Нет                |
| `API_ENABLED`                  | Включить HTTP API                                | `false`             | Нет                |
| `API_HOST`                     | Адрес привязки API-сервера                       | `0.0.0.0`           | Нет                |
| `API_PORT`                     | Порт API-сервера                                 | `8741`              | Нет                |
| `API_TOKEN`                    | Токен API — строго 64 символа hex                | -                   | При включенном API |
| `TELEGRAM_ENABLED`             | Включить Telegram-уведомления                    | `false`             | Нет                |
| `TELEGRAM_BOT_TOKEN`           | Токен бота (@BotFather)                          | -                   | Нет                |
| `TELEGRAM_CHAT_ID`             | ID чата для уведомлений                          | -                   | Нет                |
| `TELEGRAM_TOPIC_ID`            | ID топика (для форумов)                          | -                   | Нет                |
| `TELEGRAM_NOTIFY_NODE_CHANGES` | Уведомления об изменении статуса нод             | `true`              | Нет                |
| `TELEGRAM_NOTIFY_DNS_CHANGES`  | Уведомления об изменениях DNS                    | `true`              | Нет                |
| `TELEGRAM_NOTIFY_ERRORS`       | Уведомления об ошибках                           | `true`              | Нет                |
| `TELEGRAM_NOTIFY_CRITICAL`     | Уведомление при падении всех нод                 | `true`              | Нет                |
| `TELEGRAM_NOTIFY_API_CHANGES`  | Уведомления об изменениях через HTTP API         | `true`              | Нет                |
| `LANGUAGE`                     | Язык уведомлений (`en`, `ru`)                    | `en`                | Нет                |
| `TIMEZONE`                     | Часовой пояс                                     | `UTC`               | Нет                |
| `TIME_FORMAT`                  | Формат времени                                   | `%d.%m.%Y %H:%M:%S` | Нет                |

#### config.yml

| Ключ                       | Описание                 | По умолчанию | Обязательно |
|----------------------------|--------------------------|--------------|-------------|
| `remnawave.check-interval` | Интервал проверки (сек)  | `30`         | Нет         |
| `domains`                  | Список доменов и DNS-зон | `[]`         | Да          |

## Установка

### Docker (рекомендуется)

1. Создайте `docker-compose.yml`:

```yaml
services:
  remnawave-cloudflare-nodes:
    image: hteppl/remnawave-cloudflare-nodes:latest
    container_name: remnawave-cloudflare-nodes
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./config.yml:/app/config.yml
      - ./logs:/app/logs
    networks:
      - remnawave-cloudflare-nodes

networks:
  remnawave-cloudflare-nodes:
    name: remnawave-cloudflare-nodes
    driver: bridge
```

2. Настройте `.env`:

```bash
cp .env.example .env
nano .env
```

3. Запустите:

```bash
docker compose up -d && docker compose logs -f
```

### Ручная установка

```bash
git clone https://github.com/hteppl/remnawave-cloudflare-nodes.git
cd remnawave-cloudflare-nodes

python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt
cp .env.example .env
python -m src
```

## Принцип работы

1. **Запуск** - Сервис получает список нод из Remnawave и определяет Zone ID в Cloudflare

2. **Проверка состояния** - Нода считается рабочей, если:
    - `is_connected = true`
    - `is_disabled = false`
    - `xray_version` не пустой

3. **Синхронизация DNS** - Для каждой зоны сопоставляет `address` каждой записи со статусом ноды, затем:
    - Добавляет A-записи для IP, чьи ноды работают
    - Удаляет A-записи для IP, чьи ноды недоступны

4. **Цикл** - Проверка повторяется каждые `check-interval` секунд

## Telegram-уведомления

Сервис отправляет уведомления о событиях в Telegram.

### Подключение

1. Создайте бота через [@BotFather](https://t.me/BotFather)
2. Узнайте свой chat ID через [@username_to_id_bot](https://t.me/username_to_id_bot)
3. Добавьте бота в чат
4. Настройте в `.env`:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=123456789
TELEGRAM_TOPIC_ID=              # Опционально: для форумов
LANGUAGE=ru                     # en, ru
```

### Типы уведомлений

| Событие            | Описание            | Пример                                                                          |
|--------------------|---------------------|---------------------------------------------------------------------------------|
| **Нода онлайн**    | Нода доступна       | ✅ Нода онлайн<br>node-1 (1.2.3.4) доступна.<br>📊 Ноды: 5/6 онлайн, 0 отключено |
| **Нода офлайн**    | Нода недоступна     | ❌ Нода офлайн<br>node-1 (1.2.3.4) недоступна.<br>Причина: disconnected          |
| **DNS добавлен**   | Добавлена A-запись  | 📝 DNS обновлен<br>Добавлен 1.2.3.4 → s1.example.com                            |
| **DNS удален**     | Удалена A-запись    | 🗑️ DNS удален<br>Удален 1.2.3.4 из s1.example.com                              |
| **Критическая**    | Все ноды недоступны | 🔴 КРИТИЧНО: Все ноды недоступны                                                |
| **Восстановление** | Ноды снова онлайн   | 🟢 Восстановление: Ноды снова онлайн                                            |
| **Запуск**         | Сервис запущен      | 🚀 Сервис запущен                                                               |
| **Остановка**      | Сервис остановлен   | 🛑 Сервис остановлен                                                            |

### Фильтрация уведомлений

```env
TELEGRAM_NOTIFY_NODE_CHANGES=true   # Статус нод
TELEGRAM_NOTIFY_DNS_CHANGES=true    # Изменения DNS
TELEGRAM_NOTIFY_ERRORS=true         # Ошибки
TELEGRAM_NOTIFY_CRITICAL=true       # Падение всех нод
TELEGRAM_NOTIFY_API_CHANGES=true    # Изменения через HTTP API
```

## HTTP API

Сервис включает опциональный REST API для управления конфигурацией в реальном времени.

Эндпоинты и примеры кода: [`docs/AI_INTEGRATION_GUIDE.md`](docs/AI_INTEGRATION_GUIDE.md), OpenAPI-схема:
[`docs/openapi/openapi.json`](docs/openapi/openapi.json).

### Быстрый старт

1. Сгенерируйте токен:

```bash
openssl rand -hex 32
```

2. Включите в `.env`:

```env
API_ENABLED=true
API_TOKEN=<сгенерированный токен>
API_HOST=0.0.0.0
API_PORT=8741
```

### Reverse proxy

Примеры конфигурации для проброса API через reverse proxy:

- **Caddy** — [`docs/Caddyfile.example`](docs/Caddyfile.example)
- **Nginx** — [`docs/nginx.example.conf`](docs/nginx.example.conf)

Подключите reverse proxy к сети проекта, чтобы он мог обращаться к контейнеру по имени:

```yaml
networks:
  remnawave-cloudflare-nodes:
    external: true
```

### CLI

Внутри контейнера доступен интерактивный CLI для диагностики и управления конфигурацией:

```bash
docker exec -it remnawave-cloudflare-nodes cli
```

Навигация стрелками, выбор через Enter:

```
  remnawave-cloudflare-nodes

? Select action:
 ❯ Show config
   Validate config
   Reload config (hot)
   ──────────────────
   Exit
```

| Пункт               | Описание                                                       |
|---------------------|----------------------------------------------------------------|
| **Show config**     | Показать домены, зоны, ноды и настройки сервиса                |
| **Validate config** | Проверить `config.yml`, вывести ошибки или сводку              |
| **Reload config**   | Применить изменения из `config.yml` без перезапуска контейнера |

### Логи

```bash
# Docker
docker compose logs -f

# Ручная установка
# stdout + logs/app.log
```

## Миграция

Обновляетесь со старой версии? См. [Гайд по миграции](docs/MIGRATION.md).

## Лицензия

[GNU General Public License v3.0](LICENSE)
