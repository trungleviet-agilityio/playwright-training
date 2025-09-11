"""Base authentication strategy for OAuth2-based SaaS providers."""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Tuple
from enum import Enum
from playwright.async_api import Page
from src.models import LoginRequest, SessionCookie, AuthProvider, OAuthTokens

logger = logging.getLogger(__name__)


class AuthMethod(str, Enum):
    """Authentication method enumeration."""

    OAUTH2 = "oauth2"


class AuthStrategy(ABC):
    """Base authentication strategy for OAuth2-based SaaS providers."""

    @property
    @abstractmethod
    def provider(self) -> AuthProvider:
        """Return the authentication provider."""
        pass

    @property
    @abstractmethod
    def supported_methods(self) -> List[AuthMethod]:
        """Return list of supported authentication methods."""
        pass

    @property
    @abstractmethod
    def default_method(self) -> AuthMethod:
        """Return the default authentication method."""
        pass

    @abstractmethod
    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform provider-specific login steps."""
        pass

    @abstractmethod
    async def oauth2_login(
        self, page: Page, request: LoginRequest
    ) -> Optional[OAuthTokens]:
        """Perform OAuth2 authentication flow."""
        pass

    def supports_method(self, method: AuthMethod) -> bool:
        """Check if this strategy supports the given authentication method."""
        return method in self.supported_methods

    def get_required_fields(self, method: AuthMethod) -> List[str]:
        """Get required fields for the given authentication method."""
        if method == AuthMethod.OAUTH2:
            return ["email", "otp_secret"]
        return []

    async def is_success(self, page: Page) -> bool:
        """Check if login was successful."""
        error_selectors = [
            "text=Invalid credentials",
            "text=Login failed",
            "text=Incorrect email or password",
            ".error",
            ".alert-error",
        ]
        for selector in error_selectors:
            try:
                if selector.startswith("text="):
                    element = page.get_by_text(selector[5:])
                    if await element.is_visible():
                        return False
                else:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        return False
            except Exception:
                continue
        return True

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract session cookies for the provider."""
        browser_cookies = await page.context.cookies()
        session_cookies = [
            SessionCookie(
                name=c["name"],
                value=c["value"],
                domain=c["domain"],
                path=c.get("path", "/"),
                secure=c.get("secure", False),
                http_only=c.get("httpOnly", False),
            )
            for c in browser_cookies
            if "session" in c["name"].lower()
            or "auth" in c["name"].lower()
            or "token" in c["name"].lower()
        ]
        logger.info(f"Extracted {len(session_cookies)} session cookies")
        return session_cookies

    async def authenticate(
        self, page: Page, request: LoginRequest
    ) -> Tuple[bool, List[SessionCookie], str, Optional[OAuthTokens]]:
        """Main authentication flow for OAuth2."""
        try:
            logger.info(f"Starting OAuth2 authentication for {request.provider}")
            oauth_tokens = await self.oauth2_login(page, request)
            if not oauth_tokens or not oauth_tokens.access_token:
                return False, [], "OAuth2 authentication failed - no valid tokens", None

            success = await self.is_success(page)
            if not success:
                return (
                    False,
                    [],
                    "OAuth2 authentication failed - login unsuccessful",
                    None,
                )

            cookies = await self.extract_cookies(page)
            logger.info(f"Authentication successful for {request.provider}")
            return True, cookies, "OAuth2 authentication successful", oauth_tokens

        except Exception as e:
            logger.error(f"Authentication error for {request.provider}: {str(e)}")
            return False, [], f"OAuth2 authentication error: {str(e)}", None


class OAuth2BaseStrategy(AuthStrategy):
    """Base strategy for OAuth2-enabled providers."""

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.OAUTH2]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.OAUTH2

    async def login(self, page: Page, request: LoginRequest) -> None:
        """OAuth2 providers use oauth2_login instead of traditional login."""
        oauth_tokens = await self.oauth2_login(page, request)
        if not oauth_tokens:
            raise ValueError("OAuth2 login failed")
