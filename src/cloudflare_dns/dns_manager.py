from typing import TYPE_CHECKING, Dict, List, Optional, Set

from .client import CloudflareClient
from ..utils.dns import build_fqdn
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..telegram import TelegramNotifier


class DNSManager:
    def __init__(
            self,
            client: CloudflareClient,
            notifier: Optional["TelegramNotifier"] = None,
            notify_dns_changes: bool = True,
            notify_errors: bool = True,
    ):
        self.client = client
        self.logger = get_logger(__name__)
        self.notifier = notifier
        self.notify_dns_changes = notify_dns_changes
        self.notify_errors = notify_errors

    async def sync_dns_records(
            self,
            zone_id: str,
            zone_name: str,
            domain: str,
            configured_ips: List[str],
            healthy_ips: Set[str],
            ttl: int = 120,
            proxied: bool = False,
    ) -> Set[str]:
        """Synchronize DNS records and return the set of IPs that are actively published."""
        full_domain = build_fqdn(zone_name, domain)

        existing_records = await self.client.get_dns_records(zone_id, name=full_domain, record_type="A")
        existing_ips = {record["content"] for record in existing_records}
        existing_by_ip: Dict[str, dict] = {record["content"]: record for record in existing_records}

        configured_set = set(configured_ips)
        healthy_configured_ips = configured_set & healthy_ips
        unhealthy_ips = configured_set - healthy_ips

        added_count = 0
        removed_count = 0

        for ip in healthy_configured_ips:
            if ip not in existing_ips:
                if await self._add_record(zone_id, full_domain, domain, zone_name, ip, ttl, proxied):
                    added_count += 1

        for ip in unhealthy_ips:
            if ip in existing_by_ip:
                if await self._remove_record(zone_id, domain, zone_name, ip, existing_by_ip[ip]):
                    removed_count += 1

        for ip, record in existing_by_ip.items():
            if ip not in configured_set:
                if await self._remove_record(zone_id, domain, zone_name, ip, record):
                    removed_count += 1

        status = f"{len(healthy_configured_ips)}/{len(configured_ips)} online"

        if not added_count and not removed_count:
            if unhealthy_ips:
                self.logger.info(f"{full_domain}: {status}, unhealthy: {', '.join(unhealthy_ips)}")
            else:
                self.logger.info(f"{full_domain}: {status}")

        return existing_ips | healthy_configured_ips

    async def _add_record(
            self, zone_id: str, full_domain: str, domain: str, zone_name: str, ip: str, ttl: int, proxied: bool
    ) -> bool:
        try:
            await self.client.create_dns_record(
                zone_id=zone_id, name=full_domain, content=ip, record_type="A", ttl=ttl, proxied=proxied
            )
            self.logger.info(f"{full_domain}: added {ip}")
            if self.notifier and self.notify_dns_changes:
                from ..telegram import DNSChange

                self.notifier.notify_dns_change(
                    DNSChange(domain=domain, zone_name=zone_name, ip_address=ip, action="added")
                )
            return True
        except Exception as e:
            self.logger.error(f"{full_domain}: failed to add {ip}: {e}")
            if self.notifier and self.notify_errors:
                from ..telegram import DNSError

                self.notifier.notify_dns_error(
                    DNSError(domain=domain, zone_name=zone_name, ip_address=ip, action="add", error_message=str(e))
                )
            return False

    async def _remove_record(self, zone_id: str, domain: str, zone_name: str, ip: str, record: dict) -> bool:
        full_domain = build_fqdn(zone_name, domain)
        try:
            await self.client.delete_dns_record(zone_id, record["id"])
            self.logger.info(f"{full_domain}: removed {ip}")
            if self.notifier and self.notify_dns_changes:
                from ..telegram import DNSChange

                self.notifier.notify_dns_change(
                    DNSChange(domain=domain, zone_name=zone_name, ip_address=ip, action="removed")
                )
            return True
        except Exception as e:
            self.logger.error(f"{full_domain}: failed to remove {ip}: {e}")
            if self.notifier and self.notify_errors:
                from ..telegram import DNSError

                self.notifier.notify_dns_error(
                    DNSError(domain=domain, zone_name=zone_name, ip_address=ip, action="remove", error_message=str(e))
                )
            return False

    async def cleanup_zone(self, zone_id: str, zone_name: str, domain: str) -> None:
        full_domain = build_fqdn(zone_name, domain)
        try:
            existing_records = await self.client.get_dns_records(zone_id, name=full_domain, record_type="A")
        except Exception as e:
            self.logger.error(f"{full_domain}: failed to fetch records for cleanup: {e}")
            return

        for record in existing_records:
            await self._remove_record(zone_id, domain, zone_name, record["content"], record)

    async def get_all_zone_records(self, zone_id: str, domain: str) -> List[dict]:
        try:
            records = await self.client.get_dns_records(zone_id, record_type="A")
            zone_records = [r for r in records if r["name"].endswith(domain)]
            return zone_records
        except Exception as e:
            self.logger.error(f"Failed to get zone records: {e}")
            return []
