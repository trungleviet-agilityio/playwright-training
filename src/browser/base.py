"""Abstract browser provider interface."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional
from playwright.async_api import Page


class BrowserProvider(ABC):
    """Abstract browser provider interface for Playwright-based automation."""

    @abstractmethod
    async def get_page(
        self,
        headless: Optional[bool] = None,
        **kwargs,
    ) -> AsyncGenerator[Page, None]:
        """Get a Playwright page with automatic cleanup."""
        pass

    @abstractmethod
    async def create_session(self, **kwargs) -> str:
        """Create a new browser session."""
        pass

    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """Close a browser session."""
        pass
