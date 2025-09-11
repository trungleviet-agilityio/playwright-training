"""Base classes for CAPTCHA solving."""

from abc import ABC, abstractmethod
from playwright.async_api import Page
from typing import Optional


class CaptchaSolver(ABC):
    """Abstract CAPTCHA solver interface."""

    @abstractmethod
    async def can_handle(self, page: Page) -> bool:
        """Check if this solver can handle the CAPTCHA on the page."""
        pass

    @abstractmethod
    async def solve(self, page: Page) -> bool:
        """Solve the CAPTCHA on the page."""
        pass

    @abstractmethod
    def get_priority(self) -> int:
        """Get solver priority (higher = preferred)."""
        pass
