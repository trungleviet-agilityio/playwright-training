"""Manual CAPTCHA solver implementation."""

import asyncio
import logging
from playwright.async_api import Page
from ..base import CaptchaSolver

logger = logging.getLogger(__name__)


class ManualCaptchaSolver(CaptchaSolver):
    """CAPTCHA solver that waits for manual intervention."""

    def __init__(self):
        self.priority = 10  # Lowest priority - used as fallback

    async def can_handle(self, page: Page) -> bool:
        """Check if CAPTCHA is present."""
        try:
            captcha_selectors = [
                'iframe[src*="recaptcha"]',
                '.g-recaptcha',
                '.h-captcha',
                '[data-sitekey]',
                'div[class*="captcha"]',
                '[data-callback*="captcha"]',
                'div[id*="captcha"]',
                '.captcha',
                '[aria-label*="captcha"]',
                'iframe[src*="hcaptcha"]',
                'div[class*="cf-turnstile"]',
            ]

            for selector in captcha_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        return True
                except Exception:
                    continue

            # Check for "I'm not a robot" text
            try:
                robot_text = await page.get_by_text("I'm not a robot").is_visible()
                if robot_text:
                    return True
            except Exception:
                pass

            return False

        except Exception:
            return False

    async def solve(self, page: Page) -> bool:
        """Wait for user to manually solve CAPTCHA."""
        logger.info("CAPTCHA detected. Please solve it manually in the browser...")
        print("🤖 CAPTCHA detected! Please solve it manually in the browser window.")
        print("⏳ Waiting up to 120 seconds for completion...")

        # Wait up to 120 seconds for CAPTCHA to be solved
        for i in range(120):
            await asyncio.sleep(1)
            
            # Check if CAPTCHA is still present
            if not await self.can_handle(page):
                logger.info("CAPTCHA solved manually!")
                print("✅ CAPTCHA solved successfully!")
                return True
            
            # Print progress every 30 seconds
            if i > 0 and i % 30 == 0:
                remaining = 120 - i
                print(f"⏳ Still waiting... {remaining} seconds remaining")

        logger.warning("Manual CAPTCHA solving timed out")
        print("❌ CAPTCHA solving timed out. Please try again.")
        return False

    def get_priority(self) -> int:
        """Get solver priority (higher = preferred)."""
        return self.priority
