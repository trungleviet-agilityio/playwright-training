"""Microsoft 365 authentication strategy."""

import logging
from typing import List
from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import BaseWebAuthStrategy
from src.constants import MICROSOFT_365_URL

logger = logging.getLogger(__name__)


class Microsoft365AuthStrategy(BaseWebAuthStrategy):
    """Microsoft 365 authentication strategy."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.MICROSOFT_365

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Microsoft 365 login."""

        logger.info(f"Logging in to Microsoft 365 with URL: %s", MICROSOFT_365_URL)
        await page.goto(MICROSOFT_365_URL, wait_until="domcontentloaded")

        # Use base class helpers
        await self.fill_credentials(page, request)
        await self.submit_form(page)

        # Wait for potential redirects
        await page.wait_for_timeout(3000)

    async def is_success(self, page: Page) -> bool:
        """Check if Microsoft 365 login was successful."""
        success_indicators = [
            lambda: "office.com" in page.url or "portal.office.com" in page.url,
            lambda: page.query_selector('[data-testid="dashboard"]'),
            lambda: page.query_selector(".ms-nav"),
            lambda: page.get_by_text("Office 365").is_visible(),
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
        """Extract Microsoft 365 session cookies."""
        browser_cookies = await page.context.cookies()

        # Focus on important Microsoft cookies
        important_cookies = {"FedAuth", "rtFa", "ESTSAUTH", "ESTSAUTHPERSISTENT"}

        session_cookies = []
        for cookie in browser_cookies:
            if (
                any(
                    domain in cookie["domain"]
                    for domain in ["microsoft.com", "office.com", "microsoftonline.com"]
                )
                or cookie["name"] in important_cookies
            ):
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

        return (
            session_cookies if session_cookies else await super().extract_cookies(page)
        )
