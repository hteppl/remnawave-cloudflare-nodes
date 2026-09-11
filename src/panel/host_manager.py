from typing import Dict, List, Optional, Set

from .client import RemnawaveClient
from ..hosts_config import HostsConfig
from ..telegram import HostGroupChange, HostStateChange, TelegramNotifier
from ..utils.logger import get_logger


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
            hosts_config: Optional[HostsConfig] = None,
    ):
        self.client = client
        self.notifier = notifier
        self.enabled = enabled
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

        pending: Dict[bool, List[str]] = {False: [], True: []}  # disable first, then enable
        groups: Dict[str, HostGroupChange] = {}
        seen_uuids: Set[str] = set()

        for host in hosts:
            if host.address not in managed_fqdns:
                continue

            uuid = str(host.uuid)
            seen_uuids.add(uuid)

            # Skip hosts not in the safelist when hosts.yml is present
            if self.hosts_config and not self.hosts_config.is_managed(uuid):
                continue

            desired = host.address in active_fqdns
            is_first_encounter = uuid not in self._previous_host_states
            self._previous_host_states[uuid] = desired

            if desired == (not host.is_disabled):
                continue

            pending[desired].append(uuid)
            # First encounter syncs silently; only real transitions are reported
            if not is_first_encounter:
                action = "enabled" if desired else "disabled"
                groups.setdefault(host.address, HostGroupChange(action=action)).remarks.append(host.remark)
                self.logger.info(f"Host {host.remark} ({host.address}) will be {action}")

        for uuid in self._previous_host_states.keys() - seen_uuids:
            del self._previous_host_states[uuid]

        for enabled, uuids in pending.items():
            if uuids:
                await self._apply(uuids, enabled)

        if groups and self.notifier:
            self.notifier.notify(HostStateChange(groups=groups))

    async def _apply(self, uuids: List[str], enabled: bool) -> None:
        action = "enable" if enabled else "disable"
        try:
            await self.client.set_hosts_enabled(uuids, enabled)
            self.logger.info(f"Bulk {action}d {len(uuids)} hosts")
        except Exception as e:
            self.logger.error(f"Failed to {action} hosts: {e}")
            # Revert state tracking so the next cycle retries
            for uuid in uuids:
                self._previous_host_states[uuid] = not enabled
