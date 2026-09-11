import asyncio
from typing import Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from .events import (
    NodeStateChange, DNSChange, DNSError, CriticalState, CriticalStateRecovered, HealthCheckError,
    ServiceStarted, HostStateChange,
    ApiConfigUpdated, ApiDomainAdded, ApiDomainRemoved,
    ApiZoneAdded, ApiZoneUpdated, ApiZoneRemoved,
)
from .formatter import MessageFormatter
from ..utils.logger import get_logger


class TelegramNotifier:
    def __init__(
            self,
            bot_token: str,
            chat_id: str,
            topic_id: Optional[int] = None,
            enabled: bool = True,
            notify_api_changes: bool = True,
            queue_size: int = 100,
            retry_attempts: int = 3,
            retry_delay: float = 1.0,
            rate_limit_delay: float = 0.1,
    ):
        self.logger = get_logger(__name__)
        self.enabled = enabled
        self.notify_api_changes = notify_api_changes
        self.chat_id = chat_id
        self.topic_id = topic_id
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.rate_limit_delay = rate_limit_delay

        self._bot: Optional[Bot] = None
        self._formatter: Optional[MessageFormatter] = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

        if enabled and bot_token and chat_id:
            self._bot = Bot(
                token=bot_token,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            self._formatter = MessageFormatter()
            topic_info = f", topic_id={topic_id}" if topic_id else ""
            self.logger.info(f"TelegramNotifier initialized{topic_info}")
        else:
            self.enabled = False
            self.logger.info("TelegramNotifier is disabled")

    async def start(self) -> None:
        if not self.enabled or not self._bot:
            return

        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        self.logger.info("TelegramNotifier worker started")

    async def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        try:
            await asyncio.wait_for(self._queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            self.logger.warning("Timed out waiting for notification queue to drain")

        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        if self._bot:
            await self._bot.session.close()

        self.logger.info("TelegramNotifier stopped")

    async def _worker(self) -> None:
        while self._running:
            try:
                try:
                    message = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                await self._send_with_retry(message)
                self._queue.task_done()
                await asyncio.sleep(self.rate_limit_delay)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in notification worker: {e}")

    async def _send_with_retry(self, message: str) -> None:
        attempt = 0
        while True:
            try:
                await self._bot.send_message(
                    chat_id=self.chat_id,
                    text=message,
                    message_thread_id=self.topic_id,
                )
                return
            except TelegramRetryAfter as e:
                self.logger.warning(f"Telegram rate limit hit, waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
            except TelegramAPIError as e:
                attempt += 1
                if attempt >= self.retry_attempts:
                    self.logger.error(f"Giving up on notification after {attempt} attempts: {e}")
                    return
                delay = min(self.retry_delay * attempt, 30.0)
                self.logger.warning(
                    f"Telegram API error (attempt {attempt}/{self.retry_attempts}), retrying in {delay}s: {e}")
                await asyncio.sleep(delay)
            except Exception as e:
                attempt += 1
                if attempt >= self.retry_attempts:
                    self.logger.error(f"Giving up on notification after {attempt} attempts: {e}")
                    return
                delay = min(self.retry_delay * attempt, 30.0)
                self.logger.error(
                    f"Failed to send notification (attempt {attempt}/{self.retry_attempts}), retrying in {delay}s: {e}")
                await asyncio.sleep(delay)

    def _enqueue(self, message: str) -> None:
        if not self.enabled or not message:
            return

        try:
            self._queue.put_nowait(message)
        except asyncio.QueueFull:
            self.logger.warning("Notification queue is full, dropping message")

    def notify_node_state_change(self, change: NodeStateChange) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_node_state_change(change)
        self._enqueue(message)

    def notify_dns_change(self, change: DNSChange) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_dns_change(change)
        self._enqueue(message)

    def notify_dns_error(self, error: DNSError) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_dns_error(error)
        self._enqueue(message)

    def notify_critical_state(self, state: CriticalState) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_critical_state(state)
        self._enqueue(message)

    def notify_critical_recovered(self, state: CriticalStateRecovered) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_critical_recovered(state)
        self._enqueue(message)

    def notify_health_check_error(self, error: HealthCheckError) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_health_check_error(error)
        self._enqueue(message)

    def notify_service_started(self, event: ServiceStarted) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_service_started(event)
        self._enqueue(message)

    def notify_service_stopped(self) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_service_stopped()
        self._enqueue(message)

    def notify_host_state_change(self, change: HostStateChange) -> None:
        if not self.enabled:
            return
        message = self._formatter.format_host_state_change(change)
        self._enqueue(message)

    def notify_api_config_updated(self, event: ApiConfigUpdated) -> None:
        if not self.enabled or not self.notify_api_changes:
            return
        message = self._formatter.format_api_config_updated(event)
        self._enqueue(message)

    def notify_api_domain_added(self, event: ApiDomainAdded) -> None:
        if not self.enabled or not self.notify_api_changes:
            return
        message = self._formatter.format_api_domain_added(event)
        self._enqueue(message)

    def notify_api_domain_removed(self, event: ApiDomainRemoved) -> None:
        if not self.enabled or not self.notify_api_changes:
            return
        message = self._formatter.format_api_domain_removed(event)
        self._enqueue(message)

    def notify_api_zone_added(self, event: ApiZoneAdded) -> None:
        if not self.enabled or not self.notify_api_changes:
            return
        message = self._formatter.format_api_zone_added(event)
        self._enqueue(message)

    def notify_api_zone_updated(self, event: ApiZoneUpdated) -> None:
        if not self.enabled or not self.notify_api_changes:
            return
        message = self._formatter.format_api_zone_updated(event)
        self._enqueue(message)

    def notify_api_zone_removed(self, event: ApiZoneRemoved) -> None:
        if not self.enabled or not self.notify_api_changes:
            return
        message = self._formatter.format_api_zone_removed(event)
        self._enqueue(message)
