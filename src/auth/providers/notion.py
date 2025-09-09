"""Notion authentication strategy."""

from typing import List
from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import BaseWebAuthStrategy


class NotionAuthStrategy(BaseWebAuthStrategy):
    """Notion authentication strategy."""
    
    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.NOTION
    
    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Notion login."""
        await page.goto("https://www.notion.so/auth/login", wait_until="domcontentloaded")
        
        # Use base class helpers
        await self.fill_credentials(page, request)
        await self.submit_form(page)
        
        # Wait for potential redirects
        await page.wait_for_timeout(3000)
    
    async def is_success(self, page: Page) -> bool:
        """Check if Notion login was successful."""
        success_indicators = [
            lambda: "notion.so" in page.url and "login" not in page.url,
            lambda: page.query_selector('[data-testid="dashboard"]'),
            lambda: page.query_selector('.notion-app'),
            lambda: page.get_by_text("workspace").is_visible(),
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
        """Extract Notion session cookies."""
        browser_cookies = await page.context.cookies()
        
        # Focus on important Notion cookies
        important_cookies = {"token_v2", "file_token", "notion_user_id"}
        
        session_cookies = []
        for cookie in browser_cookies:
            if "notion.so" in cookie["domain"] or cookie["name"] in important_cookies:
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
