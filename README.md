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

English | [Русский](README.ru.md)

> Logging, API, and Telegram settings have moved from `config.yml` to `.env`.
> See the [Migration Guide](docs/MIGRATION.md).

Automatically manage Cloudflare DNS records based on Remnawave (https://docs.rw) node health status.

## Features

- **Automatic Health Monitoring** - Continuously monitors node health status via Remnawave API
- **Dynamic DNS Management** - Adds DNS records for healthy nodes, removes records for unhealthy ones
- **Auto Zone Discovery** - Automatically discovers Cloudflare zone IDs from domain names
- **Multi-Domain Support** - Manage multiple domains with multiple DNS zones each
- **Telegram Notifications** - Real-time alerts for node status changes, DNS updates, and critical events
- **HTTP API** - Manage configuration at runtime via a secured REST API
- **Tailscale / Alternate Addresses** - Map public DNS IPs to internal node addresses (Tailscale, VPN, NAT)
- **Configurable Intervals** - Set custom health check intervals
- **Docker Ready** - Easy deployment with Docker and Docker Compose

## Prerequisites

Before you begin, ensure you have the following:

- **Remnawave Panel** with nodes configured
- **Remnawave API Token** - Generate from your Remnawave panel settings
- **Cloudflare Account** with DNS zones configured
- **Cloudflare API Token** - Create with DNS edit permissions

## Configuration

Copy [`.env.example`](.env.example) to `.env` and fill in your values:

```env
# Remnawave panel URL and API key
REMNAWAVE_API_URL=https://panel.example.com
REMNAWAVE_API_KEY=remnawave_api_key

# Cloudflare token with DNS edit permissions
CLOUDFLARE_API_TOKEN=cloudflare_api_token

# API
API_ENABLED=false
API_TOKEN=  # Generate a strong random value: openssl rand -hex 32
API_HOST=0.0.0.0
API_PORT=8741

# Telegram notifications
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=123456789
TELEGRAM_TOPIC_ID=  # Forum topic ID (leave empty for regular chats)

# Notification filters
TELEGRAM_NOTIFY_NODE_CHANGES=true
TELEGRAM_NOTIFY_DNS_CHANGES=true
TELEGRAM_NOTIFY_ERRORS=true
TELEGRAM_NOTIFY_CRITICAL=true
TELEGRAM_NOTIFY_API_CHANGES=true

# Language for notifications (en, ru)
LANGUAGE=en
# Timezone (e.g. UTC, Europe/Moscow, America/New_York)
TIMEZONE=UTC
# Time format: %d-day, %m-month, %Y-year, %H-hour, %M-min, %S-sec
TIME_FORMAT="%d.%m.%Y %H:%M:%S"
# Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=INFO
```

Copy [`config.example.yml`](config.example.yml) to `config.yml` and configure your domains:

```yaml
remnawave:
  # Health check interval in seconds
  check-interval: 30

# Domains and DNS zones to manage
domains:
  - domain: example1.com
    zones:
      - name: s1          # Creates s1.example1.com
        ttl: 60           # Record TTL in seconds
        proxied: false    # Cloudflare proxy (orange cloud)
        ips: # Node IPs to monitor
          - 1.2.3.4
          - 5.6.7.8
      - name: "@"         # Creates apex record for example1.com itself
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

### Apex (root) domain records

Use `name: "@"` to create an A record for the root domain itself (`example.com`) instead of a subdomain:

```yaml
domains:
  - domain: example.com
    zones:
      - name: "@"       # A record for example.com
        ttl: 60
        proxied: false
        ips:
          - 1.2.3.4
      - name: sub       # A record for sub.example.com
        ttl: 60
        proxied: false
        ips:
          - 5.6.7.8
```

> **Note:** When managing apex zones via the HTTP API, URL-encode `@` as `%40` in the path:
> ```
> PATCH /api/config/domains/example.com/zones/%40
> DELETE /api/config/domains/example.com/zones/%40
> ```

### Node formats

Zones support two formats for specifying which nodes to monitor.

**`ips` — simple list of IPs**

```yaml
zones:
  - name: s1
    ttl: 60
    ips:
      - 1.2.3.4
      - 5.6.7.8
```

Each IP is both written to Cloudflare DNS and matched against `node.address` in Remnawave.

**`nodes` — advanced with separate addresses**

```yaml
zones:
  - name: s1
    ttl: 60
    nodes:
      - ip: 1.2.3.4
        address: 100.64.0.1  # Tailscale or internal address in Remnawave
      - ip: 5.6.7.8
        address: 100.64.0.2
```

- `ip` — the IP written to Cloudflare DNS.
- `address` — the `node.address` used to find the node in Remnawave. Useful when nodes are accessed via Tailscale, a
  VPN, or any address that differs from the public IP. When omitted, defaults to `ip`.

Both formats can be mixed within the same zone or across different zones.

### Configuration Reference

#### Environment variables (.env)

| Variable                       | Description                                    | Default             | Required         |
|--------------------------------|------------------------------------------------|---------------------|------------------|
| `REMNAWAVE_API_URL`            | Remnawave API endpoint                         | -                   | Yes              |
| `REMNAWAVE_API_KEY`            | Remnawave API token                            | -                   | Yes              |
| `CLOUDFLARE_API_TOKEN`         | Cloudflare API token with DNS edit permissions | -                   | Yes              |
| `LOG_LEVEL`                    | Log level (`DEBUG` `INFO` `WARNING` `ERROR`)   | `INFO`              | No               |
| `API_ENABLED`                  | Enable the HTTP API server                     | `false`             | No               |
| `API_HOST`                     | Address to bind the API server                 | `0.0.0.0`           | No               |
| `API_PORT`                     | Port for the API server                        | `8741`              | No               |
| `API_TOKEN`                    | API auth token — must be 64-char hex string    | -                   | When API enabled |
| `TELEGRAM_ENABLED`             | Enable Telegram notifications                  | `false`             | No               |
| `TELEGRAM_BOT_TOKEN`           | Telegram bot token from @BotFather             | -                   | No               |
| `TELEGRAM_CHAT_ID`             | Chat ID for notifications                      | -                   | No               |
| `TELEGRAM_TOPIC_ID`            | Forum topic ID (for supergroups with topics)   | -                   | No               |
| `TELEGRAM_NOTIFY_NODE_CHANGES` | Notify on node status changes                  | `true`              | No               |
| `TELEGRAM_NOTIFY_DNS_CHANGES`  | Notify on DNS record changes                   | `true`              | No               |
| `TELEGRAM_NOTIFY_ERRORS`       | Notify on errors                               | `true`              | No               |
| `TELEGRAM_NOTIFY_CRITICAL`     | Notify when all nodes go down                  | `true`              | No               |
| `TELEGRAM_NOTIFY_API_CHANGES`  | Notify on HTTP API config changes              | `true`              | No               |
| `LANGUAGE`                     | Notification language (`en`, `ru`)             | `en`                | No               |
| `TIMEZONE`                     | Timezone for timestamps (e.g. Europe/Moscow)   | `UTC`               | No               |
| `TIME_FORMAT`                  | Time format for timestamps                     | `%d.%m.%Y %H:%M:%S` | No               |

#### config.yml

| Key                        | Description                               | Default | Required |
|----------------------------|-------------------------------------------|---------|----------|
| `remnawave.check-interval` | Interval in seconds between health checks | `30`    | No       |
| `domains`                  | List of domains and DNS zones to manage   | `[]`    | Yes      |

## Installation

### Docker (recommended)

1. Create the docker-compose.yml:

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

2. Create and configure your environment file:

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

3. Start the container:

```bash
docker compose up -d && docker compose logs -f
```

### Manual Installation

1. Clone the repository:

```bash
git clone https://github.com/hteppl/remnawave-cloudflare-nodes.git
cd remnawave-cloudflare-nodes
```

2. Create a virtual environment (recommended):

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create and configure your environment file:

```bash
cp .env.example .env
```

5. Run the application:

```bash
python -m src
```

## How It Works

1. **Initial Fetch** - On startup, the service fetches all nodes from the Remnawave API and auto-discovers
   Cloudflare zone IDs

2. **Health Evaluation** - Based on node status, determines which nodes are healthy:
    - Node must be connected (`is_connected = true`)
    - Node must not be disabled (`is_disabled = false`)
    - Node must have Xray installed (`xray_version` is not null)

3. **DNS Synchronization** - For each configured zone, matches each entry's `address` to node health status, then:
    - Adds DNS A records for IPs whose nodes are healthy
    - Removes DNS A records for IPs whose nodes are no longer healthy

4. **Continuous Updates** - The service polls the Remnawave API at the configured interval (`check-interval`) and
   updates DNS records

The service manages DNS records dynamically, ensuring only healthy nodes are included in DNS resolution.

## Telegram Notifications

The service can send real-time notifications to Telegram when events occur.

### Setup

1. Create a bot with [@BotFather](https://t.me/BotFather) and get the token
2. Get your chat ID from [@username_to_id_bot](https://t.me/username_to_id_bot)
3. Add the bot to your chat/group
4. Configure in `.env`:

```env
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=123456789
TELEGRAM_TOPIC_ID=              # Optional: for forum topics
LANGUAGE=en                     # en, ru
```

### Notification Types

| Event             | Description           | Example                                                                                 |
|-------------------|-----------------------|-----------------------------------------------------------------------------------------|
| **Node Online**   | Node became healthy   | ✅ Node Online<br>node-1 (1.2.3.4) is now available.<br>📊 Nodes: 5/6 online, 0 disabled |
| **Node Offline**  | Node became unhealthy | ❌ Node Offline<br>node-1 (1.2.3.4) is unavailable.<br>Reason: disconnected              |
| **DNS Updated**   | DNS record added      | 📝 DNS Updated<br>Added 1.2.3.4 → s1.example.com                                        |
| **DNS Removed**   | DNS record removed    | 🗑️ DNS Removed<br>Removed 1.2.3.4 from s1.example.com                                  |
| **Critical**      | All nodes down        | 🔴 CRITICAL: All Nodes Down<br>All 5 nodes are unreachable.                             |
| **Recovered**     | All nodes back online | 🟢 Recovered: Nodes Back Online                                                         |
| **Service Start** | Monitoring started    | 🚀 Service Started                                                                      |
| **Service Stop**  | Monitoring stopped    | 🛑 Service Stopped                                                                      |

### Configure Notifications

You can enable/disable specific notification types in `.env`:

```env
TELEGRAM_NOTIFY_NODE_CHANGES=true   # Node online/offline events
TELEGRAM_NOTIFY_DNS_CHANGES=true    # DNS record add/remove
TELEGRAM_NOTIFY_ERRORS=true         # Error alerts
TELEGRAM_NOTIFY_CRITICAL=true       # All nodes down alert
TELEGRAM_NOTIFY_API_CHANGES=true    # HTTP API config changes
```

## HTTP API

The service includes an optional REST API for managing configuration at runtime.

See [`docs/AI_INTEGRATION_GUIDE.md`](docs/AI_INTEGRATION_GUIDE.md) for endpoints and code snippets, or the OpenAPI
schema in [`docs/openapi/openapi.json`](docs/openapi/openapi.json).

### Quick start

1. Generate a token:

```bash
openssl rand -hex 32
```

2. Enable in `.env`:

```env
API_ENABLED=true
API_TOKEN=<generated token>
API_HOST=0.0.0.0
API_PORT=8741
```

### Reverse proxy

Example configs for exposing the API behind a reverse proxy:

- **Caddy** — [`docs/Caddyfile.example`](docs/Caddyfile.example)
- **Nginx** — [`docs/nginx.example.conf`](docs/nginx.example.conf)

Connect your reverse proxy to the project network so it can reach the container by name:

```yaml
networks:
  remnawave-cloudflare-nodes:
    external: true
```

### CLI

An interactive CLI is available inside the container for quick diagnostics and config management:

```bash
docker exec -it remnawave-cloudflare-nodes cli
```

Use arrow keys to navigate and Enter to select:

```
  remnawave-cloudflare-nodes

? Select action:
 ❯ Show config
   Validate config
   Reload config (hot)
   ──────────────────
   Exit
```

| Option              | Description                                                      |
|---------------------|------------------------------------------------------------------|
| **Show config**     | Display current domains, zones, nodes and service settings       |
| **Validate config** | Parse and validate `config.yml`, report errors or a zone summary |
| **Reload config**   | Apply changes from `config.yml` without restarting the container |

### Logs

Monitor logs to diagnose issues:

```bash
# Docker
docker compose logs -f

# Manual
# Logs are output to stdout and logs/app.log
```

## Migration

Upgrading from an older version? See the [Migration Guide](docs/MIGRATION.md).

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).
