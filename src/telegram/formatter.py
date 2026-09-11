from functools import singledispatchmethod
from typing import Iterable

from .events import (
    Event, NodeStateChange, NodeStats, DNSChange, DNSError,
    CriticalState, CriticalStateRecovered, HealthCheckError,
    ServiceStarted, ServiceStopped, HostStateChange,
    ApiConfigUpdated, ApiDomainAdded, ApiDomainRemoved,
    ApiZoneAdded, ApiZoneUpdated, ApiZoneRemoved,
)
from ..config import parse_zone_nodes
from ..i18n import get_translator
from ..utils.dns import build_fqdn


class MessageFormatter:
    def __init__(self):
        self._i18n = get_translator()

    def _t(self, message_id: str, **kwargs) -> str:
        return self._i18n.get(message_id, **kwargs)

    def _ip_list(self, ips: Iterable[str], indent: str = "") -> str:
        return "\n".join(indent + self._t("ip-list-item", ip=ip) for ip in ips)

    def _format_node_stats(self, stats: NodeStats) -> str:
        lines = [self._t("node-stats-line", online=stats.online, total=stats.total,
                         offline=stats.offline, disabled=stats.disabled)]
        lines += [
            self._t("node-zone-line", zone=z.name, online=z.online, total=z.total, offline=z.offline)
            for z in stats.zones
        ]
        return "\n".join(lines)

    @singledispatchmethod
    def format(self, event: Event) -> str:
        raise NotImplementedError(f"No formatter registered for {type(event).__name__}")

    @format.register
    def _(self, change: NodeStateChange) -> str:
        stats = self._format_node_stats(change.stats or NodeStats(total=0, online=0, disabled=0))
        if change.current_healthy:
            return self._t("node-became-healthy", name=change.node_name, address=change.node_address, stats=stats)
        return self._t(
            "node-became-unhealthy",
            name=change.node_name,
            address=change.node_address,
            reason=change.reason or self._t("node-reason-unknown"),
            stats=stats,
        )

    @format.register
    def _(self, change: DNSChange) -> str:
        msg_id = "dns-record-added" if change.action == "added" else "dns-record-removed"
        return self._t(msg_id, domain=change.fqdn, ip=change.ip_address)

    @format.register
    def _(self, error: DNSError) -> str:
        return self._t("dns-operation-error", domain=error.fqdn, ip=error.ip_address,
                       action=error.action, error=error.error_message)

    @format.register
    def _(self, state: CriticalState) -> str:
        return self._t("all-nodes-down", total=state.total_nodes, nodes=", ".join(state.down_nodes))

    @format.register
    def _(self, state: CriticalStateRecovered) -> str:
        return self._t("all-nodes-recovered", total=state.total_nodes, online=state.online_nodes)

    @format.register
    def _(self, error: HealthCheckError) -> str:
        return self._t("health-check-error", error=error.error_message)

    @format.register
    def _(self, event: ServiceStarted) -> str:
        zone_lines = [self._t("service-zone-line", zone=z.fqdn, count=z.node_count) for z in event.zones]
        summary = self._t("service-summary-header") + "\n" + (
            "\n".join(zone_lines) if zone_lines else self._t("service-no-zones")
        )
        if event.api_enabled:
            summary += "\n\n" + self._t("service-api-info", host=event.api_host, port=event.api_port)
        return self._t("service-started", summary=summary)

    @format.register
    def _(self, _event: ServiceStopped) -> str:
        return self._t("service-stopped")

    @format.register
    def _(self, change: HostStateChange) -> str:
        blocks = []
        for address, group in change.groups.items():
            action = "enabled" if group.action == "enabled" else "disabled"
            lines = [self._t(f"host-{action}", remark=remark) for remark in group.remarks]
            lines.append(self._t(f"host-group-{action}", address=address))
            blocks.append("\n".join(lines))
        return self._t("host-state-change", changes="\n\n".join(blocks))

    @format.register
    def _(self, event: ApiConfigUpdated) -> str:
        return self._t("api-config-updated", changes=", ".join(event.changes), ip=event.client_ip)

    @format.register
    def _(self, event: ApiDomainAdded) -> str:
        lines = []
        for zone in event.zones:
            lines.append(self._t("domain-zone-line", zone=build_fqdn(zone.get("name", ""), event.domain),
                                 ttl=zone.get("ttl", ""), proxied=zone.get("proxied", False)))
            lines += [self._ip_list([n.ip], indent="  ") for n in parse_zone_nodes(zone)]
        return self._t("api-domain-added", domain=event.domain, details="\n".join(lines), ip=event.client_ip)

    @format.register
    def _(self, event: ApiDomainRemoved) -> str:
        return self._t("api-domain-removed", domain=event.domain, ip=event.client_ip)

    @format.register
    def _(self, event: ApiZoneAdded) -> str:
        details = self._t("zone-added-details", ip_list=self._ip_list(event.ips),
                          ttl=event.ttl, proxied=event.proxied)
        return self._t("api-zone-added", fqdn=build_fqdn(event.zone_name, event.domain),
                       details=details, ip=event.client_ip)

    @format.register
    def _(self, event: ApiZoneUpdated) -> str:
        change_lines = []
        for key, value in event.changes.items():
            if key == "ips":
                change_lines.append(self._t("zone-change-ips", ip_list=self._ip_list(value)))
            elif key == "nodes":
                ips = (n.get("ip", "") for n in value)
                change_lines.append(self._t("zone-change-ips", ip_list=self._ip_list(ips)))
            elif key in ("ttl", "proxied"):
                change_lines.append(self._t(f"zone-change-{key}", value=value))
            else:
                change_lines.append(f"{key}={value}")
        return self._t("api-zone-updated", fqdn=build_fqdn(event.zone_name, event.domain),
                       changes="\n".join(change_lines), ip=event.client_ip)

    @format.register
    def _(self, event: ApiZoneRemoved) -> str:
        return self._t("api-zone-removed", fqdn=build_fqdn(event.zone_name, event.domain), ip=event.client_ip)
