import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
from playwright.async_api import Browser, Page, async_playwright
from ..base import BrowserProvider
from ...config import settings
import logging

logger = logging.getLogger(__name__)


class LocalBrowserProvider(BrowserProvider):
    """Local browser provider using Playwright for Slack OAuth2 authentication."""

    def __init__(self):
        self.active_sessions: Dict[str, Browser] = {}

    @asynccontextmanager
    async def get_page(
        self,
        headless: Optional[bool] = None,
        **kwargs,
    ) -> AsyncGenerator[Page, None]:
        """Get a local Playwright page for browser automation."""
        headless = headless if headless is not None else settings.headless

        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-web-security",
            "--disable-infobars",
            "--start-maximized",
            "--disable-gpu",
            "--no-first-run",
        ]

        user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )

        async with async_playwright() as p:
            if settings.browser_ws_endpoint:
                logger.info(
                    f"Connecting to remote browser: {settings.browser_ws_endpoint}"
                )
                browser = await p.chromium.connect_over_cdp(
                    settings.browser_ws_endpoint
                )
            else:
                logger.info("Launching local Chromium browser")
                browser = await p.chromium.launch(headless=headless, args=browser_args)

            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent=user_agent,
                java_script_enabled=True,
                accept_downloads=False,
                ignore_https_errors=True,
                extra_http_headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Cache-Control": "no-cache",
                    "Pragma": "no-cache",
                    "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="131", "Google Chrome";v="131"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Linux"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1",
                    "Upgrade-Insecure-Requests": "1",
                },
            )

            await context.add_init_script(
                """
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                window.chrome = {runtime: {}, loadTimes: function() {}, csi: function() {}, app: {}};
                Object.defineProperty(navigator, 'platform', {get: () => 'Linux x86_64'});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                """
            )

            page = await context.new_page()
            session_id = str(id(page))  # Simple session ID for local browser
            self.active_sessions[session_id] = browser

            try:
                logger.info("Local browser page created successfully")
                yield page
            except Exception as e:
                logger.error(f"Local browser page error: {e}")
                try:
                    await page.screenshot(
                        path=f"error_local_{session_id}.png", full_page=True
                    )
                    logger.info(f"Screenshot saved: error_local_{session_id}.png")
                except Exception:
                    pass
                raise
            finally:
                await context.close()
                if not settings.browser_ws_endpoint:
                    await browser.close()
                self.active_sessions.pop(session_id, None)
                logger.info(f"Local browser session {session_id} closed")

    async def create_session(self, **kwargs) -> str:
        """Create a local browser session (short-lived)."""
        async with self.get_page(**kwargs) as page:
            session_id = str(id(page))
            logger.info(f"Local browser session created: {session_id}")
            return session_id

    async def close_session(self, session_id: str) -> bool:
        """Close a local browser session."""
        if session_id in self.active_sessions:
            try:
                browser = self.active_sessions[session_id]
                await browser.close()
                self.active_sessions.pop(session_id)
                logger.info(f"Local browser session {session_id} closed")
                return True
            except Exception as e:
                logger.error(f"Error closing local session {session_id}: {e}")
                return False
        return False
