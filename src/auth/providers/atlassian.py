"""Atlassian authentication strategy."""

from typing import List
from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import BaseWebAuthStrategy
from src.constants import ATLASSIAN_URL


class AtlassianAuthStrategy(BaseWebAuthStrategy):
    """Atlassian authentication strategy."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.ATLASSIAN

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Atlassian login."""
        await page.goto(ATLASSIAN_URL, wait_until="domcontentloaded")

        # Use base class helpers
        await self.fill_credentials(page, request)
        await self.submit_form(page)
        
        # Wait for potential redirects
        await page.wait_for_timeout(3000)
    
    async def is_success(self, page: Page) -> bool:
        """Check if Atlassian login was successful."""
        success_indicators = [
            lambda: "atlassian.com" in page.url and "login" not in page.url,
            lambda: page.query_selector('[data-testid="navigation"]'),
            lambda: page.query_selector('.atlaskit-navigation'),
            lambda: page.get_by_text("Products").is_visible(),
        ]
        
        for indicator in success_indicators:
            try:
                result = await indicator()
                if result:
                    return True
            except Exception:
                continue
        
        return await super().is_success(page)
    
    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Atlassian session cookies."""
        browser_cookies = await page.context.cookies()
        
        # Focus on important Atlassian cookies
        important_cookies = {"JSESSIONID", "AWSALB", "atlassian_account_id"}
        
        session_cookies = []
        for cookie in browser_cookies:
            if "atlassian.com" in cookie["domain"] or cookie["name"] in important_cookies:
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
        
        return session_cookies if session_cookies else await super().extract_cookies(page)
