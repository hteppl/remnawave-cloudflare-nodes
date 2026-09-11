# AI Integration Guide — Remnawave Cloudflare Nodes HTTP API

A reference for using the HTTP API, written to be handed to an AI agent or read by a developer. The machine-readable
schema is [`openapi/openapi.json`](openapi/openapi.json) (regenerated on every release).

---

## Overview

The service watches node health in a Remnawave panel and keeps Cloudflare DNS **A records** in sync: each configured
zone (subdomain) gets one A record per **healthy** node and loses the records of unhealthy ones.

The HTTP API edits the service's `config.yml` at runtime — which domains and zones exist and which node IPs belong to
each zone.

## Connection

| Item         | Value                                                                                  |
|--------------|----------------------------------------------------------------------------------------|
| Base URL     | `http://<host>:<port>` — default port `8741`; often behind a reverse proxy with HTTPS  |
| Auth         | Header `X-API-Key: <token>` on **every** request                                       |
| Token        | 64-char lowercase hex, the `API_TOKEN` env var of the service (`openssl rand -hex 32`) |
| Content type | `application/json` for request and response bodies                                     |
| Enabled by   | `API_ENABLED=true` on the service                                                      |

No interactive docs are served (`/docs` and `/openapi.json` return 404). The API sends **no CORS headers**: call it
from a backend, CLI or server-side code, never from browser JavaScript (that would also expose the token).

The snippets below use these variables:

```bash
export RCN_API_URL=https://dns-monitor.example.com
export RCN_API_TOKEN=<64-char hex token>
```

```python
import os
import httpx

api = httpx.Client(
    base_url=os.environ["RCN_API_URL"],
    headers={"X-API-Key": os.environ["RCN_API_TOKEN"]},
    timeout=10,
)
```

```js
const API_URL = process.env.RCN_API_URL;
const headers = { "X-API-Key": process.env.RCN_API_TOKEN, "Content-Type": "application/json" };
```

## Data model

```
config
├── check_interval: int           seconds between monitoring cycles
└── domains: Domain[]
    Domain
    ├── domain: str               Cloudflare zone, e.g. "example.com" (must exist in the Cloudflare account)
    └── zones: Zone[]
        Zone
        ├── name: str             subdomain label, e.g. "s1" → s1.example.com; "@" = the apex (example.com)
        ├── ttl: int              DNS TTL, >= 1, default 120
        ├── proxied: bool         Cloudflare proxy (orange cloud), default false
        ├── ips: str[]            simple format: IP written to DNS AND used to find the node in Remnawave
        └── nodes: Node[]         advanced format
            Node
            ├── ip: str           IP written to DNS
            └── address: str?     node.address to find the node in Remnawave (e.g. a Tailscale IP); defaults to ip
```

- A zone has `ips`, `nodes`, or both — the service merges them. At least one must be non-empty on create.
- A node's DNS record exists only while the Remnawave node whose `address` matches is connected and enabled.
- IPs are not format-validated by the API; validate them before sending.

## Endpoints

| Method   | Path                                             | Body          | Success | Errors             |
|----------|--------------------------------------------------|---------------|---------|--------------------|
| `GET`    | `/api/config`                                    | —             | 200     | 401                |
| `PATCH`  | `/api/config`                                    | `ConfigPatch` | 200     | 401, 422           |
| `GET`    | `/api/config/domains`                            | —             | 200     | 401                |
| `POST`   | `/api/config/domains`                            | `DomainIn`    | 201     | 401, 409, 422      |
| `DELETE` | `/api/config/domains/{domain}`                   | —             | 200     | 401, 404           |
| `POST`   | `/api/config/domains/{domain}/zones`             | `ZoneIn`      | 201     | 401, 404, 409, 422 |
| `PATCH`  | `/api/config/domains/{domain}/zones/{zone_name}` | `ZonePatch`   | 200     | 401, 404, 422      |
| `DELETE` | `/api/config/domains/{domain}/zones/{zone_name}` | —             | 200     | 401, 404           |

Mutating endpoints return `{"status": "ok"}` on success.

**Path parameters must be URL-encoded.** This matters for the apex zone: `@` → `%40`, e.g.
`/api/config/domains/example.com/zones/%40`. Use Python `urllib.parse.quote(name, safe="")` or JS
`encodeURIComponent(name)`.

---

### Get config — `GET /api/config`

```bash
curl -s "$RCN_API_URL/api/config" -H "X-API-Key: $RCN_API_TOKEN"
```

```python
config = api.get("/api/config").raise_for_status().json()
```

```json
{
  "check_interval": 30,
  "log_level": "INFO",
  "domains": [
    {
      "domain": "example.com",
      "zones": [
        {
          "name": "s1",
          "ttl": 60,
          "proxied": false,
          "ips": [
            "1.2.3.4"
          ]
        }
      ]
    }
  ],
  "disable_unreachable_hosts": false,
  "telegram": {
    "enabled": true,
    "language": "en",
    "notify": {
      "dns_changes": true,
      "node_changes": true,
      "errors": true,
      "critical": true,
      "api_changes": true,
      "host_changes": true
    }
  }
}
```

