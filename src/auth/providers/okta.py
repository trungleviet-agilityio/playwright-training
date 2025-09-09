"""Okta authentication strategy."""

from typing import List
from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import BaseWebAuthStrategy
from src.constants import OKTA_URL


class OktaAuthStrategy(BaseWebAuthStrategy):
    """Okta authentication strategy."""
    
    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.OKTA
    
    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Okta login."""
        await page.goto(OKTA_URL, wait_until="domcontentloaded") 
        
        # Use base class helpers
        await self.fill_credentials(page, request)
        await self.submit_form(page)
        
        # Wait for potential redirects
        await page.wait_for_timeout(3000)
    
    async def is_success(self, page: Page) -> bool:
        """Check if Okta login was successful."""
        success_indicators = [
            lambda: "okta.com" in page.url and "login" not in page.url,
            lambda: page.query_selector('[data-se="dashboard"]'),
            lambda: page.query_selector('.dashboard'),
            lambda: page.get_by_text("Applications").is_visible(),
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
        """Extract Okta session cookies."""
        browser_cookies = await page.context.cookies()
        
        # Focus on important Okta cookies
        important_cookies = {"sid", "DT", "JSESSIONID", "oktaStateToken"}
        
        session_cookies = []
        for cookie in browser_cookies:
            if "okta.com" in cookie["domain"] or cookie["name"] in important_cookies:
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
