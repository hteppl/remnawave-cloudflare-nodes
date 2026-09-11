from typing import Dict, List, Optional, Set

from .client import RemnawaveClient
from ..telegram import TelegramNotifier, HostStateChange
from ..utils.logger import get_logger
from ..hosts_config import HostsConfig


class HostManager:
    """Manages Remnawave host enable/disable state based on Cloudflare DNS presence.

    For each managed FQDN, if the zone has active DNS A records, any Remnawave host
    whose `address` matches that FQDN is kept enabled. If the zone has no A records
    (all nodes unhealthy / DNS removed), matching hosts are disabled.
    """

    def __init__(
        self,
        client: RemnawaveClient,
        notifier: Optional[TelegramNotifier] = None,
        enabled: bool = False,
        notify_changes: bool = True,
        hosts_config: Optional[HostsConfig] = None,
    ):
        self.client = client
        self.notifier = notifier
        self.enabled = enabled
        self.notify_changes = notify_changes
        self.hosts_config = hosts_config
        self.logger = get_logger(__name__)
        self._previous_host_states: Dict[str, bool] = {}

    def reload(self) -> None:
        if self.hosts_config:
            self.hosts_config.reload()
            self.logger.info(f"Hosts config reloaded: {len(self.hosts_config.uuids)} managed host(s)")
        else:
            self.logger.info("Hosts config not configured, nothing to reload")

    async def sync_host_states(self, active_fqdns: Set[str], managed_fqdns: Set[str]) -> None:
        if not self.enabled:
            return

        try:
            hosts = await self.client.get_hosts()
        except Exception as e:
            self.logger.error(f"Failed to fetch hosts: {e}")
            return

        to_disable: List[str] = []
        to_enable: List[str] = []
        changes: List[dict] = []
        current_uuids: Set[str] = set()

        for host in hosts:
            address = host.address
            if address not in managed_fqdns:
                continue

            host_uuid_str = str(host.uuid)
            current_uuids.add(host_uuid_str)

            # Skip hosts not in the safelist when hosts.yml is present
            if self.hosts_config and not self.hosts_config.is_managed(host_uuid_str):
                continue

            desired_enabled = address in active_fqdns
            current_enabled = not host.is_disabled
            prev_enabled = self._previous_host_states.get(host_uuid_str)

            if prev_enabled is None:
                # First encounter: silently sync to desired state if needed
                if desired_enabled != current_enabled:
                    if desired_enabled:
                        to_enable.append(host_uuid_str)
                    else:
                        to_disable.append(host_uuid_str)
                self._previous_host_states[host_uuid_str] = desired_enabled
                continue

            if desired_enabled == current_enabled:
                # Already in correct state
                self._previous_host_states[host_uuid_str] = current_enabled
                continue

            # State transition
            if desired_enabled:
                to_enable.append(host_uuid_str)
                changes.append({
                    "remark": host.remark,
                    "address": address,
                    "action": "enabled",
                })
                self.logger.info(f"Host {host.remark} ({address}) will be enabled")
            else:
                to_disable.append(host_uuid_str)
                changes.append({
                    "remark": host.remark,
                    "address": address,
                    "action": "disabled",
                })
                self.logger.info(f"Host {host.remark} ({address}) will be disabled")

            self._previous_host_states[host_uuid_str] = desired_enabled

        # Clean up stale entries
        stale = set(self._previous_host_states.keys()) - current_uuids
        for uuid in stale:
            del self._previous_host_states[uuid]

        if to_disable:
            try:
                await self.client.disable_hosts(to_disable)
                self.logger.info(f"Bulk disabled {len(to_disable)} hosts")
            except Exception as e:
                self.logger.error(f"Failed to disable hosts: {e}")
                # On API error, revert state tracking so next cycle retries
                for u in to_disable:
                    self._previous_host_states[u] = True

        if to_enable:
            try:
                await self.client.enable_hosts(to_enable)
                self.logger.info(f"Bulk enabled {len(to_enable)} hosts")
            except Exception as e:
                self.logger.error(f"Failed to enable hosts: {e}")
                for u in to_enable:
                    self._previous_host_states[u] = False

        if changes and self.notifier and self.notify_changes:
            # Group changes by address for richer telegram formatting
            grouped: dict = {}
            for c in changes:
                addr = c["address"]
                if addr not in grouped:
                    grouped[addr] = {"action": c["action"], "remarks": []}
                grouped[addr]["remarks"].append(c["remark"])
            self.notifier.notify_host_state_change(HostStateChange(changes=changes, grouped=grouped))
