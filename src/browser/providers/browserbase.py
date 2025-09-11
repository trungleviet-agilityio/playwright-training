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
        """Get a Browserbase page with automatic cleanup following official documentation."""

        # Build session configuration following official Browserbase patterns
        session_config = {
            "project_id": settings.browserbase_project_id,
            "browser_settings": {
                # Basic Stealth Mode - automatically enabled by Browserbase
                "solveCaptchas": captcha_solving and settings.browserbase_captcha_solving,
            },
        }

        # Add Advanced Stealth Mode if configured (Scale plan only)
        if settings.browserbase_stealth_mode == "advanced":
            session_config["browser_settings"]["advancedStealth"] = True

        # Add proxy configuration for better CAPTCHA success rates
        if proxy_config:
            session_config["proxies"] = [proxy_config]
        elif settings.browserbase_use_residential_proxy:
            session_config["proxies"] = True  # Use Browserbase's automatic proxy selection

        # Add custom CAPTCHA selectors if provided (following official documentation)
        if kwargs.get("captcha_image_selector"):
            session_config["browser_settings"]["captchaImageSelector"] = kwargs["captcha_image_selector"]
        if kwargs.get("captcha_input_selector"):
            session_config["browser_settings"]["captchaInputSelector"] = kwargs["captcha_input_selector"]

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

                # Set up CAPTCHA event listeners and monitoring
                await self._setup_captcha_listeners(page)

                logger.info("Connected to Browserbase session successfully")
                
                # Keep browser alive during the entire authentication process
                try:
                    yield page
                except Exception as e:
                    logger.error(f"Error during page usage: {e}")
                    # Take screenshot for debugging
                    try:
                        await page.screenshot(path="browserbase_error_screenshot.png")
                        logger.info("📸 Error screenshot saved as browserbase_error_screenshot.png")
                    except Exception:
                        pass
                    raise
                finally:
                    # Keep browser open for a bit to allow debugging
                    logger.info("Keeping browser open for 5 seconds for debugging...")
                    await asyncio.sleep(5)

        except Exception as e:
            logger.error(f"Browserbase session error: {e}")
            raise
        finally:
            # Clean up session
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.client.sessions.delete(session_id)
                )
                logger.info("Browserbase session %s cleaned up", session_id)
            except Exception as e:
                logger.warning("Failed to clean up session %s: %s", session_id, e)

            if session_id in self.active_sessions:
                del self.active_sessions[session_id]

    async def _setup_captcha_listeners(self, page: Page) -> None:
        """Set up event listeners for CAPTCHA solving following official documentation."""

        # Set up console message monitoring for official Browserbase CAPTCHA events
        def handle_console(msg):
            message_text = msg.text.lower()
            
            # Official Browserbase CAPTCHA events from documentation
            if "browserbase-solving-started" in message_text:
                logger.info("🎯 CAPTCHA solving process has begun (browserbase-solving-started)")
            elif "browserbase-solving-finished" in message_text:
                logger.info("✅ CAPTCHA solved successfully! (browserbase-solving-finished)")
            elif "browserbase-solving-failed" in message_text:
                logger.warning("❌ CAPTCHA solving failed (browserbase-solving-failed)")
            elif "browserbase" in message_text and "captcha" in message_text:
                logger.info(f"🔍 Browserbase CAPTCHA event: {msg.text}")
        
        # Set up console event listener
        page.on("console", handle_console)
        
        logger.info("✅ CAPTCHA monitoring setup complete - listening for official Browserbase events")


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
                    None, lambda: self.client.sessions.delete(session_id)
                )
                del self.active_sessions[session_id]
                return True
            except Exception as e:
                logger.error("Error closing session %s: %s", session_id, e)
                return False
        return False
