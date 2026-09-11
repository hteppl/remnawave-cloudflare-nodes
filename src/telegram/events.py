from dataclasses import dataclass, field
from enum import StrEnum
from typing import ClassVar, Dict, List, Optional


class EventCategory(StrEnum):
    """Notification categories; each can be muted independently via TELEGRAM_NOTIFY_* settings."""

    SERVICE = "service"
    NODE = "node"
    DNS = "dns"
    ERROR = "error"
    CRITICAL = "critical"
    HOST = "host"
    API = "api"


@dataclass
class Event:
    category: ClassVar[EventCategory] = EventCategory.SERVICE


@dataclass
class ZoneStats:
    name: str
    total: int
    online: int

    @property
    def offline(self) -> int:
        return self.total - self.online


@dataclass
class NodeStats:
    total: int
    online: int
    disabled: int
    zones: List[ZoneStats] = field(default_factory=list)

    @property
    def offline(self) -> int:
        return self.total - self.online


@dataclass
class NodeStateChange(Event):
    category = EventCategory.NODE

    node_name: str
    node_address: str
    previous_healthy: bool
    current_healthy: bool
    stats: Optional[NodeStats] = None
    reason: Optional[str] = None


@dataclass
class DNSChange(Event):
    category = EventCategory.DNS

    fqdn: str
    ip_address: str
    action: str  # "added" or "removed"


@dataclass
class DNSError(Event):
    category = EventCategory.ERROR

    fqdn: str
    ip_address: str
    action: str  # "add" or "remove"
    error_message: str


@dataclass
class CriticalState(Event):
    category = EventCategory.CRITICAL

    total_nodes: int
    down_nodes: List[str]


@dataclass
class CriticalStateRecovered(Event):
    category = EventCategory.CRITICAL

    total_nodes: int
    online_nodes: int


@dataclass
class HealthCheckError(Event):
    category = EventCategory.ERROR

    error_message: str


@dataclass
class ZoneSummary:
    fqdn: str
    node_count: int


@dataclass
class ServiceStarted(Event):
    zones: List[ZoneSummary]
    api_enabled: bool = False
    api_host: str = ""
    api_port: int = 0


@dataclass
class ServiceStopped(Event):
    pass


@dataclass
class HostGroupChange:
    action: str  # "enabled" or "disabled"
    remarks: List[str] = field(default_factory=list)


@dataclass
class HostStateChange(Event):
    category = EventCategory.HOST

    groups: Dict[str, HostGroupChange]  # keyed by host address


# API events

@dataclass
class ApiEvent(Event):
    category = EventCategory.API


@dataclass
class ApiConfigUpdated(ApiEvent):
    changes: List[str]
    client_ip: str


@dataclass
class ApiDomainAdded(ApiEvent):
    domain: str
    zones: List[dict]
    client_ip: str


@dataclass
class ApiDomainRemoved(ApiEvent):
    domain: str
    client_ip: str


@dataclass
class ApiZoneAdded(ApiEvent):
    domain: str
    zone_name: str
    ips: List[str]
    ttl: int
    proxied: bool
    client_ip: str


@dataclass
class ApiZoneUpdated(ApiEvent):
    domain: str
    zone_name: str
    changes: dict
    client_ip: str


@dataclass
class ApiZoneRemoved(ApiEvent):
    domain: str
    zone_name: str
    client_ip: str
