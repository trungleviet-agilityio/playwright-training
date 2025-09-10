"""Browserbase browser provider with managed sessions."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional, Dict, Any
from playwright.async_api import async_playwright, Page

from browserbase import Browserbase

BROWSERBASE_AVAILABLE = True

from src.browser.base import BrowserProvider
from src.config import settings
from src.storage import SessionStorage, MockSessionStorage, DynamoDBSessionStorage

import logging

logger = logging.getLogger(__name__)


class BrowserbaseProvider(BrowserProvider):
    """Browserbase browser provider with managed sessions."""

    def __init__(self):
        if not BROWSERBASE_AVAILABLE:
            raise ValueError(
                "Browserbase library not available. Install with: pip install browserbase"
            )

        if not settings.browserbase_api_key:
            raise ValueError("BROWSERBASE_API_KEY is required for Browserbase provider")

        self.client = Browserbase(api_key=settings.browserbase_api_key)
        self.active_sessions: Dict[str, str] = {}  # session_id -> connect_url
        
        # Initialize session storage
        if settings.storage_type == "dynamodb":
            self.session_storage = DynamoDBSessionStorage()
        else:
            self.session_storage = MockSessionStorage()

    @asynccontextmanager
    async def get_page(
        self,
        headless: Optional[bool] = None,
        captcha_solving: bool = True,
        proxy_config: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> AsyncGenerator[Page, None]:
        """Get a Browserbase page with automatic cleanup."""

        session_config = {
            "project_id": settings.browserbase_project_id,
            "browser_settings": {
                "solve_captchas": captcha_solving,
                "fingerprint": {
                    "devices": ["desktop"],
                    "locales": ["en-US"],
                    "operating_systems": ["linux"],
                },
            },
        }

        # Add proxy configuration if provided
        if proxy_config:
            session_config["proxies"] = [proxy_config]
        elif settings.browserbase_use_residential_proxy:
            session_config["proxies"] = [
                {"type": "residential", "geolocation": {"country": "US"}}
            ]

        # Create session
        logger.info("Creating Browserbase session...")
        session = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.client.sessions.create(**session_config)
        )

        session_id = session.id
        connect_url = session.connect_url
        self.active_sessions[session_id] = connect_url

        logger.info("Browserbase session created: %s", session_id)

        try:
            # Connect Playwright to Browserbase session
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(connect_url)

                # Get the default context and page
                contexts = browser.contexts
                if contexts:
                    context = contexts[0]
                    pages = context.pages
                    if pages:
                        page = pages[0]
                    else:
                        page = await context.new_page()
                else:
                    context = await browser.new_context()
                    page = await context.new_page()

                # Set up CAPTCHA event listeners
                await self._setup_captcha_listeners(page)

                logger.info("Connected to Browserbase session successfully")
                yield page

        finally:
            # Clean up session
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.client.sessions.close(session_id)
                )
                logger.info("Browserbase session %s cleaned up", session_id)
            except Exception as e:
                logger.warning("Failed to clean up session %s: %s", session_id, e)

            if session_id in self.active_sessions:
                del self.active_sessions[session_id]

    async def _setup_captcha_listeners(self, page: Page) -> None:
        """Set up event listeners for CAPTCHA solving."""

        # Listen for Browserbase CAPTCHA events
        await page.evaluate(
            """
            window.addEventListener('browserbase-captcha-detected', (event) => {
                console.log('CAPTCHA detected by Browserbase:', event.detail);
            });
            
            window.addEventListener('browserbase-captcha-solved', (event) => {
                console.log('CAPTCHA solved by Browserbase:', event.detail);
            });
            
            window.addEventListener('browserbase-captcha-failed', (event) => {
                console.log('CAPTCHA solving failed:', event.detail);
            });
        """
        )

    async def create_session(self, **kwargs) -> str:
        """Create a new Browserbase session."""
        session_config = {
            "project_id": settings.browserbase_project_id,
            "browser_settings": {
                "solve_captchas": kwargs.get("captcha_solving", True),
                "fingerprint": {
                    "devices": ["desktop"],
                    "locales": ["en-US"],
                    "operating_systems": ["linux"],
                },
            },
        }

        # Add proxy configuration if provided
        if kwargs.get("proxy_config"):
            session_config["proxies"] = [kwargs["proxy_config"]]
        elif settings.browserbase_use_residential_proxy:
            session_config["proxies"] = [
                {"type": "residential", "geolocation": {"country": "US"}}
            ]

        # Create session
        logger.info("Creating persistent Browserbase session...")
        session = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.client.sessions.create(**session_config)
        )

        session_id = session.id
        connect_url = session.connect_url
        self.active_sessions[session_id] = connect_url

        logger.info(f"Persistent Browserbase session created: {session_id}")
        return session_id

    async def close_session(self, session_id: str) -> bool:
        """Close a Browserbase session."""
        # Implementation for session cleanup would go here
        if session_id in self.active_sessions:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.client.sessions.close(session_id)
                )
                del self.active_sessions[session_id]
                return True
            except Exception as e:
                logger.error("Error closing session %s: %s", session_id, e)
                return False
        return False
