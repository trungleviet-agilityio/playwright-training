"""Browserbase provider for Playwright-based browser automation."""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from playwright.async_api import async_playwright, Page
from browserbase import Browserbase
import logging
from src.browser.base import BrowserProvider
from src.config import settings
from src.storage import SessionStorage, MockSessionStorage, DynamoDBSessionStorage

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class BrowserbaseProvider(BrowserProvider):
    """Browserbase provider for Playwright-based browser automation."""

    def __init__(self):
        try:
            from browserbase import Browserbase
        except ImportError:
            raise ValueError(
                "Browserbase library not available. Install with: pip install browserbase"
            )

        if not settings.browserbase_api_key:
            raise ValueError("BROWSERBASE_API_KEY is required")

        self.client = Browserbase(api_key=settings.browserbase_api_key)
        self.active_sessions: Dict[str, str] = {}  # session_id -> connect_url

        # Initialize session storage
        self.session_storage = (
            DynamoDBSessionStorage()
            if settings.storage_type == "dynamodb"
            else MockSessionStorage()
        )

    @asynccontextmanager
    async def get_page(
        self,
        headless: Optional[bool] = None,
        **kwargs,
    ) -> AsyncGenerator[Page, None]:
        """Get a Browserbase Playwright page."""
        session_config = {"project_id": settings.browserbase_project_id}

        logger.info("Creating Browserbase session...")
        session = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.client.sessions.create(**session_config)
        )

        session_id = session.id
        connect_url = session.connect_url
        self.active_sessions[session_id] = connect_url
        logger.info(f"Browserbase session created: {session_id}")

        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(connect_url)
                context = (
                    browser.contexts[0]
                    if browser.contexts
                    else await browser.new_context()
                )
                page = context.pages[0] if context.pages else await context.new_page()

                logger.info("Connected to Browserbase session")
                yield page

        except Exception as e:
            logger.error(f"Browserbase session error: {e}")
            try:
                await page.screenshot(path=f"error_{session_id}.png", full_page=True)
                logger.info(f"Screenshot saved: error_{session_id}.png")
            except Exception:
                pass
            raise
        finally:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.client.sessions.close(session_id)
                )
                logger.info(f"Browserbase session {session_id} closed")
            except Exception as e:
                logger.warning(f"Failed to close session {session_id}: {e}")
            self.active_sessions.pop(session_id, None)

    async def create_session(self, **kwargs) -> str:
        """Create a new Browserbase session."""
        session_config = {"project_id": settings.browserbase_project_id}
        session = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.client.sessions.create(**session_config)
        )
        session_id = session.id
        self.active_sessions[session_id] = session.connect_url
        logger.info(f"Persistent Browserbase session created: {session_id}")
        return session_id

    async def close_session(self, session_id: str) -> bool:
        """Close a Browserbase session."""
        if session_id in self.active_sessions:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.client.sessions.close(session_id)
                )
                self.active_sessions.pop(session_id)
                logger.info(f"Session {session_id} closed")
                return True
            except Exception as e:
                logger.error(f"Error closing session {session_id}: {e}")
                return False
        return False
