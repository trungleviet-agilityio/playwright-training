"""Slack authentication strategy for Google OAuth2 with PyOTP 2FA."""

import logging
import asyncio
from typing import List, Optional
from urllib.parse import urlparse, parse_qs
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError
import pyotp
from src.models import AuthProvider, LoginRequest, SessionCookie, OAuthTokens
from src.auth.base import OAuth2BaseStrategy, AuthMethod
from src.auth.oauth_helper import (
    exchange_slack_code_for_token,
    build_slack_authorize_url,
    TokenExchangeError,
)
from src.config import settings
from src.constants import (
    DEFAULT_TIMEOUT,
    SLACK_SIGNIN_URL,
    SLACK_EMAIL_SELECTORS,
    SLACK_PASSWORD_SELECTORS,
    SLACK_CONTINUE_BUTTON_SELECTORS,
    SLACK_2FA_SELECTORS,
)

logger = logging.getLogger(__name__)


class SlackAuthStrategy(OAuth2BaseStrategy):
    """Slack authentication strategy for Google OAuth2 with PyOTP 2FA."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.SLACK

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.OAUTH2]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.OAUTH2

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Handle Slack Google Authentication flow."""
        logger.info(f"Starting Slack Google Authentication for {request.email}")

        # Navigate to Slack login URL
        workspace_url = getattr(request, "workspace_url", None)
        login_url = (
            f"https://{workspace_url.replace('https://', '').replace('.slack.com', '')}.slack.com/signin"
            if workspace_url
            else SLACK_SIGNIN_URL
        )
        logger.info(f"Navigating to {login_url}")
        await page.goto(
            login_url, wait_until="domcontentloaded", timeout=DEFAULT_TIMEOUT
        )

        # Click "Continue with Google" button
        await self._click_google_signin_button(page)

        # Handle Google OAuth login
        await self._handle_google_oauth(page, request)

        # Handle Google 2FA with PyOTP
        await self._handle_google_2fa(page, request)

        logger.info("Slack Google Authentication completed")

    async def _handle_workspace_signin(self, page: Page, request: LoginRequest) -> None:
        """Handle Slack workspace signin page."""
        logger.info("Handling workspace signin")

        # Extract workspace from workspace_url or email domain
        workspace = None
        if request.workspace_url:
            # Extract workspace name from workspace URL
            workspace = request.workspace_url.replace("https://", "").replace(
                ".slack.com", ""
            )
        elif not workspace:
            # Try to extract workspace from email domain
            email_domain = request.email.split("@")[1] if "@" in request.email else ""
            if email_domain:
                # Remove common email providers and use the domain as workspace
                if email_domain not in [
                    "gmail.com",
                    "yahoo.com",
                    "hotmail.com",
                    "outlook.com",
                ]:
                    workspace = email_domain.split(".")[0]
                else:
                    # For common email providers, we need the user to provide workspace
                    workspace = (
                        "your-workspace"  # This will need to be provided by user
                    )

        if workspace and workspace != "your-workspace":
            logger.info(f"Using workspace: {workspace}")
            # Fill in the workspace domain
            domain_input = await page.query_selector('input[id="domain"]')
            if domain_input:
                await domain_input.fill(workspace)
                logger.info(f"Filled workspace domain: {workspace}")

                # Click continue button
                continue_button = await page.query_selector('button[type="submit"]')
                if continue_button:
                    await continue_button.click()
                    logger.info("Clicked continue button")
                    await page.wait_for_timeout(3000)  # Wait for navigation
                else:
                    logger.warning("Continue button not found")
            else:
                logger.warning("Workspace domain input not found")
        else:
            logger.warning("No workspace provided, user will need to enter it manually")

    async def _click_google_signin_button(self, page: Page) -> None:
        """Click the 'Google' signin button."""
        google_button_selectors = [
            'button:has-text("Google")',
            'button:has-text("Continue with Google")',
            'div[data-qa="sso_google"]',
            'button[data-qa="signin_with_google"]',
            'div[aria-label="Sign in with Google"]',
            'button[aria-label*="Google"]',
        ]
        for selector in google_button_selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    logger.info("Clicked 'Continue with Google' button")
                    await page.wait_for_timeout(2000)
                    return
            except Exception as e:
                logger.debug(f"Google button selector {selector} failed: {e}")
        raise ValueError("Google sign-in button not found")

    async def _handle_google_oauth(self, page: Page, request: LoginRequest) -> None:
        """Handle Google OAuth login flow."""
        logger.info("Handling Google OAuth login")

        # Wait for page to load
        await page.wait_for_timeout(3000)

        # Log current URL and page title for debugging
        logger.info(f"Current URL: {page.url}")
        title = await page.title()
        logger.info(f"Page title: {title}")

        # Handle email input
        for selector in SLACK_EMAIL_SELECTORS:
            try:
                email_input = await page.query_selector(selector)
                if email_input and await email_input.is_visible():
                    await email_input.fill(request.email)
                    logger.info(f"Filled email: {request.email}")
                    await self._click_continue_button(page)
                    
                    # Wait for password page to load
                    await page.wait_for_timeout(3000)
                    
                    # Handle password input if available
                    password = getattr(request, "password", None)
                    if password:
                        await self._handle_google_password(page, password)
                    else:
                        logger.warning("No password provided, user will need to enter it manually")
                    return
            except Exception as e:
                logger.debug(f"Email selector {selector} failed: {e}")
        raise ValueError("Email input field not found")

    async def _handle_google_password(self, page: Page, password: str) -> None:
        """Handle Google password input."""
        logger.info("Handling Google password input")
        
        for selector in SLACK_PASSWORD_SELECTORS:
            try:
                password_input = await page.query_selector(selector)
                if password_input and await password_input.is_visible():
                    await password_input.fill(password)
                    logger.info("Filled password")
                    await self._click_continue_button(page)
                    return
            except Exception as e:
                logger.debug(f"Password selector {selector} failed: {e}")
        logger.warning("Password input field not found")

    async def _handle_google_2fa(self, page: Page, request: LoginRequest) -> None:
        """Handle Google 2FA using PyOTP."""
        logger.info("Checking for Google 2FA")
        if not getattr(request, "otp_secret", None):
            logger.info("No OTP secret provided, skipping 2FA")
            return

        try:
            totp = pyotp.TOTP(request.otp_secret)
            otp_code = totp.now()
            logger.info(f"Generated 2FA code: {otp_code}")

            for selector in SLACK_2FA_SELECTORS:
                try:
                    otp_input = await page.query_selector(selector)
                    if otp_input and await otp_input.is_visible():
                        await otp_input.fill(otp_code)
                        logger.info("Filled 2FA code")
                        await self._click_continue_button(page)
                        await page.wait_for_timeout(2000)
                        return
                except Exception as e:
                    logger.debug(f"2FA selector {selector} failed: {e}")
            logger.warning("No 2FA input field found")
        except Exception as e:
            logger.error(f"2FA handling failed: {e}")

    async def _click_continue_button(self, page: Page) -> None:
        """Click the continue button."""
        for selector in SLACK_CONTINUE_BUTTON_SELECTORS:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    logger.info("Clicked continue button")
                    await page.wait_for_timeout(2000)
                    return
            except Exception as e:
                logger.debug(f"Continue button selector {selector} failed: {e}")
        logger.info("No continue button found, attempting Enter key")
        await page.press('input[type="email"]', "Enter")
        await page.wait_for_timeout(2000)

    async def oauth2_login(
        self, page: Page, request: LoginRequest
    ) -> Optional[OAuthTokens]:
        """Handle Slack OAuth2 login flow."""
        logger.info("Starting Slack OAuth2 flow")

        try:
            # Build OAuth URL
            authorize_url = build_slack_authorize_url(
                client_id=settings.slack_client_id,
                redirect_uri=settings.slack_redirect_uri,
                scopes=settings.slack_scopes,
                team_id=getattr(request, "team_id", None),
                state=getattr(request, "state", None),
            )
            logger.info(f"Navigating to OAuth URL: {authorize_url}")
            await page.goto(authorize_url, wait_until="domcontentloaded", timeout=30000)

            # Debug: Log current state after navigation
            logger.info(f"After navigation - URL: {page.url}")
            title = await page.title()
            logger.info(f"After navigation - Title: {title}")

            # Handle login flow
            if not await self._is_already_logged_in(page):
                logger.info(
                    "User not already logged in, proceeding with authentication"
                )

                # Check if we're on the workspace signin page
                if "workspace-signin" in page.url:
                    logger.info(
                        "On workspace signin page, handling workspace selection"
                    )
                    await self._handle_workspace_signin(page, request)

                # Now handle Google OAuth - first click Google button
                await self._click_google_signin_button(page)
                await self._handle_google_oauth(page, request)
                await self._handle_google_2fa(page, request)
            else:
                logger.info("User already logged in, skipping authentication")

            # Handle app authorization
            await self._handle_app_authorization(page)

            # Capture authorization code
            auth_code = await self._capture_auth_code(page)

            # Exchange code for tokens
            oauth_tokens = await self._exchange_slack_code_for_tokens(
                auth_code, request
            )
            logger.info("Slack OAuth2 flow completed")
            return oauth_tokens

        except Exception as e:
            logger.error(f"Slack OAuth2 flow failed: {e}")
            return None

    async def _is_already_logged_in(self, page: Page) -> bool:
        """Check if user is already logged in."""
        auth_selectors = [
            'button[data-qa="oauth_submit_button"]',
            'button:has-text("Allow")',
            'button:has-text("Authorize")',
        ]
        for selector in auth_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    logger.info("Already logged in - found authorization button")
                    return True
            except Exception:
                continue
        return False

    async def _handle_app_authorization(self, page: Page) -> None:
        """Handle app authorization step."""
        auth_selectors = [
            'button[data-qa="oauth_submit_button"]',
            'button:has-text("Allow")',
            'button:has-text("Authorize")',
        ]
        for selector in auth_selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    logger.info("Clicked authorization button")
                    await page.wait_for_timeout(2000)
                    return
            except Exception as e:
                logger.debug(f"Authorization button {selector} failed: {e}")
        logger.info("No authorization button found, assuming already authorized")

    async def _capture_auth_code(self, page: Page) -> str:
        """Capture authorization code from redirect URL."""
        for _ in range(30):
            if "code=" in page.url:
                parsed_url = urlparse(page.url)
                query_params = parse_qs(parsed_url.query)
                auth_code = query_params.get("code", [None])[0]
                if auth_code:
                    logger.info(f"Captured authorization code: {auth_code[:10]}...")
                    return auth_code
            await asyncio.sleep(1)
        raise ValueError(f"Failed to capture auth code from URL: {page.url}")

    async def _exchange_slack_code_for_tokens(
        self, auth_code: str, request: LoginRequest
    ) -> OAuthTokens:
        """Exchange Slack authorization code for tokens."""
        logger.info("Exchanging Slack authorization code for tokens")
        try:
            token_data = await exchange_slack_code_for_token(
                client_id=settings.slack_client_id,
                client_secret=settings.slack_client_secret,
                redirect_uri=settings.slack_redirect_uri,
                code=auth_code,
            )
            oauth_tokens = OAuthTokens(
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_type=token_data.get("token_type", "Bearer"),
                expires_in=token_data.get("expires_in"),
                scope=token_data.get("scope"),
                team_id=token_data.get("team", {}).get("id"),
                team_name=token_data.get("team", {}).get("name"),
                user_id=token_data.get("authed_user", {}).get("id"),
                bot_user_id=token_data.get("bot_user_id"),
                app_id=token_data.get("app_id"),
            )
            logger.info("Slack OAuth tokens obtained")
            return oauth_tokens
        except TokenExchangeError as e:
            logger.error(f"Slack token exchange failed: {e}")
            raise

    async def is_success(self, page: Page) -> bool:
        """Check if login was successful."""
        success_indicators = [
            lambda: "slack.com" in page.url and "/messages" in page.url,
            lambda: page.query_selector('[data-qa="workspace_menu"]'),
            lambda: page.query_selector('[data-qa="channel_sidebar"]'),
        ]
        for i, indicator in enumerate(success_indicators):
            try:
                if await indicator():
                    logger.info(f"Login success confirmed (indicator {i+1})")
                    return True
            except Exception:
                continue
        logger.info("No success indicators matched")
        return False

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract session cookies."""
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
            if "slack.com" in c["domain"]
        ]
        logger.info(f"Extracted {len(session_cookies)} cookies")
        return session_cookies
