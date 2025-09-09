"""Google authentication strategy."""

import logging
from typing import List

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import GOOGLE_URL

# Set up logger for this module
logger = logging.getLogger(__name__)


class GoogleAuthStrategy(AuthStrategy):
    """Google authentication strategy with enhanced stealth."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.GOOGLE

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Google login with enhanced anti-detection."""
        logger.info(f"Starting Google authentication for email: {request.email}")
        
        # Navigate to Google sign-in
        logger.info(f"Navigating to Google URL: {GOOGLE_URL}")
        await page.goto(GOOGLE_URL, wait_until="domcontentloaded")
        logger.info("Successfully navigated to Google sign-in page")

        # Wait for email input
        logger.info("Waiting for email input field...")
        await page.wait_for_selector('input[type="email"]', timeout=10000)
        logger.info("Email input field found")

        # Fill email with human-like typing
        logger.info(f"Filling email field with: {request.email}")
        await page.fill('input[type="email"]', request.email)
        await page.wait_for_timeout(500)
        logger.info("Email field filled successfully")

        # Click Next button
        logger.info("Looking for Next button...")
        next_button = await page.query_selector(
            'button:has-text("Next"), #identifierNext'
        )
        if next_button:
            logger.info("Next button found, clicking...")
            await next_button.click()
            logger.info("Next button clicked successfully")
        else:
            logger.info("No Next button found, using Enter key")
            await page.press('input[type="email"]', "Enter")

        # Wait and check for security warnings
        logger.info("Waiting for potential security warnings...")
        await page.wait_for_timeout(2000)

        # Handle "Couldn't sign you in" warning
        try:
            if await page.get_by_text("Couldn't sign you in").is_visible():
                logger.warning("Google security warning detected!")
                try_again_link = await page.query_selector('a:has-text("Try again")')
                if try_again_link:
                    logger.info("Found 'Try again' link, clicking...")
                    await try_again_link.click()
                    await page.wait_for_timeout(3000)
                    logger.info("'Try again' link clicked successfully")
                else:
                    logger.warning("Could not find 'Try again' link")
        except Exception as e:
            logger.info(f"No security warning detected: {e}")

        # Wait for password field
        logger.info("Waiting for password input field...")
        await page.wait_for_selector('input[type="password"]', timeout=30000)
        logger.info("Password input field found")

        if not request.password:
            logger.error("Password is required for Google login")
            raise ValueError("Password is required for Google login")

        # Fill password
        logger.info("Filling password field...")
        await page.fill('input[type="password"]', request.password)
        await page.wait_for_timeout(500)
        logger.info("Password field filled successfully")

        # Submit password
        logger.info("Looking for password submit button...")
        password_next = await page.query_selector(
            'button:has-text("Next"), #passwordNext'
        )
        if password_next:
            logger.info("Password submit button found, clicking...")
            await password_next.click()
            logger.info("Password submit button clicked successfully")
        else:
            logger.info("No password submit button found, using Enter key")
            await page.press('input[type="password"]', "Enter")

        # Wait for potential redirects or additional verification
        logger.info("Waiting for potential redirects or additional verification...")
        await page.wait_for_timeout(5000)
        logger.info("Google login process completed")

    async def is_success(self, page: Page) -> bool:
        """Check if Google login was successful."""
        logger.info("Checking if Google login was successful...")
        logger.info(f"Current URL: {page.url}")
        
        success_indicators = [
            # Google account page
            lambda: "myaccount.google.com" in page.url,
            # Google services page
            lambda: page.query_selector('[data-g-label="Account"]'),
            lambda: page.query_selector(".gb_A"),  # Google apps menu
            # Profile elements
            lambda: page.query_selector('[aria-label*="Google Account"]'),
            lambda: page.get_by_text("Welcome").is_visible(),
        ]

        for i, indicator in enumerate(success_indicators):
            try:
                logger.info(f"Testing success indicator {i+1}/{len(success_indicators)}")
                result = await indicator()
                if result:
                    logger.info(f"Success indicator {i+1} matched! Login successful.")
                    return True
                else:
                    logger.info(f"Success indicator {i+1} did not match")
            except Exception as e:
                logger.info(f"Success indicator {i+1} failed with error: {e}")
                continue

        logger.warning("No success indicators matched. Login may have failed.")
        return False

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Google session cookies."""
        logger.info("Extracting Google session cookies...")
        browser_cookies = await page.context.cookies()
        logger.info(f"Found {len(browser_cookies)} total cookies")

        # Focus on important Google cookies
        important_cookies = {
            "SID",
            "HSID",
            "SSID",
            "SAPISID",
            "APISID",
            "session_state",
        }

        session_cookies = []
        for cookie in browser_cookies:
            # Include all google.com cookies and important ones
            if "google.com" in cookie["domain"] or cookie["name"] in important_cookies:
                logger.info(f"Extracting cookie: {cookie['name']} from {cookie['domain']}")
                session_cookies.append(
                    SessionCookie(
                        name=cookie["name"],
                        value=cookie["value"],
                        domain=cookie["domain"],
                        path=cookie.get("path", "/"),
                        secure=cookie.get("secure", False),
                        http_only=cookie.get("httpOnly", False),
                    )
                )

        logger.info(f"Extracted {len(session_cookies)} relevant cookies")
        return session_cookies
