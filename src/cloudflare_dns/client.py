import asyncio
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar

from cloudflare import AsyncCloudflare

from ..utils.logger import get_logger
from ..utils.retry import retry_async

T = TypeVar("T")


def _is_server_error(e: Exception) -> bool:
    """Client errors (4xx) are deterministic, so retrying them is pointless."""
    status_code = getattr(e, "status_code", None)
    return not (status_code and 400 <= status_code < 500)


def _record_to_dict(record: Any) -> Dict:
    return {
        "id": record.id,
        "name": record.name,
        "content": record.content,
        "type": record.type,
        "ttl": record.ttl,
        "proxied": record.proxied,
    }


class CloudflareClient:
    def __init__(self, api_token: str, rate_limit_delay: float = 0.25, retry_delay: float = 1.0, max_retries: int = 5):
        self.logger = get_logger(__name__)
        self.cf = AsyncCloudflare(api_token=api_token)
        self.rate_limit_delay = rate_limit_delay
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self._last_request_time: float = 0
        self._rate_limit_lock = asyncio.Lock()

    async def _rate_limit(self) -> None:
        async with self._rate_limit_lock:
            elapsed = time.monotonic() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - elapsed)
            self._last_request_time = time.monotonic()

    async def _request(
            self,
            description: str,
            operation: Callable[[], Awaitable[T]],
            should_retry: Callable[[Exception], bool] = lambda _: True,
    ) -> T:
        async def rate_limited() -> T:
            await self._rate_limit()
            return await operation()

        return await retry_async(
            rate_limited,
            description=description,
            logger=self.logger,
            attempts=self.max_retries,
            base_delay=self.retry_delay,
            should_retry=should_retry,
        )

    async def get_dns_records(self, zone_id: str, name: Optional[str] = None, record_type: str = "A") -> List[Dict]:
        params = {"type": record_type}
        if name:
            params["name"] = name

        async def fetch() -> List[Dict]:
            return [_record_to_dict(r) async for r in self.cf.dns.records.list(zone_id=zone_id, **params)]

        records = await self._request("Fetching DNS records", fetch)
        self.logger.debug(f"Found {len(records)} DNS records for zone {zone_id}")
        return records

    async def create_dns_record(
            self, zone_id: str, name: str, content: str, record_type: str = "A", ttl: int = 120, proxied: bool = False
    ) -> Dict:
        record = await self._request(
            "Creating DNS record",
            lambda: self.cf.dns.records.create(  # type: ignore[call-overload]
                zone_id=zone_id, type=record_type, name=name, content=content, ttl=int(ttl), proxied=proxied
            ),
            should_retry=_is_server_error,
        )
        self.logger.debug(f"Created DNS record: {name} -> {content}")
        return _record_to_dict(record)

    async def delete_dns_record(self, zone_id: str, record_id: str) -> None:
        await self._request(
            "Deleting DNS record",
            lambda: self.cf.dns.records.delete(dns_record_id=record_id, zone_id=zone_id),
        )
        self.logger.debug(f"Deleted DNS record: {record_id}")

    async def get_zone_id_by_domain(self, domain: str) -> Optional[str]:
        async def fetch() -> Optional[str]:
            async for zone in self.cf.zones.list(name=domain):
                return zone.id
            return None

        zone_id = await self._request(f"Fetching zone for domain {domain}", fetch)
        if zone_id:
            self.logger.info(f"Found zone_id for {domain}: {zone_id}")
        else:
            self.logger.error(f"No zone found for domain: {domain}")
        return zone_id
