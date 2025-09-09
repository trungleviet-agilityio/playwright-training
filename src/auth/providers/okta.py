"""Okta authentication strategy."""

import logging
from typing import List
from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import BaseWebAuthStrategy
from src.constants import OKTA_URL

# Set up logger for this module
logger = logging.getLogger(__name__)


class OktaAuthStrategy(BaseWebAuthStrategy):
    """Okta authentication strategy."""
    
    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.OKTA
    
    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Okta login."""
        logger.info(f"Starting Okta authentication for email: {request.email}")
        
        logger.info(f"Navigating to Okta URL: {OKTA_URL}")
        await page.goto(OKTA_URL, wait_until="domcontentloaded")
        logger.info("Successfully navigated to Okta sign-in page")
        
        # Use base class helpers
        logger.info("Filling credentials using base class helper...")
        await self.fill_credentials(page, request)
        logger.info("Credentials filled successfully")
        
        logger.info("Submitting form using base class helper...")
        await self.submit_form(page)
        logger.info("Form submitted successfully")
        
        # Wait for potential redirects
        logger.info("Waiting for potential redirects...")
        await page.wait_for_timeout(3000)
        logger.info("Okta login process completed")
    
    async def is_success(self, page: Page) -> bool:
        """Check if Okta login was successful."""
        logger.info("Checking if Okta login was successful...")
        logger.info(f"Current URL: {page.url}")
        
        success_indicators = [
            lambda: "okta.com" in page.url and "login" not in page.url,
            lambda: page.query_selector('[data-se="dashboard"]'),
            lambda: page.query_selector('.dashboard'),
            lambda: page.get_by_text("Applications").is_visible(),
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
        
        logger.info("No custom success indicators matched, trying base class method...")
        return await super().is_success(page)
    
    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Okta session cookies."""
        logger.info("Extracting Okta session cookies...")
        browser_cookies = await page.context.cookies()
        logger.info(f"Found {len(browser_cookies)} total cookies")
        
        # Focus on important Okta cookies
        important_cookies = {"sid", "DT", "JSESSIONID", "oktaStateToken"}
        
        session_cookies = []
        for cookie in browser_cookies:
            if "okta.com" in cookie["domain"] or cookie["name"] in important_cookies:
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
        return session_cookies if session_cookies else await super().extract_cookies(page)
