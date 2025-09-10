"""Base classes for authentication strategies."""

import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
from playwright.async_api import Page
from src.models import LoginRequest, SessionCookie, AuthProvider, OAuthTokens

logger = logging.getLogger(__name__)


class AuthStrategy(ABC):
    """Simplified base authentication strategy."""

    @property
    @abstractmethod
    def provider(self) -> AuthProvider:
        """Return the authentication provider."""
        pass

    @abstractmethod
    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform provider-specific login steps."""
        pass

    async def is_success(self, page: Page) -> bool:
        """Check if login was successful. Override for provider-specific logic."""
        # Simple default: check for common error indicators
        error_selectors = [
            "text=Invalid credentials",
            "text=Login failed", 
            "text=Incorrect email or password",
            ".error",
            ".alert-error"
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

        # If no errors found, assume success
        return True

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract session cookies. Override for provider-specific filtering."""
        browser_cookies = await page.context.cookies()
        
        session_cookies = []
        for cookie in browser_cookies:
            # Include cookies that look like session cookies
            if any(keyword in cookie["name"].lower() for keyword in ["session", "auth", "token", "sid"]):
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

        # If no session cookies found, include all cookies from current domain
        if not session_cookies:
            current_domain = page.url.split("//")[1].split("/")[0]
            for cookie in browser_cookies:
                if current_domain in cookie["domain"]:
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

        return session_cookies

    async def handle_captcha(self, page: Page) -> bool:
        """Handle CAPTCHA if present. Override for provider-specific logic."""
        # Simple default: assume no CAPTCHA or it's handled automatically
        return True

    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Handle 2FA if required. Override for provider-specific logic."""
        # Simple default: assume no 2FA or it's handled automatically
        return True

    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Perform OAuth2 authentication. Override in provider-specific strategies."""
        logger.info("OAuth2 login not implemented for this provider")
        return None

    async def extract_oauth_tokens(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Extract OAuth tokens from the page. Override in provider-specific strategies."""
        logger.info("OAuth token extraction not implemented for this provider")
        return None

    async def authenticate(self, page: Page, request: LoginRequest) -> Tuple[bool, List[SessionCookie], str, Optional[OAuthTokens]]:
        """Main authentication flow with OAuth2 support."""
        try:
            # Step 1: Perform login based on auth mode
            if request.auth_mode == "oauth2":
                oauth_tokens = await self.oauth2_login(page, request)
                if not oauth_tokens:
                    return False, [], "OAuth2 authentication failed", None
                return True, [], "OAuth2 authentication successful", oauth_tokens
            
            elif request.auth_mode == "hybrid":
                # Try OAuth2 first, fallback to password
                oauth_tokens = await self.oauth2_login(page, request)
                if oauth_tokens:
                    return True, [], "Hybrid OAuth2 authentication successful", oauth_tokens
                # Fallback to password authentication
                logger.info("OAuth2 failed, falling back to password authentication")

            # Step 2: Perform password login
            await self.login(page, request)

            # Step 3: Handle CAPTCHA
            if not await self.handle_captcha(page):
                return False, [], "CAPTCHA could not be solved", None

            # Step 4: Handle 2FA
            if not await self.handle_2fa(page, request):
                return False, [], "2FA could not be completed", None

            # Step 5: Check success
            if not await self.is_success(page):
                return False, [], "Login failed - invalid credentials or other error", None

            # Step 6: Extract cookies
            cookies = await self.extract_cookies(page)
            if not cookies:
                return False, [], "No valid session cookies found", None

            # Step 7: Try to extract OAuth tokens if available
            oauth_tokens = await self.extract_oauth_tokens(page, request)

            return True, cookies, "Login successful", oauth_tokens

        except Exception as e:
            return False, [], f"Authentication error: {str(e)}", None


class BaseWebAuthStrategy(AuthStrategy):
    """Base strategy for web-based authentication with common patterns."""

    async def fill_credentials(self, page: Page, request: LoginRequest) -> None:
        """Fill email and password with common selectors."""
        # Fill email
        email_selectors = [
            'input[type="email"]',
            'input[name="email"]',
            'input[name="username"]',
            'input[name="login"]',
        ]

        for selector in email_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await page.fill(selector, request.email)
                    break
            except Exception:
                continue

        # Fill password if provided
        if request.password:
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
            ]

            for selector in password_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await page.fill(selector, request.password)
                        break
                except Exception:
                    continue

    async def submit_form(self, page: Page) -> None:
        """Submit form with common selectors."""
        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Sign In")',
            'button:has-text("Login")',
            'button:has-text("Continue")',
        ]

        for selector in submit_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    await element.click()
                    return
            except Exception:
                continue

        # Fallback: press Enter on password field
        try:
            await page.press('input[type="password"]', "Enter")
        except Exception:
            pass