Only `check_interval` is editable through the API; the rest comes from the service's environment variables.

### Set check interval — `PATCH /api/config`

`check_interval`: integer, `>= 5`. Takes effect after the current wait ends.

```bash
curl -s -X PATCH "$RCN_API_URL/api/config" -H "X-API-Key: $RCN_API_TOKEN" \
  -H "Content-Type: application/json" -d '{"check_interval": 60}'
```

```python
api.patch("/api/config", json={"check_interval": 60}).raise_for_status()
```

### List domains — `GET /api/config/domains`

```bash
curl -s "$RCN_API_URL/api/config/domains" -H "X-API-Key: $RCN_API_TOKEN"
```

```python
domains = api.get("/api/config/domains").raise_for_status().json()
for d in domains:
    for z in d.get("zones") or []:
        fqdn = d["domain"] if z["name"] == "@" else f'{z["name"]}.{d["domain"]}'
        print(fqdn, z.get("ttl", 120), z.get("proxied", False), z.get("ips", []), z.get("nodes", []))
```

```json
[
  {
    "domain": "example.com",
    "zones": [
      {
        "name": "s1",
        "ttl": 60,
        "proxied": false,
        "ips": [
          "1.2.3.4",
          "5.6.7.8"
        ]
      },
      {
        "name": "@",
        "nodes": [
          {
            "ip": "9.9.9.9",
            "address": "100.64.0.1"
          }
        ]
      }
    ]
  }
]
```

Zones are returned **as stored in `config.yml`**: `ttl` and `proxied` may be missing (treat as `120` / `false`), and a
zone may carry `ips`, `nodes`, or both.

### Add domain — `POST /api/config/domains`

`zones` needs at least one zone. Returns `201`; `409` if the domain already exists.

```bash
curl -s -X POST "$RCN_API_URL/api/config/domains" -H "X-API-Key: $RCN_API_TOKEN" \
  -H "Content-Type: application/json" -d '{
    "domain": "example.com",
    "zones": [
      { "name": "s1", "ttl": 60, "ips": ["1.2.3.4", "5.6.7.8"] },
      { "name": "@", "nodes": [ { "ip": "9.9.9.9", "address": "100.64.0.1" } ] }
    ]
  }'
```

```python
api.post("/api/config/domains", json={
    "domain": "example.com",
    "zones": [
        {"name": "s1", "ttl": 60, "ips": ["1.2.3.4", "5.6.7.8"]},
        {"name": "@", "nodes": [{"ip": "9.9.9.9", "address": "100.64.0.1"}]},
    ],
}).raise_for_status()
```

### Delete domain — `DELETE /api/config/domains/{domain}`

Removes the domain and **immediately deletes all its zones' A records from Cloudflare**. `404` if not found.

```bash
curl -s -X DELETE "$RCN_API_URL/api/config/domains/example.com" -H "X-API-Key: $RCN_API_TOKEN"
```

```python
from urllib.parse import quote

api.delete(f"/api/config/domains/{quote('example.com', safe='')}").raise_for_status()
```

### Add zone — `POST /api/config/domains/{domain}/zones`

| Field     | Type    | Notes                                    |
|-----------|---------|------------------------------------------|
| `name`    | string  | required; `"@"` for the apex             |
| `ttl`     | integer | `>= 1`, default `120`                    |
| `proxied` | boolean | default `false`                          |
| `ips`     | array   | IPs (simple format)                      |
| `nodes`   | array   | `{ "ip": str, "address": str? }` objects |

At least one of `ips` / `nodes` is required. Returns `201`; `404` if the domain doesn't exist, `409` if the zone does.

```bash
curl -s -X POST "$RCN_API_URL/api/config/domains/example.com/zones" -H "X-API-Key: $RCN_API_TOKEN" \
  -H "Content-Type: application/json" -d '{"name": "s2", "proxied": true, "ips": ["1.2.3.4"]}'
```

```python
api.post(
    f"/api/config/domains/{quote('example.com', safe='')}/zones",
    json={"name": "s2", "proxied": True, "ips": ["1.2.3.4"]},
).raise_for_status()
```

```js
await fetch(`${API_URL}/api/config/domains/${encodeURIComponent("example.com")}/zones`, {
  method: "POST",
  headers,
  body: JSON.stringify({ name: "s2", proxied: true, ips: ["1.2.3.4"] }),
});
```

### Update zone — `PATCH /api/config/domains/{domain}/zones/{zone_name}`

All fields optional: `ttl`, `proxied`, `ips` (at least 1 item), `nodes`. **Each given field replaces the stored value.**
`404` if the domain or zone doesn't exist.

