"""Base classes for authentication strategies."""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import List, Tuple, Protocol, Optional
from playwright.async_api import Page
from src.models import LoginRequest, SessionCookie, AuthProvider, OAuthTokens

logger = logging.getLogger(__name__)


class CaptchaSolver(Protocol):
    """Protocol for CAPTCHA solving implementations."""

    async def can_handle(self, page: Page) -> bool: ...
    async def solve(self, page: Page) -> bool: ...
    def get_priority(self) -> int: ...


class TwoFAStrategy(Protocol):
    """Protocol for 2FA handling implementations."""

    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool: ...


class AuthStrategy(ABC):
    """Base authentication strategy with pluggable CAPTCHA and 2FA support."""

    def __init__(
        self,
        captcha_solver: Optional[CaptchaSolver] = None,
        twofa_strategy: Optional[TwoFAStrategy] = None,
    ) -> None:
        # Import here to avoid circular imports
        from src.auth.captcha.solvers import ManualCaptchaSolver
        from src.auth.twofa import ManualTwoFAHandler

        self.captcha_solver = captcha_solver or ManualCaptchaSolver()
        self.twofa_strategy = twofa_strategy or ManualTwoFAHandler()

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
        # Default implementation: check for common error indicators
        error_indicators = [
            "text=Invalid credentials",
            "text=Login failed",
            "text=Incorrect email or password",
            "text=Authentication failed",
            '[data-testid*="error"]',
            ".error",
            ".alert-error",
        ]

        for selector in error_indicators:
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
            # Default: include all cookies that look like session cookies
            if any(
                keyword in cookie["name"].lower()
                for keyword in ["session", "auth", "token", "sid"]
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

        # If no session cookies found, include all cookies from the current domain
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
        """Handle CAPTCHA if present."""
        return await self.captcha_solver.solve(page)

    async def setup_browserbase_integration(self, page: Page) -> None:
        """Set up Browserbase-specific integrations if using Browserbase provider."""
        try:
            # Check if we're using Browserbase by checking the current provider
            from src.config import settings

            if settings.browser_provider == "browserbase":
                logger.info("Browserbase provider detected, setting up integration...")
                await self._setup_browserbase_captcha_listeners(page)
            else:
                logger.debug(
                    "Not using Browserbase provider, skipping integration setup"
                )
        except Exception as e:
            logger.debug(f"Browserbase integration setup failed: {e}")

    async def _setup_browserbase_captcha_listeners(self, page: Page) -> None:
        """Set up Browserbase CAPTCHA event listeners."""
        await page.evaluate(
            """
            window.addEventListener('browserbase-captcha-detected', (event) => {
                console.log('Browserbase: CAPTCHA detected', event.detail);
            });
            
            window.addEventListener('browserbase-captcha-solved', (event) => {
                console.log('Browserbase: CAPTCHA solved', event.detail);
            });
            
            window.addEventListener('browserbase-captcha-failed', (event) => {
                console.log('Browserbase: CAPTCHA solving failed', event.detail);
            });
        """
        )

    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Handle 2FA if required."""
        return await self.twofa_strategy.handle_2fa(page, request)

    async def oauth2_login(
        self, page: Page, request: LoginRequest
    ) -> Optional[OAuthTokens]:
        """Perform OAuth2 authentication. Override in provider-specific strategies."""
        logger.info("OAuth2 login not implemented for this provider")
        return None

    async def extract_oauth_tokens(
        self, page: Page, request: LoginRequest
    ) -> Optional[OAuthTokens]:
        """Extract OAuth tokens from the page. Override in provider-specific strategies."""
        logger.info("OAuth token extraction not implemented for this provider")
        return None

    async def authenticate(
        self, page: Page, request: LoginRequest
    ) -> Tuple[bool, List[SessionCookie], str, Optional[OAuthTokens]]:
        """Main authentication flow with OAuth2 support."""
        try:
            # Step 0: Set up Browserbase integration if applicable
            await self.setup_browserbase_integration(page)

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
                    return (
                        True,
                        [],
                        "Hybrid OAuth2 authentication successful",
                        oauth_tokens,
                    )
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
                return (
                    False,
                    [],
                    "Login failed - invalid credentials or other error",
                    None,
                )

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
            'input[placeholder*="email"]',
            'input[placeholder*="Email"]',
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
                'input[placeholder*="password"]',
                'input[placeholder*="Password"]',
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
            'button:has-text("Submit")',
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


class OAuth2AuthStrategy(AuthStrategy):
    """Base strategy for OAuth2-based authentication."""

    def __init__(self):
        super().__init__()
        self.oauth_helper = None  # Will be set by subclasses

    async def oauth2_login(
        self, page: Page, request: LoginRequest
    ) -> Optional[OAuthTokens]:
        """Perform OAuth2 authentication flow."""
        if not request.client_id or not request.redirect_uri:
            logger.error(
                "OAuth2 configuration missing: client_id and redirect_uri required"
            )
            return None

        try:
            # Step 1: Navigate to OAuth2 authorization URL
            auth_url = await self._build_authorization_url(request)
            logger.info(f"Navigating to OAuth2 authorization URL: {auth_url}")
            await page.goto(auth_url, wait_until="domcontentloaded")

            # Step 2: Handle user consent (if required)
            await self._handle_consent(page, request)

            # Step 3: Wait for redirect to callback URL
            callback_url = await self._wait_for_callback(page, request.redirect_uri)

            # Step 4: Extract authorization code
            auth_code = self._extract_auth_code(callback_url)
            if not auth_code:
                logger.error("Failed to extract authorization code from callback URL")
                return None

            # Step 5: Exchange code for tokens
            tokens = await self._exchange_code_for_tokens(auth_code, request)
            if not tokens:
                logger.error("Failed to exchange authorization code for tokens")
                return None

            logger.info("OAuth2 authentication successful")
            return tokens

        except Exception as e:
            logger.error(f"OAuth2 authentication failed: {e}")
            return None

    async def _build_authorization_url(self, request: LoginRequest) -> str:
        """Build OAuth2 authorization URL. Override in provider-specific strategies."""
        raise NotImplementedError("Subclasses must implement _build_authorization_url")

    async def _handle_consent(self, page: Page, request: LoginRequest) -> None:
        """Handle user consent page. Override in provider-specific strategies."""
        # Default implementation - wait for redirect
        await page.wait_for_timeout(2000)

    async def _wait_for_callback(self, page: Page, redirect_uri: str) -> str:
        """Wait for redirect to callback URL."""
        logger.info(f"Waiting for redirect to: {redirect_uri}")

        # Wait for URL to contain redirect_uri
        await page.wait_for_function(
            f"window.location.href.startsWith('{redirect_uri}')",
            timeout=60000,  # 60 seconds timeout
        )

        callback_url = page.url
        logger.info(f"Redirected to callback URL: {callback_url}")
        return callback_url

    def _extract_auth_code(self, callback_url: str) -> Optional[str]:
        """Extract authorization code from callback URL."""
        from urllib.parse import urlparse, parse_qs

        try:
            parsed_url = urlparse(callback_url)
            query_params = parse_qs(parsed_url.query)

            # Check for 'code' parameter
            if "code" in query_params:
                return query_params["code"][0]

            # Check for 'error' parameter
            if "error" in query_params:
                error = query_params["error"][0]
                logger.error(f"OAuth2 error in callback: {error}")
                return None

            logger.error("No authorization code found in callback URL")
            return None

        except Exception as e:
            logger.error(f"Error extracting auth code from URL: {e}")
            return None

    async def _exchange_code_for_tokens(
        self, auth_code: str, request: LoginRequest
    ) -> Optional[OAuthTokens]:
        """Exchange authorization code for access tokens."""
        if not self.oauth_helper:
            logger.error("OAuth helper not configured")
            return None

        try:
            token_data = await self.oauth_helper.exchange_code_for_token(
                token_url=self._get_token_url(),
                client_id=request.client_id,
                client_secret=request.client_secret,
                redirect_uri=request.redirect_uri,
                code=auth_code,
                extra=self._get_token_extra_params(request),
            )

            # Convert to OAuthTokens model
            tokens = OAuthTokens(
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                scope=token_data.get("scope"),
            )

            # Calculate expires_at if expires_in is provided
            if tokens.expires_in:
                from datetime import datetime, timedelta

                tokens.expires_at = datetime.utcnow() + timedelta(
                    seconds=tokens.expires_in
                )

            return tokens

        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return None

    def _get_token_url(self) -> str:
        """Get OAuth2 token URL. Override in provider-specific strategies."""
        raise NotImplementedError("Subclasses must implement _get_token_url")

    def _get_token_extra_params(self, request: LoginRequest) -> dict:
        """Get extra parameters for token exchange. Override in provider-specific strategies."""
        return {}
