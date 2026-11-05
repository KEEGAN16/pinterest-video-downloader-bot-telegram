"""In-process download admission for a small public Telegram bot.

All methods are synchronous and should be called from the Telegram event loop.
The check and reservation happen without an ``await``, making the admission
atomic relative to other event-loop tasks in the same Python process.
"""

import math
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Decision:
    allowed: bool
    message: str = ""


class DownloadLimiter:
    def __init__(
        self,
        max_concurrent: int = 2,
        cooldown_seconds: float = 30,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if cooldown_seconds < 0:
            raise ValueError("cooldown_seconds must be non-negative")

        self.max_concurrent = max_concurrent
        self.cooldown_seconds = cooldown_seconds
        self._clock = clock
        self._active_users: set[int] = set()
        self._last_finished: dict[int, float] = {}
        self._check_count = 0

    def try_start(self, user_id: int) -> Decision:
        """Reserve one global slot for user_id, or return an explanation."""
        self._check_count += 1
        if self._check_count % 200 == 0:
            self._prune_cooldowns()

        if user_id in self._active_users:
            return Decision(False, "⚠️ You already have a download in progress. Please wait.")

        last_finished = self._last_finished.get(user_id)
        if last_finished is not None:
            seconds_left = self.cooldown_seconds - (self._clock() - last_finished)
            if seconds_left > 0:
                return Decision(
                    False,
                    f"⏳ Please wait {math.ceil(seconds_left)} seconds before another download.",
                )

        if len(self._active_users) >= self.max_concurrent:
            return Decision(False, "🚦 The bot is busy right now. Please try again shortly.")

        self._active_users.add(user_id)
        return Decision(True)

    def finish(self, user_id: int) -> None:
        """Release an acquired slot and start the user's cooldown."""
        if user_id not in self._active_users:
            return

        self._active_users.remove(user_id)
        self._last_finished[user_id] = self._clock()

    def _prune_cooldowns(self) -> None:
        """Discard expired cooldowns occasionally to avoid unbounded growth."""
        now = self._clock()
        self._last_finished = {
            user_id: end
            for user_id, end in self._last_finished.items()
            if now - end < self.cooldown_seconds
        }
