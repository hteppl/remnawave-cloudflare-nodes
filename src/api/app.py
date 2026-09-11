from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse

from .auth import make_auth_dependency
from .models import ConfigPatch, DomainIn, ZoneIn, ZonePatch
from ..config import Config, ConfigConflictError, ConfigNotFoundError
from ..telegram import (
    Event,
    TelegramNotifier,
    ApiConfigUpdated,
    ApiDomainAdded,
    ApiDomainRemoved,
    ApiZoneAdded,
    ApiZoneUpdated,
    ApiZoneRemoved,
)
from ..utils.logger import get_logger

if TYPE_CHECKING:
    from ..monitoring_service import MonitoringService

logger = get_logger(__name__)

OK = {"status": "ok"}


def _client_ip(request: Request) -> str:
    if forwarded_for := request.headers.get("X-Forwarded-For"):
        return forwarded_for.split(",")[0].strip()
    if real_ip := request.headers.get("X-Real-IP"):
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"


ClientIP = Annotated[str, Depends(_client_ip)]


def _format_changes(updates: dict) -> str:
    parts = []
    for key, value in updates.items():
        if key == "ips":
            parts.append(f"ips={', '.join(value)}")
        elif key == "nodes":
            parts.append(f"nodes={len(value)} entry(s)")
        else:
            parts.append(f"{key}={value}")
    return ", ".join(parts)


def create_app(config: Config, notifier: TelegramNotifier, monitoring_service: "MonitoringService") -> FastAPI:
    app = FastAPI(
        title="Remnawave Cloudflare DNS Monitor",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        dependencies=[Depends(make_auth_dependency(config.api_token))],
    )

    @app.exception_handler(ConfigNotFoundError)
    async def not_found_handler(_: Request, exc: ConfigNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})

    @app.exception_handler(ConfigConflictError)
    async def conflict_handler(_: Request, exc: ConfigConflictError) -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})

    def notify(event: Event) -> None:
        if notifier:
            notifier.notify(event)

    @app.get("/api/config")
    async def get_config(ip: ClientIP):
        logger.debug(f"API: GET config [from {ip}]")
        return {
            "check_interval": config.check_interval,
            "log_level": config.log_level,
            "domains": config.domains,
            "disable_unreachable_hosts": config.disable_unreachable_hosts,
            "telegram": {
                "enabled": config.telegram_enabled,
                "language": config.language,
                "notify": {
                    "dns_changes": config.telegram_notify_dns_changes,
                    "node_changes": config.telegram_notify_node_changes,
                    "errors": config.telegram_notify_errors,
                    "critical": config.telegram_notify_critical,
                    "api_changes": config.telegram_notify_api_changes,
                    "host_changes": config.telegram_notify_host_changes,
                },
            },
        }

    @app.patch("/api/config")
    async def patch_config(ip: ClientIP, body: ConfigPatch):
        if body.check_interval is not None:
            config.update_check_interval(body.check_interval)
            changes = [f"check_interval={body.check_interval}"]
            logger.info(f"API: updated config [{', '.join(changes)}] [from {ip}]")
            notify(ApiConfigUpdated(changes=changes, client_ip=ip))
        return OK

    @app.get("/api/config/domains")
    async def list_domains(ip: ClientIP):
        domains = config.domains
        logger.debug(f"API: GET domains — {len(domains)} domain(s) [from {ip}]")
        return domains

    @app.post("/api/config/domains", status_code=status.HTTP_201_CREATED)
    async def add_domain(ip: ClientIP, body: DomainIn):
        zones = [z.model_dump(exclude_none=True) for z in body.zones]
        config.add_domain(domain=body.domain, zones=zones)
        logger.info(f"API: added domain '{body.domain}' with {len(zones)} zone(s) [from {ip}]")
        notify(ApiDomainAdded(domain=body.domain, zones=zones, client_ip=ip))
        return OK

    @app.delete("/api/config/domains/{domain}")
    async def remove_domain(ip: ClientIP, domain: str):
        if not config.has_domain(domain):
            raise ConfigNotFoundError(f"Domain '{domain}' not found")
        # Cleanup DNS before removing from config so zones are still readable
        await monitoring_service.cleanup_domain(domain)
        config.remove_domain(domain)
        logger.info(f"API: removed domain '{domain}' [from {ip}]")
        notify(ApiDomainRemoved(domain=domain, client_ip=ip))
        return OK

    @app.post("/api/config/domains/{domain}/zones", status_code=status.HTTP_201_CREATED)
    async def add_zone(ip: ClientIP, domain: str, body: ZoneIn):
        config.add_zone(domain, body.model_dump(exclude_none=True))
        logger.info(
            f"API: added zone '{body.name}' to '{domain}' "
            f"[{len(body.dns_ips)} node(s), ttl={body.ttl}, proxied={body.proxied}] [from {ip}]"
        )
        notify(ApiZoneAdded(domain=domain, zone_name=body.name, ips=body.dns_ips,
                            ttl=body.ttl, proxied=body.proxied, client_ip=ip))
        return OK

    @app.patch("/api/config/domains/{domain}/zones/{zone_name}")
    async def patch_zone(ip: ClientIP, domain: str, zone_name: str, body: ZonePatch):
        updates = body.model_dump(exclude_none=True)
        if not updates:
            return OK
        config.update_zone(domain, zone_name, **updates)
        logger.info(f"API: updated zone '{zone_name}' of '{domain}' [{_format_changes(updates)}] [from {ip}]")
        notify(ApiZoneUpdated(domain=domain, zone_name=zone_name, changes=updates, client_ip=ip))
        return OK

    @app.delete("/api/config/domains/{domain}/zones/{zone_name}")
    async def remove_zone(ip: ClientIP, domain: str, zone_name: str):
        config.remove_zone(domain, zone_name)
        await monitoring_service.cleanup_zone(domain, zone_name)
        logger.info(f"API: removed zone '{zone_name}' from '{domain}' [from {ip}]")
        notify(ApiZoneRemoved(domain=domain, zone_name=zone_name, client_ip=ip))
        return OK

    return app
