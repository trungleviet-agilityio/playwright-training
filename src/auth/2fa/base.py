"""Base 2FA handler interface."""

from abc import ABC, abstractmethod
from typing import Optional
from playwright.async_api import Page
from src.models import LoginRequest


class TwoFAHandler(ABC):
    """Abstract base class for 2FA handling implementations."""

    @abstractmethod
    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Handle 2FA authentication."""
        pass

    @abstractmethod
    async def can_handle(self, page: Page) -> bool:
        """Check if this handler can handle the 2FA on the page."""
        pass

    @abstractmethod
    def get_priority(self) -> int:
        """Get handler priority (higher = preferred)."""
        pass
