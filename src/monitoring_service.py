import asyncio
from itertools import groupby
from operator import attrgetter
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from .cloudflare_dns import DNSManager
from .config import Config, Zone
from .remnawave_panel import HostManager, NodeMonitor, NodeStatus
from .telegram import (
    CriticalState,
    CriticalStateRecovered,
    Event,
    HealthCheckError,
    NodeStateChange,
    NodeStats,
    ZoneStats,
)
from .utils.dns import build_fqdn
from .utils.logger import get_logger

if TYPE_CHECKING:
    from .telegram import TelegramNotifier


class MonitoringService:
    def __init__(
            self,
            config: Config,
            node_monitor: NodeMonitor,
            dns_manager: DNSManager,
            host_manager: Optional[HostManager] = None,
            notifier: Optional["TelegramNotifier"] = None,
    ):
        self.config = config
        self.node_monitor = node_monitor
        self.dns_manager = dns_manager
        self.host_manager = host_manager
        self.notifier = notifier
        self.logger = get_logger(__name__)
        self._previous_node_states: Dict[str, bool] = {}
        self._previous_all_down: bool = False

    async def initialize(self) -> None:
        self.logger.info("Initializing zones")

        for domain, zones in groupby(self.config.get_all_zones(), key=attrgetter("domain")):
            zone_id = await self.dns_manager.get_zone_id(domain)
            if not zone_id:
                self.logger.warning(f"Could not find zone_id for domain {domain}")
                continue
            self.logger.info(f"Domain: {domain}, Zone ID: {zone_id}")

            for zone in zones:
                self.logger.info(f"  Zone: {zone.fqdn}, TTL: {zone.ttl}, Proxied: {zone.proxied}")
                for entry in zone.nodes:
                    note = f" (via {entry.address})" if entry.address != entry.ip else ""
                    self.logger.info(f"    Node: {entry.ip}{note}")

                existing = ", ".join(await self.dns_manager.get_record_ips(zone_id, zone.fqdn)) or "None"
                self.logger.info(f"  Existing DNS records: {existing}")

        self.logger.info("Initialization complete")

    async def run_health_check(self) -> None:
        self.logger.info("Starting health check cycle")

        try:
            zones = self.config.get_all_zones()
            all_nodes = await self.node_monitor.check_nodes()
            nodes_by_address = {node.address: node for node in all_nodes}

            configured_addresses = {entry.address for zone in zones for entry in zone.nodes}
            configured_nodes = [n for n in all_nodes if n.address in configured_addresses]
            unhealthy_nodes = [n for n in configured_nodes if not n.is_healthy]

            self.logger.info(
                f"Nodes: {len(configured_nodes) - len(unhealthy_nodes)}/{len(configured_nodes)} online, "
                f"{len(unhealthy_nodes)} unhealthy"
            )
            if unhealthy_nodes:
                details = "; ".join(f"{n.address} ({', '.join(n.unhealthy_reasons)})" for n in unhealthy_nodes)
                self.logger.info(f"Unhealthy nodes: {details}")

            self._report_node_transitions(configured_nodes, self._group_nodes_by_zone(zones, nodes_by_address))
            self._report_critical_state(configured_nodes, unhealthy_nodes)

            active_fqdns, managed_fqdns = await self._sync_all_zones(zones, nodes_by_address)

            if self.host_manager:
                await self.host_manager.sync(active_fqdns, managed_fqdns)

            self.logger.info("Health check cycle completed")

        except Exception as e:
            self.logger.error(f"Error during health check: {e}", exc_info=True)
            self._notify(HealthCheckError(error_message=str(e)))
            raise

    async def cleanup_zone(self, domain: str, zone_name: str) -> None:
        fqdn = build_fqdn(zone_name, domain)
        zone_id = await self.dns_manager.get_zone_id(domain)
        if not zone_id:
            self.logger.warning(f"Cannot cleanup {fqdn}: zone_id not found")
            return
        await self.dns_manager.cleanup(zone_id, fqdn)

    async def cleanup_domain(self, domain: str) -> None:
        zone_id = await self.dns_manager.get_zone_id(domain)
        if not zone_id:
            self.logger.warning(f"Cannot cleanup domain {domain}: zone_id not found")
            return
        for zone in self.config.get_all_zones():
            if zone.domain == domain:
                await self.dns_manager.cleanup(zone_id, zone.fqdn)

    # --- Internals ---

    def _notify(self, event: Event) -> None:
        if self.notifier:
            self.notifier.notify(event)

    async def _sync_all_zones(
            self, zones: List[Zone], nodes_by_address: Dict[str, NodeStatus]
    ) -> Tuple[Set[str], Set[str]]:
        """Sync all zones concurrently; returns (fqdns with published records, all managed fqdns)."""
        zone_ids: Dict[str, Optional[str]] = {}
        for domain in dict.fromkeys(zone.domain for zone in zones):
            zone_ids[domain] = await self.dns_manager.get_zone_id(domain)
            if not zone_ids[domain]:
                self.logger.warning(f"Could not find zone_id for domain {domain}, skipping")

        syncable = [zone for zone in zones if zone_ids[zone.domain]]

        def healthy_ips(zone: Zone) -> Set[str]:
            return {
                entry.ip for entry in zone.nodes
                if (node := nodes_by_address.get(entry.address)) and node.is_healthy
            }

        results = await asyncio.gather(
            *(
                self.dns_manager.sync(
                    zone_id=zone_ids[zone.domain],
                    fqdn=zone.fqdn,
                    configured_ips=zone.ips,
                    healthy_ips=healthy_ips(zone),
                    ttl=zone.ttl,
                    proxied=zone.proxied,
                )
                for zone in syncable
            ),
            return_exceptions=True,
        )
        if errors := [r for r in results if isinstance(r, BaseException)]:
            raise errors[0]

        active_fqdns = {zone.fqdn for zone, published in zip(syncable, results) if published}
        managed_fqdns = {zone.fqdn for zone in syncable}
        return active_fqdns, managed_fqdns

    @staticmethod
    def _group_nodes_by_zone(
            zones: List[Zone], nodes_by_address: Dict[str, NodeStatus]
    ) -> Dict[str, List[NodeStatus]]:
        """Map each zone FQDN to its unique, known nodes."""
        result: Dict[str, List[NodeStatus]] = {}
        for zone in zones:
            addresses = dict.fromkeys(entry.address for entry in zone.nodes)
            result[zone.fqdn] = [nodes_by_address[a] for a in addresses if a in nodes_by_address]
        return result

    def _report_node_transitions(self, nodes: List[NodeStatus], zone_nodes: Dict[str, List[NodeStatus]]) -> None:
        previous = self._previous_node_states

        def was_online(node: NodeStatus) -> bool:
            return previous.get(node.address, node.is_healthy)

        total = len(nodes)
        disabled = sum(n.is_disabled for n in nodes)
        online = sum(map(was_online, nodes))
        zone_online = {fqdn: sum(map(was_online, znodes)) for fqdn, znodes in zone_nodes.items()}

        # A node reports stats for the first zone it belongs to
        zone_of: Dict[str, str] = {}
        for fqdn, znodes in zone_nodes.items():
            for n in znodes:
                zone_of.setdefault(n.address, fqdn)

        for node in nodes:
            prev_healthy = previous.get(node.address)
            previous[node.address] = node.is_healthy
            if prev_healthy is None or prev_healthy == node.is_healthy:
                continue

            delta = 1 if node.is_healthy else -1
            online += delta

            zones_stats = []
            if fqdn := zone_of.get(node.address):
                zone_online[fqdn] += delta
                zones_stats.append(ZoneStats(name=fqdn, total=len(zone_nodes[fqdn]), online=zone_online[fqdn]))

            self._notify(
                NodeStateChange(
                    node_name=node.name,
                    node_address=node.address,
                    previous_healthy=prev_healthy,
                    current_healthy=node.is_healthy,
                    stats=NodeStats(total=total, online=online, disabled=disabled, zones=zones_stats),
                    reason=None if node.is_healthy else ", ".join(node.unhealthy_reasons) or "unknown",
                )
            )

    def _report_critical_state(self, configured_nodes: List[NodeStatus], unhealthy_nodes: List[NodeStatus]) -> None:
        all_down = 0 < len(configured_nodes) == len(unhealthy_nodes)

        if all_down and not self._previous_all_down:
            self._notify(
                CriticalState(total_nodes=len(configured_nodes), down_nodes=[n.address for n in unhealthy_nodes])
            )
        elif not all_down and self._previous_all_down:
            self._notify(
                CriticalStateRecovered(
                    total_nodes=len(configured_nodes),
                    online_nodes=len(configured_nodes) - len(unhealthy_nodes),
                )
            )

        self._previous_all_down = all_down
