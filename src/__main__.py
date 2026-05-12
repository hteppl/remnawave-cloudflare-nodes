import asyncio
import signal
import sys

import uvicorn

from .cloudflare_dns import CloudflareClient, DNSManager
from .config import Config
from .hosts_config import HostsConfig
from .i18n import get_translator
from .monitoring_service import MonitoringService
from .panel import RemnawaveClient, NodeMonitor, HostManager
from .telegram import TelegramNotifier, ServiceStarted
from .utils.logger import setup_logger


class GracefulExit(SystemExit):
    code = 0


def raise_graceful_exit(signum, frame):
    raise GracefulExit()


async def run_api_server(app, host: str, port: int) -> None:
    server_config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(server_config)
    server.install_signal_handlers = lambda: None  # our signal handlers manage shutdown
    await server.serve()


async def run_monitoring_loop(service: MonitoringService, config: Config, logger):
    logger.info(f"Starting monitoring loop with {config.check_interval}s interval")

    while True:
        try:
            await service.perform_health_check()

            interval = config.check_interval
            logger.info(f"Waiting {interval} seconds until next check...")
            await asyncio.sleep(interval)

        except GracefulExit:
            logger.info("Received shutdown signal, stopping...")
            break
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, stopping...")
            break
        except Exception as e:
            interval = config.check_interval
            logger.info(f"Retrying in {interval} seconds after error: {e}")
            await asyncio.sleep(interval)


async def main():
    config = Config()
    config.validate()

    logger = setup_logger(name="remnawave-cloudflare-monitor", level=config.log_level, log_file="logs/app.log")

    signal.signal(signal.SIGTERM, raise_graceful_exit)
    signal.signal(signal.SIGINT, raise_graceful_exit)

    loop = asyncio.get_event_loop()

    def handle_sighup():
        try:
            config.reload()
            config.validate()
            if host_manager:
                host_manager.reload()
            logger.info("Config reloaded from disk successfully")
        except Exception as e:
            logger.error(f"Config reload failed, keeping current config: {e}")

    loop.add_signal_handler(signal.SIGHUP, handle_sighup)

    get_translator(config.language)

    logger.info("Starting Remnawave-Cloudflare DNS Monitor")
    logger.info(f"Check interval: {config.check_interval}s")

    remnawave_client = RemnawaveClient(api_url=config.remnawave_url, api_key=config.remnawave_api_key)

    node_monitor = NodeMonitor(remnawave_client)

    notifier = TelegramNotifier(
        bot_token=config.telegram_bot_token,
        chat_id=config.telegram_chat_id,
        topic_id=config.telegram_topic_id,
        enabled=config.telegram_enabled,
        notify_api_changes=config.telegram_notify_api_changes,
    )

    host_manager = HostManager(
        client=remnawave_client,
        notifier=notifier,
        enabled=config.disable_unreachable_hosts,
        notify_changes=config.telegram_notify_host_changes,
        hosts_config=HostsConfig(),
    )

    cloudflare_client = CloudflareClient(api_token=config.cloudflare_token)
    dns_manager = DNSManager(
        client=cloudflare_client,
        notifier=notifier,
        notify_dns_changes=config.telegram_notify_dns_changes,
        notify_errors=config.telegram_notify_errors,
    )

    monitoring_service = MonitoringService(
        config=config,
        node_monitor=node_monitor,
        cloudflare_client=cloudflare_client,
        dns_manager=dns_manager,
        host_manager=host_manager,
        notifier=notifier,
    )

    api_task = None

    try:
        await notifier.start()
        notifier.notify_service_started(
            ServiceStarted(
                domains=config.domains,
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
            try:
                await api_task
            except asyncio.CancelledError:
                pass
        notifier.notify_service_stopped()
        await notifier.stop()

    logger.info("Remnawave-Cloudflare DNS Monitor stopped")


if __name__ == "__main__":
    asyncio.run(main())
