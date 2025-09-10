"""No-operation CAPTCHA solver implementation."""

import logging
from playwright.async_api import Page
from ..base import CaptchaSolver

logger = logging.getLogger(__name__)


class NoopCaptchaSolver(CaptchaSolver):
    """No-operation CAPTCHA solver that always succeeds without action."""

    def __init__(self):
        self.priority = 0  # Lowest priority

    async def can_handle(self, page: Page) -> bool:
        """Always returns True to handle any CAPTCHA."""
        return True

    async def solve(self, page: Page) -> bool:
        """No-op implementation that always succeeds."""
        logger.info("No-op CAPTCHA solver: Skipping CAPTCHA solving")
        return True

    def get_priority(self) -> int:
        """Get solver priority (higher = preferred)."""
        return self.priority
