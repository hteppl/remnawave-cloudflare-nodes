from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ZoneStats:
    name: str
    total: int
    online: int
    offline: int


@dataclass
class NodeStats:
    total: int
    online: int
    offline: int
    disabled: int
    zones: List["ZoneStats"]


@dataclass
class NodeStateChange:
    node_name: str
    node_address: str
    previous_healthy: bool
    current_healthy: bool
    stats: Optional[NodeStats] = None
    reason: Optional[str] = None


@dataclass
class DNSChange:
    domain: str
    zone_name: str
    ip_address: str
    action: str  # "added" or "removed"


@dataclass
class DNSError:
    domain: str
    zone_name: str
    ip_address: str
    action: str
    error_message: str


@dataclass
class CriticalState:
    total_nodes: int
    down_nodes: List[str]


@dataclass
class CriticalStateRecovered:
    total_nodes: int
    online_nodes: int


@dataclass
class HealthCheckError:
    error_message: str


@dataclass
class ServiceStarted:
    domains: List[dict]
    api_enabled: bool = False
    api_host: str = ""
    api_port: int = 0


@dataclass
class HostStateChange:
    changes: List[dict]  # each dict has: remark, address, action ("enabled" or "disabled")
    # Grouped by address for better formatting: {address: {"action": "enabled|disabled", "remarks": [...]}}
    grouped: Optional[dict] = None


# API events

@dataclass
class ApiConfigUpdated:
    changes: List[str]
    client_ip: str


@dataclass
class ApiDomainAdded:
    domain: str
    zones: List[dict]
    client_ip: str


@dataclass
class ApiDomainRemoved:
    domain: str
    client_ip: str


@dataclass
class ApiZoneAdded:
    domain: str
    zone_name: str
    ips: List[str]
    ttl: int
    proxied: bool
    client_ip: str


@dataclass
class ApiZoneUpdated:
    domain: str
    zone_name: str
    changes: dict
    client_ip: str


@dataclass
class ApiZoneRemoved:
    domain: str
    zone_name: str
    client_ip: str
