"""Manual 2FA handler for fallback scenarios."""

import asyncio
import logging
from playwright.async_api import Page

from .base import TwoFAHandler
from src.models import LoginRequest

logger = logging.getLogger(__name__)


class ManualTwoFAHandler(TwoFAHandler):
    """Manual 2FA handler that waits for user input."""

    def __init__(self):
        self.priority = 10  # Lower priority - used as fallback

    async def can_handle(self, page: Page) -> bool:
        """Check if 2FA is present."""
        try:
            twofa_selectors = [
                'input[placeholder*="code" i]',
                'input[placeholder*="verification" i]',
                'input[placeholder*="2fa" i]',
                'input[placeholder*="two-factor" i]',
                'input[name*="code"]',
                'input[name*="verification"]',
                'input[id*="code"]',
                'input[id*="verification"]',
                'input[data-qa*="code"]',
                'input[data-qa*="verification"]',
                'input[type="tel"][maxlength="6"]',
                'input[autocomplete="one-time-code"]',
            ]

            for selector in twofa_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        return True
                except Exception:
                    continue

            # Check for 2FA text indicators
            text_indicators = [
                "Enter verification code",
                "Two-factor authentication",
                "Enter the 6-digit code",
                "Authentication required",
                "Enter your authenticator code",
                "Enter your security code"
            ]

            for text in text_indicators:
                try:
                    element = page.get_by_text(text)
                    if await element.is_visible():
                        return True
                except Exception:
                    continue

            return False

        except Exception:
            return False

    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Wait for user to manually enter 2FA code."""
        if not await self.can_handle(page):
            return True

        print(f"🔐 2FA required for {request.email}")
        print("Please enter the 2FA code manually in the browser...")
        print("⏳ Waiting up to 120 seconds for completion...")

        # Wait up to 120 seconds for 2FA to be completed
        for i in range(120):
            await asyncio.sleep(1)

            # Check if 2FA is still present
            if not await self.can_handle(page):
                print("✅ 2FA completed successfully!")
                logger.info("2FA completed manually")
                return True

            # Print progress every 30 seconds
            if i > 0 and i % 30 == 0:
                remaining = 120 - i
                print(f"⏳ Still waiting... {remaining} seconds remaining")

        print("❌ 2FA verification timed out")
        logger.warning("Manual 2FA verification timed out")
        return False

    def get_priority(self) -> int:
        """Get handler priority (higher = preferred)."""
        return self.priority
