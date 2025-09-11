"""Browser manager for Playwright-based automation."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from playwright.async_api import Page
from .factory import BrowserProviderFactory, BrowserProviderType
from ..config import settings
from ..storage import SessionStorage, MockSessionStorage, DynamoDBSessionStorage
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """Browser manager for Playwright-based automation."""

    def __init__(self):
        self.factory = BrowserProviderFactory()
        self._current_provider = None
        self._session_stats = {
            "total_sessions": 0,
            "successful_sessions": 0,
            "failed_sessions": 0,
        }
        self.session_storage = (
            DynamoDBSessionStorage()
            if settings.storage_type == "dynamodb"
            else MockSessionStorage()
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.info(f"Session statistics: {self._session_stats}")
        return False

    @asynccontextmanager
    async def get_page(
        self,
        headless: Optional[bool] = None,
        provider_type: Optional[BrowserProviderType] = None,
        **kwargs,
    ) -> AsyncGenerator[Page, None]:
        """Get a Playwright page with fallback support."""
        self._session_stats["total_sessions"] += 1
        provider_type = provider_type or (
            BrowserProviderType.BROWSERBASE
            if settings.browser_provider == "browserbase"
            else BrowserProviderType.LOCAL
        )

        logger.info(f"Creating browser session with provider: {provider_type.value}")
        try:
            provider = self.factory.create_provider(provider_type)
            self._current_provider = provider
            logger.info(f"Provider created: {provider.__class__.__name__}")
            async with provider.get_page(headless=headless, **kwargs) as page:
                logger.info("Browser page created successfully")
                self._session_stats["successful_sessions"] += 1
                yield page
        except Exception as e:
            logger.error(f"Failed to create browser page: {e}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            self._session_stats["failed_sessions"] += 1
            if provider_type == BrowserProviderType.BROWSERBASE:
                logger.info("Falling back to local browser provider")
                try:
                    provider = self.factory.create_provider(BrowserProviderType.LOCAL)
                    self._current_provider = provider
                    async with provider.get_page(headless=headless, **kwargs) as page:
                        logger.info("Fallback browser page created")
                        self._session_stats["successful_sessions"] += 1
                        yield page
                except Exception as fallback_error:
                    logger.error(f"Fallback browser failed: {fallback_error}")
                    self._session_stats["failed_sessions"] += 1
                    raise
            else:
                raise

    def get_current_provider_type(self) -> Optional[str]:
        """Get the type of the currently active provider."""
        return (
            self._current_provider.__class__.__name__
            if self._current_provider
            else None
        )

    def get_session_stats(self) -> Dict[str, int]:
        """Get current session statistics."""
        return self._session_stats.copy()

    async def create_persistent_session(
        self, provider_type: Optional[BrowserProviderType] = None, **kwargs
    ) -> str:
        """Create a persistent browser session."""
        provider_type = provider_type or (
            BrowserProviderType.BROWSERBASE
            if settings.browser_provider == "browserbase"
            else BrowserProviderType.LOCAL
        )
        provider = self.factory.create_provider(provider_type)
        return await provider.create_session(**kwargs)

    async def close_persistent_session(
        self, session_id: str, provider_type: Optional[BrowserProviderType] = None
    ) -> bool:
        """Close a persistent browser session."""
        provider_type = provider_type or (
            BrowserProviderType.BROWSERBASE
            if settings.browser_provider == "browserbase"
            else BrowserProviderType.LOCAL
        )
        provider = self.factory.create_provider(provider_type)
        return await provider.close_session(session_id)

    async def get_reusable_session(
        self, provider: str, provider_type: Optional[BrowserProviderType] = None
    ) -> Optional[str]:
        """Get a reusable session for the specified provider."""
        try:
            active_sessions = await self.session_storage.list_active_sessions(provider)
            if active_sessions:
                most_recent = max(active_sessions, key=lambda s: s["last_accessed"])
                logger.info(
                    f"Found reusable session {most_recent['session_id']} for provider {provider}"
                )
                return most_recent["session_id"]
            logger.info(f"No reusable sessions found for provider {provider}")
            return None
        except Exception as e:
            logger.error(f"Error getting reusable session for provider {provider}: {e}")
            return None

    async def store_session_cookies(
        self,
        session_id: str,
        provider: str,
        cookies: list,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Store session cookies for reuse."""
        try:
            return await self.session_storage.store_session(
                session_id, provider, cookies, metadata
            )
        except Exception as e:
            logger.error(f"Error storing session cookies: {e}")
            return False
