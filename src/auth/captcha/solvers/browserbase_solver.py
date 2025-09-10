"""Browserbase CAPTCHA solver implementation."""

import logging
import asyncio
from typing import Optional
from playwright.async_api import Page
from ..base import CaptchaSolver

logger = logging.getLogger(__name__)


class BrowserbaseCaptchaSolver(CaptchaSolver):
    """CAPTCHA solver that relies on Browserbase's automatic solving."""

    def __init__(self):
        self.priority = 100  # Highest priority when available

    async def can_handle(self, page: Page) -> bool:
        """Check if CAPTCHA is present and Browserbase can handle it."""
        try:
            # Check for common CAPTCHA indicators
            captcha_indicators = [
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
                'div[class*="cf-turnstile"]',  # Cloudflare Turnstile
            ]

            for selector in captcha_indicators:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info(f"CAPTCHA detected with selector: {selector}")
                        return True
                except Exception:
                    continue

            # Check for "I'm not a robot" text
            try:
                robot_text = await page.get_by_text("I'm not a robot").is_visible()
                if robot_text:
                    logger.info("CAPTCHA detected by 'I'm not a robot' text")
                    return True
            except Exception:
                pass

            return False

        except Exception as e:
            logger.error(f"Error checking for CAPTCHA: {e}")
            return False

    async def solve(self, page: Page) -> bool:
        """
        Solve CAPTCHA using Browserbase's automatic solving.
        
        Note: Browserbase handles CAPTCHA solving automatically in the background.
        This method monitors for completion signals.
        """
        logger.info("Browserbase CAPTCHA solver: Waiting for automatic solving...")

        try:
            # Set up event listeners for Browserbase CAPTCHA events
            await page.evaluate("""
                window.browserbaseCaptchaEvents = {
                    detected: false,
                    solved: false,
                    failed: false
                };
                
                window.addEventListener('browserbase-captcha-detected', (event) => {
                    console.log('Browserbase: CAPTCHA detected', event.detail);
                    window.browserbaseCaptchaEvents.detected = true;
                });
                
                window.addEventListener('browserbase-captcha-solved', (event) => {
                    console.log('Browserbase: CAPTCHA solved', event.detail);
                    window.browserbaseCaptchaEvents.solved = true;
                });
                
                window.addEventListener('browserbase-captcha-failed', (event) => {
                    console.log('Browserbase: CAPTCHA solving failed', event.detail);
                    window.browserbaseCaptchaEvents.failed = true;
                });
            """)

            # Wait for Browserbase to solve the CAPTCHA (up to 60 seconds)
            for attempt in range(60):
                await asyncio.sleep(1)

                # Check if CAPTCHA was solved
                events = await page.evaluate("window.browserbaseCaptchaEvents || {}")
                
                if events.get("solved"):
                    logger.info("Browserbase successfully solved CAPTCHA")
                    return True
                
                if events.get("failed"):
                    logger.warning("Browserbase failed to solve CAPTCHA")
                    return False

                # Check if CAPTCHA elements are no longer visible
                if not await self.can_handle(page):
                    logger.info("CAPTCHA no longer detected - likely solved by Browserbase")
                    return True

                # Log progress every 10 seconds
                if attempt % 10 == 0 and attempt > 0:
                    logger.info(f"Still waiting for Browserbase CAPTCHA solving... ({attempt}s)")

            logger.warning("Browserbase CAPTCHA solving timed out after 60 seconds")
            return False

        except Exception as e:
            logger.error(f"Browserbase CAPTCHA solving error: {e}")
            return False

    def get_priority(self) -> int:
        """Get solver priority (higher = preferred)."""
        return self.priority
