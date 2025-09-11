"""Base classes for authentication strategies."""

import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
from playwright.async_api import Page
from src.models import LoginRequest, SessionCookie, AuthProvider, OAuthTokens

logger = logging.getLogger(__name__)


class AuthMethod(str, Enum):
    """Authentication method enumeration."""
    PASSWORD = "password"
    OAUTH2 = "oauth2"
    HYBRID = "hybrid"  # Supports both password and OAuth2
    SSO = "sso"  # Single Sign-On
    API_KEY = "api_key"


class AuthStrategy(ABC):
    """Base authentication strategy for SaaS providers."""

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

    def supports_method(self, method: AuthMethod) -> bool:
        """Check if this strategy supports the given authentication method."""
        return method in self.supported_methods

    def get_required_fields(self, method: AuthMethod) -> List[str]:
        """Get required fields for the given authentication method."""
        if method == AuthMethod.PASSWORD:
            return ["email", "password"]
        elif method == AuthMethod.OAUTH2:
            return ["client_id", "client_secret", "redirect_uri"]
        elif method == AuthMethod.API_KEY:
            return ["api_key"]
        else:
            return ["email"]

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


class OAuth2BaseStrategy(AuthStrategy):
    """Base strategy for OAuth2-enabled providers."""

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.OAUTH2]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.OAUTH2

    @abstractmethod
    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Perform OAuth2 authentication flow."""
        pass

    async def login(self, page: Page, request: LoginRequest) -> None:
        """OAuth2 providers don't use traditional login."""
        raise NotImplementedError("Use oauth2_login method for OAuth2 authentication")

    async def authenticate(self, page: Page, request: LoginRequest) -> Tuple[bool, List[SessionCookie], str, Optional[OAuthTokens]]:
        """OAuth2 authentication flow with enhanced error handling."""
        try:
            # Validate required OAuth2 fields
            required_fields = self.get_required_fields(AuthMethod.OAUTH2)
            missing_fields = []
            for field in required_fields:
                if not getattr(request, field, None):
                    missing_fields.append(field)
            
            if missing_fields:
                error_msg = f"Missing required OAuth2 fields: {', '.join(missing_fields)}"
                logger.error(error_msg)
                return False, [], error_msg, None
            
            # Perform OAuth2 login
            oauth_tokens = await self.oauth2_login(page, request)
            if oauth_tokens and oauth_tokens.access_token:
                logger.info("OAuth2 authentication successful")
                return True, [], "OAuth2 authentication successful", oauth_tokens
            else:
                error_msg = "OAuth2 authentication failed - no valid tokens received"
                logger.error(error_msg)
                return False, [], error_msg, None
        except Exception as e:
            error_msg = f"OAuth2 authentication error: {str(e)}"
            logger.error(error_msg)
            return False, [], error_msg, None


class PasswordBaseStrategy(AuthStrategy):
    """Base strategy for password-based authentication."""

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.PASSWORD]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.PASSWORD

    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Password-based providers don't support OAuth2."""
        logger.info("OAuth2 not supported for password-based authentication")
        return None

    async def authenticate(self, page: Page, request: LoginRequest) -> Tuple[bool, List[SessionCookie], str, Optional[OAuthTokens]]:
        """Password authentication flow."""
        try:
            # Perform password login
            await self.login(page, request)

            # Handle CAPTCHA
            if not await self.handle_captcha(page):
                return False, [], "CAPTCHA could not be solved", None

            # Handle 2FA
            if not await self.handle_2fa(page, request):
                return False, [], "2FA could not be completed", None

            # Check success
            if not await self.is_success(page):
                return False, [], "Login failed - invalid credentials or other error", None

            # Extract cookies
            cookies = await self.extract_cookies(page)
            if not cookies:
                return False, [], "No valid session cookies found", None

            return True, cookies, "Password authentication successful", None

        except Exception as e:
            return False, [], f"Password authentication error: {str(e)}", None


class HybridBaseStrategy(AuthStrategy):
    """Base strategy for providers supporting both password and OAuth2."""

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.PASSWORD, AuthMethod.OAUTH2, AuthMethod.HYBRID]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.HYBRID

    @abstractmethod
    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Perform OAuth2 authentication flow."""
        pass

    async def authenticate(self, page: Page, request: LoginRequest) -> Tuple[bool, List[SessionCookie], str, Optional[OAuthTokens]]:
        """Hybrid authentication flow - try OAuth2 first, fallback to password."""
        try:
            # Determine authentication method
            auth_method = AuthMethod(request.auth_mode) if request.auth_mode else self.default_method

            if auth_method in [AuthMethod.OAUTH2, AuthMethod.HYBRID]:
                # Try OAuth2 first
                oauth_tokens = await self.oauth2_login(page, request)
                if oauth_tokens:
                    return True, [], "OAuth2 authentication successful", oauth_tokens

                if auth_method == AuthMethod.OAUTH2:
                    return False, [], "OAuth2 authentication failed", None
                
                # Fallback to password for hybrid mode
                logger.info("OAuth2 failed, falling back to password authentication")

            # Password authentication
            await self.login(page, request)

            # Handle CAPTCHA
            if not await self.handle_captcha(page):
                return False, [], "CAPTCHA could not be solved", None

            # Handle 2FA
            if not await self.handle_2fa(page, request):
                return False, [], "2FA could not be completed", None

            # Check success
            if not await self.is_success(page):
                return False, [], "Login failed - invalid credentials or other error", None

            # Extract cookies
            cookies = await self.extract_cookies(page)
            if not cookies:
                return False, [], "No valid session cookies found", None

            return True, cookies, "Password authentication successful", None

        except Exception as e:
            return False, [], f"Hybrid authentication error: {str(e)}", None


class SSOBaseStrategy(AuthStrategy):
    """Base strategy for Single Sign-On providers."""

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.SSO]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.SSO

    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """SSO providers typically use OAuth2 under the hood."""
        return await self.sso_login(page, request)

    @abstractmethod
    async def sso_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Perform SSO authentication."""
        pass

    async def login(self, page: Page, request: LoginRequest) -> None:
        """SSO providers don't use traditional login."""
        raise NotImplementedError("Use sso_login method for SSO authentication")


class APIKeyBaseStrategy(AuthStrategy):
    """Base strategy for API key-based authentication."""

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.API_KEY]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.API_KEY

    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """API key providers don't support OAuth2."""
        logger.info("OAuth2 not supported for API key authentication")
        return None

    @abstractmethod
    async def api_key_login(self, request: LoginRequest) -> Optional[OAuthTokens]:
        """Perform API key authentication."""
        pass

    async def login(self, page: Page, request: LoginRequest) -> None:
        """API key providers don't use browser-based login."""
        raise NotImplementedError("Use api_key_login method for API key authentication")

    async def authenticate(self, page: Page, request: LoginRequest) -> Tuple[bool, List[SessionCookie], str, Optional[OAuthTokens]]:
        """API key authentication flow."""
        try:
            oauth_tokens = await self.api_key_login(request)
            if oauth_tokens:
                return True, [], "API key authentication successful", oauth_tokens
            else:
                return False, [], "API key authentication failed", None
        except Exception as e:
            return False, [], f"API key authentication error: {str(e)}", None
