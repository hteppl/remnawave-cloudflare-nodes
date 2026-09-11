import asyncio
from typing import Iterable, Optional

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter

from .events import Event, EventCategory
from .formatter import MessageFormatter
from ..utils.logger import get_logger
from ..utils.retry import retry_async


class TelegramNotifier:
    """Formats events and delivers them to Telegram through a background queue."""

    def __init__(
            self,
            bot_token: str,
            chat_id: str,
            topic_id: Optional[int] = None,
            enabled: bool = True,
            muted: Iterable[EventCategory] = (),
            queue_size: int = 100,
            retry_attempts: int = 3,
            retry_delay: float = 1.0,
            rate_limit_delay: float = 0.1,
    ):
        self.logger = get_logger(__name__)
        self.chat_id = chat_id
        self.topic_id = topic_id
        self.muted = frozenset(muted)
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.rate_limit_delay = rate_limit_delay

        self._queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_size)
        self._worker_task: Optional[asyncio.Task] = None
        self._bot: Optional[Bot] = None
        self._formatter: Optional[MessageFormatter] = None

        self.enabled = bool(enabled and bot_token and chat_id)
        if self.enabled:
            self._bot = Bot(token=bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
            self._formatter = MessageFormatter()
            topic_info = f", topic_id={topic_id}" if topic_id else ""
            self.logger.info(f"TelegramNotifier initialized{topic_info}")
        else:
            self.logger.info("TelegramNotifier is disabled")

    async def start(self) -> None:
        if self.enabled:
            self._worker_task = asyncio.create_task(self._worker())
            self.logger.info("TelegramNotifier worker started")

    async def stop(self) -> None:
        if not self._worker_task:
            return

        try:
            await asyncio.wait_for(self._queue.join(), timeout=5.0)
        except asyncio.TimeoutError:
            self.logger.warning("Timed out waiting for notification queue to drain")

        self._worker_task.cancel()
        try:
            await self._worker_task
        except asyncio.CancelledError:
            pass
        self._worker_task = None

        await self._bot.session.close()
        self.logger.info("TelegramNotifier stopped")

    def notify(self, event: Event) -> None:
        """Queue a notification for `event` unless its category is muted."""
        if not self.enabled or event.category in self.muted:
            return
        try:
            self._queue.put_nowait(self._formatter.format(event))
        except asyncio.QueueFull:
            self.logger.warning("Notification queue is full, dropping message")

    async def _worker(self) -> None:
        while True:
            message = await self._queue.get()
            try:
                await retry_async(
                    lambda: self._send(message),
                    description="Sending Telegram notification",
                    logger=self.logger,
                    attempts=self.retry_attempts,
                    base_delay=self.retry_delay,
                )
            except Exception as e:
                self.logger.error(f"Giving up on notification: {e}")
            finally:
                self._queue.task_done()
            await asyncio.sleep(self.rate_limit_delay)

    async def _send(self, message: str) -> None:
        while True:
            try:
                await self._bot.send_message(chat_id=self.chat_id, text=message, message_thread_id=self.topic_id)
                return
            except TelegramRetryAfter as e:
                self.logger.warning(f"Telegram rate limit hit, waiting {e.retry_after}s")
                await asyncio.sleep(e.retry_after)
