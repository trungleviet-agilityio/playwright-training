"""Salesforce authentication strategy."""

from typing import List

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import SALESFORCE_URL


class SalesforceAuthStrategy(AuthStrategy):
    """Salesforce authentication strategy."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.SALESFORCE

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Salesforce login."""
        await page.goto(SALESFORCE_URL, wait_until="domcontentloaded")
        
        # Wait for email input
        await page.wait_for_selector('input[type="email"]', timeout=10000)
        
        # Fill email
        await page.fill('input[type="email"]', request.email)
        
        # Click continue button
        await page.click('button[type="submit"]')

        # Wait for password input
        await page.wait_for_selector('input[type="password"]', timeout=10000)

        # Fill password
        await page.fill('input[type="password"]', request.password)

        # Click continue button
        await page.click('button[type="submit"]')

    async def is_success(self, page: Page) -> bool:
        """Check if Salesforce login was successful."""
        return "salesforce.com" in page.url

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Salesforce session cookies."""
        return await page.context.cookies()
