"""Salesforce authentication strategy."""

import logging
from typing import List

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import SALESFORCE_URL

# Set up logger for this module
logger = logging.getLogger(__name__)


class SalesforceAuthStrategy(AuthStrategy):
    """Salesforce authentication strategy."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.SALESFORCE

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Salesforce login."""
        logger.info(f"Starting Salesforce authentication for email: {request.email}")
        
        logger.info(f"Navigating to Salesforce URL: {SALESFORCE_URL}")
        await page.goto(SALESFORCE_URL, wait_until="domcontentloaded")
        logger.info("Successfully navigated to Salesforce sign-in page")
        
        # Wait for email input
        logger.info("Waiting for email input field...")
        await page.wait_for_selector('input[type="email"]', timeout=10000)
        logger.info("Email input field found")
        
        # Fill email
        logger.info(f"Filling email field with: {request.email}")
        await page.fill('input[type="email"]', request.email)
        logger.info("Email field filled successfully")
        
        # Click continue button
        logger.info("Clicking continue button...")
        await page.click('button[type="submit"]')
        logger.info("Continue button clicked successfully")

        # Wait for password input
        logger.info("Waiting for password input field...")
        await page.wait_for_selector('input[type="password"]', timeout=10000)
        logger.info("Password input field found")

        # Fill password
        logger.info("Filling password field...")
        await page.fill('input[type="password"]', request.password)
        logger.info("Password field filled successfully")

        # Click continue button
        logger.info("Clicking submit button...")
        await page.click('button[type="submit"]')
        logger.info("Submit button clicked successfully")
        logger.info("Salesforce login process completed")

    async def is_success(self, page: Page) -> bool:
        """Check if Salesforce login was successful."""
        logger.info("Checking if Salesforce login was successful...")
        logger.info(f"Current URL: {page.url}")
        
        success = "salesforce.com" in page.url
        if success:
            logger.info("Salesforce URL detected - login successful!")
        else:
            logger.warning("Salesforce URL not detected - login may have failed")
        
        return success

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Salesforce session cookies."""
        logger.info("Extracting Salesforce session cookies...")
        browser_cookies = await page.context.cookies()
        logger.info(f"Found {len(browser_cookies)} total cookies")
        
        session_cookies = []
        for cookie in browser_cookies:
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
        
        logger.info(f"Extracted {len(session_cookies)} cookies")
        return session_cookies
