from typing import TYPE_CHECKING, Awaitable, Dict, Iterable, List, Optional, Set

from .client import CloudflareClient
from ..telegram import DNSChange, DNSError
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..telegram import Event, TelegramNotifier

_PAST_TENSE = {"add": "added", "remove": "removed"}


class DNSManager:
    def __init__(self, client: CloudflareClient, notifier: Optional["TelegramNotifier"] = None):
        self.client = client
        self.notifier = notifier
        self.logger = get_logger(__name__)
        self._zone_ids: Dict[str, str] = {}

    async def get_zone_id(self, domain: str) -> Optional[str]:
        """Resolve the Cloudflare zone ID for `domain`, caching successful lookups."""
        if domain not in self._zone_ids:
            zone_id = await self.client.get_zone_id(domain)
            if not zone_id:
                return None
            self._zone_ids[domain] = zone_id
        return self._zone_ids[domain]

    async def get_record_ips(self, zone_id: str, fqdn: str) -> List[str]:
        return [r["content"] for r in await self.client.get_dns_records(zone_id, name=fqdn, record_type="A")]

    async def sync(
            self,
            zone_id: str,
            fqdn: str,
            configured_ips: Iterable[str],
            healthy_ips: Set[str],
            ttl: int = 120,
            proxied: bool = False,
    ) -> Set[str]:
        """Reconcile A records for `fqdn` and return the IPs that remain published."""
        existing = {r["content"]: r for r in await self.client.get_dns_records(zone_id, name=fqdn, record_type="A")}

        configured = set(configured_ips)
        to_add = (configured & healthy_ips) - existing.keys()
        # Drop records of unhealthy nodes as well as records no longer in config
        to_remove = existing.keys() - (configured & healthy_ips)

        published = set(existing)
        for ip in sorted(to_add):
            if await self._apply(fqdn, ip, "add", self.client.create_dns_record(
                    zone_id=zone_id, name=fqdn, content=ip, record_type="A", ttl=ttl, proxied=proxied)):
                published.add(ip)
        for ip in sorted(to_remove):
            if await self._apply(fqdn, ip, "remove", self.client.delete_dns_record(zone_id, existing[ip]["id"])):
                published.discard(ip)

        if not to_add and not to_remove:
            unhealthy = configured - healthy_ips
            status = f"{len(configured & healthy_ips)}/{len(configured)} online"
            suffix = f", unhealthy: {', '.join(sorted(unhealthy))}" if unhealthy else ""
            self.logger.info(f"{fqdn}: {status}{suffix}")

        return published

    async def cleanup(self, zone_id: str, fqdn: str) -> None:
        """Remove every A record of `fqdn`."""
        try:
            records = await self.client.get_dns_records(zone_id, name=fqdn, record_type="A")
        except Exception as e:
            self.logger.error(f"{fqdn}: failed to fetch records for cleanup: {e}")
            return

        for record in records:
            await self._apply(fqdn, record["content"], "remove", self.client.delete_dns_record(zone_id, record["id"]))

    async def _apply(self, fqdn: str, ip: str, action: str, operation: Awaitable) -> bool:
        """Await a record change, logging and notifying the outcome. Returns True on success."""
        past = _PAST_TENSE[action]
        try:
            await operation
        except Exception as e:
            self.logger.error(f"{fqdn}: failed to {action} {ip}: {e}")
            self._notify(DNSError(fqdn=fqdn, ip_address=ip, action=action, error_message=str(e)))
            return False
        self.logger.info(f"{fqdn}: {past} {ip}")
        self._notify(DNSChange(fqdn=fqdn, ip_address=ip, action=past))
        return True

    def _notify(self, event: "Event") -> None:
        if self.notifier:
            self.notifier.notify(event)