```bash
# apex zone: "@" is encoded as %40
curl -s -X PATCH "$RCN_API_URL/api/config/domains/example.com/zones/%40" -H "X-API-Key: $RCN_API_TOKEN" \
  -H "Content-Type: application/json" -d '{"ttl": 300, "proxied": false}'
```

```python
def zone_path(domain: str, zone: str) -> str:
    return f"/api/config/domains/{quote(domain, safe='')}/zones/{quote(zone, safe='')}"


api.patch(zone_path("example.com", "@"), json={"ttl": 300, "proxied": False}).raise_for_status()
```

```js
await fetch(`${API_URL}/api/config/domains/example.com/zones/${encodeURIComponent("@")}`, {
  method: "PATCH",
  headers,
  body: JSON.stringify({ ttl: 300, proxied: false }),
});
```

### Delete zone — `DELETE /api/config/domains/{domain}/zones/{zone_name}`

Removes the zone and **immediately deletes its A records from Cloudflare**. `404` if the domain or zone doesn't exist.

```bash
curl -s -X DELETE "$RCN_API_URL/api/config/domains/example.com/zones/s2" -H "X-API-Key: $RCN_API_TOKEN"
```

```python
api.delete(zone_path("example.com", "s2")).raise_for_status()
```

---

## Common tasks

### Add or remove one IP in a zone

PATCH replaces the whole list, so read the zone, change the list, and send it back.

```python
def get_zone(domain: str, name: str) -> dict | None:
    for d in api.get("/api/config/domains").raise_for_status().json():
        if d["domain"] == domain:
            return next((z for z in d.get("zones") or [] if z["name"] == name), None)
    return None


def add_ip(domain: str, name: str, ip: str) -> None:
    ips = get_zone(domain, name).get("ips") or []
    if ip not in ips:
        api.patch(zone_path(domain, name), json={"ips": [*ips, ip]}).raise_for_status()


def remove_ip(domain: str, name: str, ip: str) -> None:
    ips = [i for i in get_zone(domain, name).get("ips") or [] if i != ip]
    if not ips:
        raise ValueError("'ips' cannot be emptied via PATCH; delete and re-create the zone")
    api.patch(zone_path(domain, name), json={"ips": ips}).raise_for_status()
```

For `nodes`, do the same on the `nodes` list, matching entries by `ip`.

### Create or update a zone

`POST` is not idempotent, so fall back to `PATCH` on `409`. Pass a complete zone (with `ips` and/or `nodes`) — a
partial one fails POST validation with `422` before the existence check.

```python
def upsert_zone(domain: str, zone: dict) -> None:
    r = api.post(f"/api/config/domains/{quote(domain, safe='')}/zones", json=zone)
    if r.status_code == 409:
        changes = {k: v for k, v in zone.items() if k != "name"}
        api.patch(zone_path(domain, zone["name"]), json=changes).raise_for_status()
    else:
        r.raise_for_status()
```

### Handle errors

```python
r = api.post(f"/api/config/domains/{quote('example.com', safe='')}/zones", json={"name": "s1"})
if r.is_error:
    detail = r.json()["detail"]
    if r.status_code == 422:
        # validation errors: list of {"type", "loc", "msg", "input"}
        for err in detail:
            print(".".join(map(str, err["loc"])), err["msg"])
    else:
        # 401 / 404 / 409: plain string
        print(r.status_code, detail)
```

| Code  | Meaning                        | `detail`                                       |
|-------|--------------------------------|------------------------------------------------|
| `401` | Missing or wrong `X-API-Key`   | `"Invalid or missing API key"`                 |
| `404` | Domain or zone not found       | `"Domain 'example.com' not found"`             |
| `409` | Domain or zone already exists  | `"Zone 's1' already exists for 'example.com'"` |
| `422` | Request body failed validation | list of `{type, loc, msg, input}`              |

---

## Behaviour to keep in mind

1. **Eventual effect.** Config is saved immediately, but DNS changes happen on the next monitoring cycle (up to
   `check_interval` seconds).
2. **Deletes are destructive.** Deleting a zone or domain removes its A records from Cloudflare right away.
3. **PATCH replaces lists.** Sending `ips` overwrites the whole `ips` list; same for `nodes`.
4. **`ips` and `nodes` are independent.** Patching one leaves the other untouched. Neither can be cleared through
   PATCH (`ips` requires at least one item, `null` is ignored) — delete and re-create the zone instead.
5. **No rename.** Zone `name` and `domain` cannot be changed; delete and re-create instead.
6. **Unknown fields are ignored.** A misspelled field is a silent no-op that still returns `200`.
7. **Exact matching.** Domain and zone names are matched as exact, case-sensitive strings. Normalize to lowercase and
   strip trailing dots before sending.
8. **Empty PATCH is a no-op** and still returns `200`.
9. **Every mutation sends a Telegram notification** on the service side (if enabled), including the caller IP.
