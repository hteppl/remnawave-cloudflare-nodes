import asyncio
import contextlib
import logging
import signal
import sys

import uvicorn

from .cloudflare_dns import CloudflareClient, DNSManager
from .config import Config
from .hosts_config import HostsConfig
from .i18n import get_translator
from .monitoring_service import MonitoringService
from .panel import RemnawaveClient, NodeMonitor, HostManager
from .telegram import EventCategory, ServiceStarted, ServiceStopped, TelegramNotifier, ZoneSummary
from .utils.logger import setup_logger


class GracefulExit(SystemExit):
    code = 0


def raise_graceful_exit(signum, frame):
    raise GracefulExit()


def muted_categories(config: Config) -> set[EventCategory]:
    toggles = {
        EventCategory.NODE: config.telegram_notify_node_changes,
        EventCategory.DNS: config.telegram_notify_dns_changes,
        EventCategory.ERROR: config.telegram_notify_errors,
        EventCategory.CRITICAL: config.telegram_notify_critical,
        EventCategory.HOST: config.telegram_notify_host_changes,
        EventCategory.API: config.telegram_notify_api_changes,
    }
    return {category for category, enabled in toggles.items() if not enabled}


async def run_api_server(app, host: str, port: int) -> None:
    server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
    server.install_signal_handlers = lambda: None  # our signal handlers manage shutdown
    await server.serve()


async def run_monitoring_loop(service: MonitoringService, config: Config, logger: logging.Logger) -> None:
    logger.info(f"Starting monitoring loop with {config.check_interval}s interval")

    while True:
        try:
            await service.perform_health_check()
            logger.info(f"Waiting {config.check_interval} seconds until next check...")
        except Exception as e:
            logger.info(f"Retrying in {config.check_interval} seconds after error: {e}")
        await asyncio.sleep(config.check_interval)


async def main():
    config = Config()
    config.validate()

    logger = setup_logger(name="remnawave-cloudflare-monitor", level=config.log_level, log_file="logs/app.log")
    get_translator(config.language)

    logger.info("Starting Remnawave-Cloudflare DNS Monitor")
    logger.info(f"Check interval: {config.check_interval}s")

    notifier = TelegramNotifier(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        topic_id=config.telegram_topic_id,
        enabled=config.telegram_enabled,
        muted=muted_categories(config),
    )
    remnawave_client = RemnawaveClient(api_url=config.remnawave_url, api_key=config.remnawave_api_key)
    cloudflare_client = CloudflareClient(api_token=config.cloudflare_token)
    host_manager = HostManager(
        client=remnawave_client,
        notifier=notifier,
        enabled=config.disable_unreachable_hosts,
        hosts_config=HostsConfig(),
    )
    monitoring_service = MonitoringService(
        config=config,
        node_monitor=NodeMonitor(remnawave_client),
        cloudflare_client=cloudflare_client,
        dns_manager=DNSManager(client=cloudflare_client, notifier=notifier),
        host_manager=host_manager,
        notifier=notifier,
    )

    def handle_sighup():
        try:
            config.reload()
            config.validate()
            host_manager.reload()
            logger.info("Config reloaded from disk successfully")
        except Exception as e:
            logger.error(f"Config reload failed, keeping current config: {e}")

    signal.signal(signal.SIGTERM, raise_graceful_exit)
    signal.signal(signal.SIGINT, raise_graceful_exit)
    asyncio.get_running_loop().add_signal_handler(signal.SIGHUP, handle_sighup)

    api_task = None
    try:
        await notifier.start()
        notifier.notify(
            ServiceStarted(
                zones=[ZoneSummary(fqdn=z.fqdn, node_count=len(z.nodes)) for z in config.get_all_zones()],
                api_enabled=config.api_enabled,
                api_host=config.api_host,
                api_port=config.api_port,
            )
        )

        await monitoring_service.initialize_and_print_zones()

        if config.api_enabled:
            from .api import create_app

            api_app = create_app(config, notifier, monitoring_service)
            api_task = asyncio.create_task(run_api_server(api_app, config.api_host, config.api_port))
            logger.info(f"API server listening on {config.api_host}:{config.api_port}")

        await run_monitoring_loop(service=monitoring_service, config=config, logger=logger)
    except (GracefulExit, KeyboardInterrupt):
        logger.info("Shutting down gracefully")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if api_task:
            api_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await api_task
        notifier.notify(ServiceStopped())
        await notifier.stop()

    logger.info("Remnawave-Cloudflare DNS Monitor stopped")


if __name__ == "__main__":
    asyncio.run(main())
