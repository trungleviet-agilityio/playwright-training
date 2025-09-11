"""Enhanced browser manager using factory pattern."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from playwright.async_api import Page

from .factory import BrowserProviderFactory, BrowserProviderType
from ..config import settings
from ..storage import SessionStorage, MockSessionStorage, DynamoDBSessionStorage
import logging

logger = logging.getLogger(__name__)


class BrowserManager:
    """Enhanced browser manager with support for multiple providers."""

    def __init__(self):
        self.factory = BrowserProviderFactory()
        self._current_provider = None
        
        # Initialize session storage
        if settings.storage_type == "dynamodb":
            self.session_storage = DynamoDBSessionStorage()
        else:
            self.session_storage = MockSessionStorage()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        # Cleanup any resources if needed
        if self._current_provider:
            # Currently no cleanup needed for providers
            pass
        return False

    @asynccontextmanager
    async def get_page(
        self,
        headless: Optional[bool] = None,
        captcha_solving: bool = False,
        proxy_config: Optional[Dict[str, Any]] = None,
        browser_type: str = "chromium",
        provider_type: Optional[BrowserProviderType] = None,
        **kwargs,
    ) -> AsyncGenerator[Page, None]:
        """
        Get a browser page using the configured or specified provider.

        Args:
            headless: Whether to run browser in headless mode
            captcha_solving: Whether to enable automatic CAPTCHA solving
            proxy_config: Proxy configuration dict
            browser_type: Browser type for local provider
            provider_type: Override the configured browser provider
            **kwargs: Additional arguments passed to the provider
        """
        # Determine which provider to use
        if provider_type is None:
            if settings.browser_provider == "browserbase":
                provider_type = BrowserProviderType.BROWSERBASE
            else:
                provider_type = BrowserProviderType.LOCAL

        logger.info("Creating browser session with provider: %s", provider_type.value)

        try:
            # Create provider instance
            provider = self.factory.create_provider(provider_type)
            self._current_provider = provider

            # Get page from provider
            async with provider.get_page(
                headless=headless,
                captcha_solving=captcha_solving,
                proxy_config=proxy_config,
                browser_type=browser_type,
                **kwargs,
            ) as page:
                logger.info("Browser page created successfully")
                yield page

        except Exception as e:
            logger.error("Failed to create browser page: %s", e)

            # Fallback to local provider if Browserbase fails
            if provider_type == BrowserProviderType.BROWSERBASE:
                logger.info("Falling back to local browser provider...")
                try:
                    local_provider = self.factory.create_provider(
                        BrowserProviderType.LOCAL
                    )
                    self._current_provider = local_provider

                    async with local_provider.get_page(
                        headless=headless,
                        captcha_solving=False,  # Local doesn't support auto-solving
                        proxy_config=proxy_config,
                        browser_type=browser_type,
                        **kwargs,
                    ) as page:
                        logger.info("Fallback browser page created successfully")
                        yield page

                except Exception as fallback_error:
                    logger.error("Fallback browser also failed: %s", fallback_error)
                    raise
            else:
                raise

    def get_current_provider_type(self) -> Optional[str]:
        """Get the type of the currently active provider."""
        if self._current_provider is None:
            return None
        return self._current_provider.__class__.__name__

    async def create_persistent_session(
        self, provider_type: Optional[BrowserProviderType] = None, **kwargs
    ) -> str:
        """Create a persistent browser session."""
        if provider_type is None:
            if settings.browser_provider == "browserbase":
                provider_type = BrowserProviderType.BROWSERBASE
            else:
                provider_type = BrowserProviderType.LOCAL

        provider = self.factory.create_provider(provider_type)
        return await provider.create_session(**kwargs)

    async def close_persistent_session(
        self, session_id: str, provider_type: Optional[BrowserProviderType] = None
    ) -> bool:
        """Close a persistent browser session."""
        if provider_type is None:
            if settings.browser_provider == "browserbase":
                provider_type = BrowserProviderType.BROWSERBASE
            else:
                provider_type = BrowserProviderType.LOCAL

        provider = self.factory.create_provider(provider_type)
        return await provider.close_session(session_id)
    
    async def get_reusable_session(
        self, 
        provider: str, 
        provider_type: Optional[BrowserProviderType] = None
    ) -> Optional[str]:
        """Get a reusable session for the specified provider."""
        try:
            active_sessions = await self.session_storage.list_active_sessions(provider)
            if active_sessions:
                # Return the most recently accessed session
                most_recent = max(active_sessions, key=lambda s: s['last_accessed'])
                logger.info(f"Found reusable session {most_recent['session_id']} for provider {provider}")
                return most_recent['session_id']
            else:
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
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store session cookies for reuse."""
        try:
            return await self.session_storage.store_session(
                session_id, provider, cookies, metadata
            )
        except Exception as e:
            logger.error(f"Error storing session cookies: {e}")
            return False
    
    def get_browserbase_config(self) -> Dict[str, Any]:
        """Get Browserbase configuration based on debug script patterns."""
        return {
            "project_id": settings.browserbase_project_id,
            "browser_settings": {
                "stealth": settings.browserbase_stealth_mode,
                "solve_captchas": settings.browserbase_captcha_solving,
                "captcha_solving": {
                    "enabled": settings.browserbase_captcha_solving,
                    "auto_solve": settings.browserbase_auto_solve_captcha,
                    "timeout": settings.browserbase_captcha_timeout,
                    "retry_attempts": settings.browserbase_captcha_retry_attempts,
                    "provider": settings.browserbase_captcha_provider
                },
                "fingerprint": {
                    "devices": ["desktop"],
                    "locales": ["en-US", "en-GB", "en-CA"],
                    "operating_systems": ["linux", "windows", "macos"],
                    "timezones": ["America/New_York", "America/Los_Angeles", "Europe/London"],
                },
                "human_behavior": {
                    "mouse_movements": True,
                    "typing_patterns": True,
                    "scroll_behavior": True,
                    "click_timing": True,
                },
                "anti_detection": {
                    "webrtc_leak_protection": True,
                    "canvas_fingerprint_randomization": True,
                    "webgl_fingerprint_spoofing": True,
                    "font_fingerprint_randomization": True,
                },
            },
            "proxies": [
                {
                    "type": "residential",
                    "geolocation": {"country": "US"},
                    "rotation": "per-session"
                }
            ] if settings.browserbase_use_residential_proxy else None
        }