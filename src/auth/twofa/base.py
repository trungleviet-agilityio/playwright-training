"""Enhanced base 2FA handler interface with better integration."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from playwright.async_api import Page
from src.models import LoginRequest
import logging

logger = logging.getLogger(__name__)


class TwoFAHandler(ABC):
    """Enhanced abstract base class for 2FA handling implementations."""

    @abstractmethod
    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Handle 2FA authentication."""
        pass

    @abstractmethod
    async def can_handle(self, page: Page) -> bool:
        """Check if this handler can handle the 2FA on the page."""
        pass

    @abstractmethod
    def get_priority(self) -> int:
        """Get handler priority (higher = preferred)."""
        pass

    async def get_2fa_info(self, page: Page) -> Dict[str, Any]:
        """Get information about 2FA on the page."""
        try:
            twofa_info = await page.evaluate(
                """
                () => {
                    const twofaSelectors = [
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
                        'input[autocomplete="one-time-code"]'
                    ];
                    
                    const info = {
                        count: 0,
                        visible: 0,
                        details: []
                    };
                    
                    twofaSelectors.forEach((selector, index) => {
                        const elements = document.querySelectorAll(selector);
                        elements.forEach((el, elIndex) => {
                            const isVisible = el.offsetParent !== null;
                            if (isVisible) info.visible++;
                            
                            info.count++;
                            info.details.push({
                                selector: selector,
                                index: elIndex,
                                visible: isVisible,
                                placeholder: el.placeholder || null,
                                name: el.name || null,
                                id: el.id || null,
                                type: el.type || null,
                                maxlength: el.maxLength || null
                            });
                        });
                    });
                    
                    return info;
                }
            """
            )
            return twofa_info
        except Exception as e:
            logger.error(f"Error getting 2FA info: {e}")
            return {"count": 0, "visible": 0, "details": []}

    async def wait_for_2fa_completion(
        self, page: Page, timeout: int = 120, check_interval: int = 1
    ) -> bool:
        """Wait for 2FA to be completed."""
        import asyncio

        for attempt in range(timeout):
            await asyncio.sleep(check_interval)

            # Check if 2FA is still present
            if not await self.can_handle(page):
                logger.info("2FA completed successfully")
                return True

            if attempt % 30 == 0 and attempt > 0:
                remaining = timeout - attempt
                logger.info(
                    f"Still waiting for 2FA completion... ({remaining}s remaining)"
                )

        logger.warning(f"2FA completion timed out after {timeout} seconds")
        return False

    async def find_2fa_input(self, page: Page) -> Optional[Page]:
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

    async def submit_2fa_form(self, page: Page) -> bool:
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
                    logger.info(f"2FA form submitted using selector: {selector}")
                    return True
            except Exception:
                continue

        # Fallback: press Enter on the input field
        try:
            input_field = await self.find_2fa_input(page)
            if input_field:
                await input_field.press("Enter")
                logger.info("2FA form submitted using Enter key")
                return True
        except Exception:
            pass

        logger.warning("Could not submit 2FA form")
        return False
