from typing import Callable, Dict, Iterable, Type

from .events import (
    Event, NodeStateChange, NodeStats, DNSChange, DNSError,
    CriticalState, CriticalStateRecovered, HealthCheckError,
    ServiceStarted, ServiceStopped, HostStateChange,
    APIConfigUpdated, APIDomainAdded, APIDomainRemoved,
    APIZoneAdded, APIZoneUpdated, APIZoneRemoved,
)
from ..config import parse_zone_nodes
from ..i18n import get_translator
from ..utils.dns import build_fqdn


_FORMATTERS: Dict[Type[Event], Callable[["TelegramFormatter", Event], str]] = {}


def _formats(event_type: Type[Event]):
    """Register the decorated method as the formatter for `event_type`."""

    def register(method):
        _FORMATTERS[event_type] = method
        return method

    return register


class TelegramFormatter:
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

    def format(self, event: Event) -> str:
        formatter = _FORMATTERS.get(type(event))
        if formatter is None:
            raise NotImplementedError(f"No formatter registered for {type(event).__name__}")
        return formatter(self, event)

    @_formats(NodeStateChange)
    def _format_node_state_change(self, change: NodeStateChange) -> str:
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

    @_formats(DNSChange)
    def _format_dns_change(self, change: DNSChange) -> str:
        msg_id = "dns-record-added" if change.action == "added" else "dns-record-removed"
        return self._t(msg_id, domain=change.fqdn, ip=change.ip_address)

    @_formats(DNSError)
    def _format_dns_error(self, error: DNSError) -> str:
        return self._t("dns-operation-error", domain=error.fqdn, ip=error.ip_address,
                       action=error.action, error=error.error_message)

    @_formats(CriticalState)
    def _format_critical_state(self, state: CriticalState) -> str:
        return self._t("all-nodes-down", total=state.total_nodes, nodes=", ".join(state.down_nodes))

    @_formats(CriticalStateRecovered)
    def _format_critical_state_recovered(self, state: CriticalStateRecovered) -> str:
        return self._t("all-nodes-recovered", total=state.total_nodes, online=state.online_nodes)

    @_formats(HealthCheckError)
    def _format_health_check_error(self, error: HealthCheckError) -> str:
        return self._t("health-check-error", error=error.error_message)

    @_formats(ServiceStarted)
    def _format_service_started(self, event: ServiceStarted) -> str:
        zone_lines = [self._t("service-zone-line", zone=z.fqdn, count=z.node_count) for z in event.zones]
        summary = self._t("service-summary-header") + "\n" + (
            "\n".join(zone_lines) if zone_lines else self._t("service-no-zones")
        )
        if event.api_enabled:
            summary += "\n\n" + self._t("service-api-info", host=event.api_host, port=event.api_port)
        return self._t("service-started", summary=summary)

    @_formats(ServiceStopped)
    def _format_service_stopped(self, _event: ServiceStopped) -> str:
        return self._t("service-stopped")

    @_formats(HostStateChange)
    def _format_host_state_change(self, change: HostStateChange) -> str:
        blocks = []
        for address, group in change.groups.items():
            action = "enabled" if group.action == "enabled" else "disabled"
            lines = [self._t(f"host-{action}", remark=remark) for remark in group.remarks]
            lines.append(self._t(f"host-group-{action}", address=address))
            blocks.append("\n".join(lines))
        return self._t("host-state-change", changes="\n\n".join(blocks))

    @_formats(APIConfigUpdated)
    def _format_api_config_updated(self, event: APIConfigUpdated) -> str:
        return self._t("api-config-updated", changes=", ".join(event.changes), ip=event.client_ip)

    @_formats(APIDomainAdded)
    def _format_api_domain_added(self, event: APIDomainAdded) -> str:
        lines = []
        for zone in event.zones:
            lines.append(self._t("domain-zone-line", zone=build_fqdn(zone.get("name", ""), event.domain),
                                 ttl=zone.get("ttl", ""), proxied=zone.get("proxied", False)))
            lines += [self._ip_list([n.ip], indent="  ") for n in parse_zone_nodes(zone)]
        return self._t("api-domain-added", domain=event.domain, details="\n".join(lines), ip=event.client_ip)

    @_formats(APIDomainRemoved)
    def _format_api_domain_removed(self, event: APIDomainRemoved) -> str:
        return self._t("api-domain-removed", domain=event.domain, ip=event.client_ip)

    @_formats(APIZoneAdded)
    def _format_api_zone_added(self, event: APIZoneAdded) -> str:
        details = self._t("zone-added-details", ip_list=self._ip_list(event.ips),
                          ttl=event.ttl, proxied=event.proxied)
        return self._t("api-zone-added", fqdn=build_fqdn(event.zone_name, event.domain),
                       details=details, ip=event.client_ip)

    @_formats(APIZoneUpdated)
    def _format_api_zone_updated(self, event: APIZoneUpdated) -> str:
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

    @_formats(APIZoneRemoved)
    def _format_api_zone_removed(self, event: APIZoneRemoved) -> str:
        return self._t("api-zone-removed", fqdn=build_fqdn(event.zone_name, event.domain), ip=event.client_ip)
