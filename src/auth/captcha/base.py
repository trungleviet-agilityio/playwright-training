"""Enhanced base classes for CAPTCHA solving with better integration."""

from abc import ABC, abstractmethod
from playwright.async_api import Page
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class CaptchaSolver(ABC):
    """Enhanced abstract CAPTCHA solver interface."""

    @abstractmethod
    async def can_handle(self, page: Page) -> bool:
        """Check if this solver can handle the CAPTCHA on the page."""
        pass

    @abstractmethod
    async def solve(self, page: Page) -> bool:
        """Solve the CAPTCHA on the page."""
        pass

    @abstractmethod
    def get_priority(self) -> int:
        """Get solver priority (higher = preferred)."""
        pass

    async def get_captcha_info(self, page: Page) -> Dict[str, Any]:
        """Get information about the CAPTCHA on the page."""
        try:
            captcha_info = await page.evaluate(
                """
                () => {
                    const captchaElements = document.querySelectorAll(
                        'iframe[src*="recaptcha"], .g-recaptcha, .h-captcha, [data-sitekey], [data-hcaptcha-sitekey]'
                    );
                    
                    const info = {
                        count: captchaElements.length,
                        types: [],
                        visible: 0,
                        details: []
                    };
                    
                    captchaElements.forEach((el, index) => {
                        const isVisible = el.offsetParent !== null;
                        if (isVisible) info.visible++;
                        
                        let type = 'unknown';
                        if (el.src && el.src.includes('recaptcha')) type = 'recaptcha';
                        else if (el.classList.contains('g-recaptcha')) type = 'recaptcha';
                        else if (el.classList.contains('h-captcha')) type = 'hcaptcha';
                        else if (el.hasAttribute('data-sitekey')) type = 'recaptcha';
                        else if (el.hasAttribute('data-hcaptcha-sitekey')) type = 'hcaptcha';
                        
                        info.types.push(type);
                        info.details.push({
                            index: index,
                            type: type,
                            visible: isVisible,
                            src: el.src || null,
                            sitekey: el.getAttribute('data-sitekey') || el.getAttribute('data-hcaptcha-sitekey') || null
                        });
                    });
                    
                    return info;
                }
            """
            )
            return captcha_info
        except Exception as e:
            logger.error(f"Error getting CAPTCHA info: {e}")
            return {"count": 0, "types": [], "visible": 0, "details": []}

    async def wait_for_captcha_completion(
        self, page: Page, timeout: int = 30, check_interval: int = 1
    ) -> bool:
        """Wait for CAPTCHA to be completed."""
        import asyncio

        for attempt in range(timeout):
            await asyncio.sleep(check_interval)

            # Check if CAPTCHA is still present
            if not await self.can_handle(page):
                logger.info("CAPTCHA completed successfully")
                return True

            if attempt % 10 == 0 and attempt > 0:
                logger.info(f"Still waiting for CAPTCHA completion... ({attempt}s)")

        logger.warning(f"CAPTCHA completion timed out after {timeout} seconds")
        return False

    async def take_debug_screenshot(
        self, page: Page, stage: str, description: str = ""
    ) -> Optional[str]:
        """Take a debug screenshot."""
        try:
            import os
            from datetime import datetime

            debug_dir = "captcha_debug"
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            filename = f"{timestamp}_{stage}.png"
            filepath = os.path.join(debug_dir, filename)

            await page.screenshot(path=filepath, full_page=True)
            logger.info(f"Debug screenshot saved: {filepath}")
            if description:
                logger.info(f"Screenshot description: {description}")

            return filepath
        except Exception as e:
            logger.error(f"Failed to take debug screenshot: {e}")
            return None
