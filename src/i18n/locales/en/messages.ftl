# Service lifecycle
service-started = <b>🚀 Service Started</b>
    Monitoring is now active.

    { $summary }

service-stopped = <b>🛑 Service Stopped</b>
    Monitoring has been shut down.

# Node status changes
node-became-healthy = <b>✅ Node Online</b>
    { $name } ({ $address }) is now available.

    { $stats }

node-became-unhealthy = <b>❌ Node Offline</b>
    { $name } ({ $address }) is unavailable.
    Reason: { $reason }

    { $stats }

# DNS operations
dns-record-added = <b>📝 DNS Updated</b>
    Added { $ip } → { $domain }

dns-record-removed = <b>🗑️ DNS Removed</b>
    Removed { $ip } from { $domain }

# Errors
dns-operation-error = <b>⚠️ DNS Error</b>
    Failed to { $action } { $ip } for { $domain }
    Error: { $error }

health-check-error = <b>⚠️ Health Check Failed</b>
    Error during health check: { $error }

# Critical states
all-nodes-down = <b>🔴 CRITICAL: All Nodes Down</b>
    All { $total } nodes are unreachable.
    Affected: { $nodes }

    DNS records have been cleared. Immediate attention required.

all-nodes-recovered = <b>🟢 Recovered: Nodes Back Online</b>
    { $online } of { $total } nodes are now reachable.
    DNS records have been restored.

# Format templates
node-reason-unknown = unknown
node-stats-line = 📊 Nodes: { $online }/{ $total } online, { $offline } offline, { $disabled } disabled
node-zone-line = • { $zone }: { $online }/{ $total } online, { $offline } offline
ip-list-item = • { $ip }
service-summary-header = 📡 Domains:
service-no-zones = —
service-zone-line = • { $zone } — { $count } IPs
service-api-info = 🔌 API: { $host }:{ $port }
domain-zone-line = • { $zone } (TTL: { $ttl }, Proxied: { $proxied })
zone-added-details =
    IPs:
            { $ip_list }
            TTL: { $ttl } | Proxied: { $proxied }
zone-change-ips =
    IPs:
            { $ip_list }
zone-change-ttl = TTL: { $value }
zone-change-proxied = Proxied: { $value }

# API events
api-config-updated = <b>⚙️ Config Updated via API</b>
    { $changes }
    From: { $ip }

api-domain-added = <b>➕ Domain Added via API</b>
    { $domain }
    { $details }
    From: { $ip }

api-domain-removed = <b>➖ Domain Removed via API</b>
    { $domain }
    From: { $ip }

api-zone-added = <b>➕ Zone Added via API</b>
    { $fqdn }
    { $details }
    From: { $ip }

api-zone-updated = <b>⚙️ Zone Updated via API</b>
    { $fqdn }
    { $changes }
    From: { $ip }

api-zone-removed = <b>➖ Zone Removed via API</b>
    { $fqdn }
    From: { $ip }

# Host state changes
host-enabled = • { $remark } is enabled ✅
host-disabled = • { $remark } is disabled ❌
host-group-enabled = <i>Some nodes managing { $address } are up</i>
host-group-disabled = <i>All nodes managing { $address } are down</i>
host-state-change = <b>🔧 Host State Changed</b>
    { $changes }
