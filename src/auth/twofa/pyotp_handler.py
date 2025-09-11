"""PyOTP-based 2FA handler for GitHub, Okta, etc."""

import logging
import asyncio
from typing import Optional
from playwright.async_api import Page
import pyotp

from .base import TwoFAHandler
from src.models import LoginRequest

logger = logging.getLogger(__name__)


class PyOTPHandler(TwoFAHandler):
    """2FA handler using PyOTP for OTP generation."""

    def __init__(self):
        self.priority = 100  # High priority when available

    async def can_handle(self, page: Page) -> bool:
        """Check if 2FA is present and we can handle it."""
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
                        logger.info(f"2FA input detected with selector: {selector}")
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
                        logger.info(f"2FA text detected: {text}")
                        return True
                except Exception:
                    continue

            return False

        except Exception as e:
            logger.error(f"Error checking for 2FA: {e}")
            return False

    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Handle 2FA using PyOTP."""
        if not await self.can_handle(page):
            logger.info("No 2FA detected, skipping")
            return True

        logger.info("2FA detected, attempting to generate OTP...")

        # Check if we have a TOTP secret in the request
        if not hasattr(request, 'totp_secret') or not request.totp_secret:
            logger.warning("No TOTP secret provided in request")
            return False

        try:
            # Generate TOTP code
            totp = pyotp.TOTP(request.totp_secret)
            otp_code = totp.now()
            logger.info(f"Generated OTP code: {otp_code}")

            # Find 2FA input field
            twofa_input = await self._find_2fa_input(page)
            if not twofa_input:
                logger.error("Could not find 2FA input field")
                return False

            # Fill the OTP code
            await twofa_input.fill(otp_code)
            logger.info("OTP code filled successfully")

            # Submit the form
            await self._submit_2fa_form(page)
            logger.info("2FA form submitted")

            # Wait for processing
            await page.wait_for_timeout(3000)

            # Check if 2FA was successful
            if not await self.can_handle(page):
                logger.info("2FA completed successfully")
                return True
            else:
                logger.warning("2FA still present after submission")
                return False

        except Exception as e:
            logger.error(f"2FA handling failed: {e}")
            return False

    async def _find_2fa_input(self, page: Page) -> Optional[Page]:
        """Find the 2FA input field."""
        selectors = [
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

        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return element
            except Exception:
                continue

        return None

    async def _submit_2fa_form(self, page: Page) -> None:
        """Submit the 2FA form."""
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Verify")',
            'button:has-text("Submit")',
            'button:has-text("Continue")',
            'button:has-text("Confirm")',
            'button[data-qa*="submit"]',
            'button[data-qa*="verify"]',
            'button[data-qa*="confirm"]',
        ]

        for selector in submit_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    return
            except Exception:
                continue

        # Fallback: press Enter on the input field
        try:
            input_field = await self._find_2fa_input(page)
            if input_field:
                await input_field.press("Enter")
        except Exception:
            pass

    def get_priority(self) -> int:
        """Get handler priority (higher = preferred)."""
        return self.priority
