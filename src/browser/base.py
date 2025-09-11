"""Abstract browser provider interface."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any
from playwright.async_api import Page


class BrowserProvider(ABC):
    """Abstract browser provider interface."""

    @abstractmethod
    async def get_page(
        self,
        headless: Optional[bool] = None,
        captcha_solving: bool = False,
        proxy_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncGenerator[Page, None]:
        """Get a browser page with automatic cleanup."""
        pass

    @abstractmethod
    async def create_session(self, **kwargs) -> str:
        """Create a new browser session."""
        pass

    @abstractmethod
    async def close_session(self, session_id: str) -> bool:
        """Close a browser session."""
        pass
