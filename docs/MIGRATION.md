# Migration Guide

## v1.x → v1.4

Logging, API, and Telegram settings have moved from `config.yml` to `.env`. The `config.yml` file now only contains
`remnawave` and `domains` sections.

### 1. Move settings to `.env`

Take the values from your current `config.yml` and add the corresponding environment variables to your `.env` file:

| `config.yml` (old)             | `.env` (new)                   | Default   |
|--------------------------------|--------------------------------|-----------|
| `logging.level`                | `LOG_LEVEL`                    | `INFO`    |
| `api.enabled`                  | `API_ENABLED`                  | `false`   |
| `api.host`                     | `API_HOST`                     | `0.0.0.0` |
| `api.port`                     | `API_PORT`                     | `8741`    |
| `telegram.enabled`             | `TELEGRAM_ENABLED`             | `false`   |
| `telegram.locale`              | `LANGUAGE`                     | `en`      |
| `telegram.notify.node_changes` | `TELEGRAM_NOTIFY_NODE_CHANGES` | `true`    |
| `telegram.notify.dns_changes`  | `TELEGRAM_NOTIFY_DNS_CHANGES`  | `true`    |
| `telegram.notify.errors`       | `TELEGRAM_NOTIFY_ERRORS`       | `true`    |
| `telegram.notify.critical`     | `TELEGRAM_NOTIFY_CRITICAL`     | `true`    |
| `telegram.notify.api_changes`  | `TELEGRAM_NOTIFY_API_CHANGES`  | `true`    |

**Example:** if your old `config.yml` had:

```yaml
logging:
  level: DEBUG

api:
  enabled: true
  host: "0.0.0.0"
  port: 8741

telegram:
  enabled: true
  locale: ru
  notify:
    node_changes: true
    dns_changes: true
    errors: true
    critical: true
    api_changes: false
```

Add these lines to your `.env`:

```env
LOG_LEVEL=DEBUG

API_ENABLED=true
API_HOST=0.0.0.0
API_PORT=8741

TELEGRAM_ENABLED=true
LANGUAGE=ru
TELEGRAM_NOTIFY_NODE_CHANGES=true
TELEGRAM_NOTIFY_DNS_CHANGES=true
TELEGRAM_NOTIFY_ERRORS=true
TELEGRAM_NOTIFY_CRITICAL=true
TELEGRAM_NOTIFY_API_CHANGES=false
```

### 2. Clean up `config.yml`

Remove the `logging`, `api`, and `telegram` blocks from your `config.yml`. Only `remnawave` and `domains` should
remain:

```yaml
remnawave:
  check-interval: 30

domains:
  - domain: example.com
    zones:
      - name: s1
        ttl: 60
        proxied: false
        ips:
          - 1.2.3.4
          - 5.6.7.8
```

The old blocks are simply ignored if left in the file, but removing them avoids confusion.

### 3. HTTP API changes

The `PATCH /api/config` endpoint no longer accepts `log_level` or `telegram` fields. Only `check_interval` can be
updated at runtime:

```json
{
  "check_interval": 60
}
```

`GET /api/config` still returns `log_level` and `telegram` status for visibility, but they are read-only.
