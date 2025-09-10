"""Slack authentication strategy"""

import logging
from typing import List, Optional
from urllib.parse import urlencode, urlparse, parse_qs

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie, OAuthTokens
from src.auth.base import AuthStrategy
from src.auth.oauth_helper import exchange_code_for_token
from src.constants import SLACK_URL

logger = logging.getLogger(__name__)


class SlackAuthStrategy(AuthStrategy):
    """Slack authentication strategy following the base strategy pattern."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.SLACK

    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Perform Slack OAuth2 authentication - Clean implementation."""
        if not request.client_id or not request.redirect_uri:
            logger.error("Slack OAuth2 requires client_id and redirect_uri")
            return None

        try:
            # Step 1: Navigate to Slack OAuth2 authorization URL
            auth_url = self._build_oauth_url(request)
            logger.info(f"Navigating to Slack OAuth2: {auth_url}")
            await page.goto(auth_url, wait_until="domcontentloaded")

            # Step 2: Handle sign-in if required
            await self._handle_signin_if_needed(page, request)

            # Step 3: Handle consent/authorization
            await self._handle_authorization(page)

            # Step 4: Wait for callback and extract code
            callback_url = await self._wait_for_callback(page, request.redirect_uri)
            auth_code = self._extract_code(callback_url)
            
            if not auth_code:
                logger.error("Failed to extract authorization code")
                return None

            # Step 5: Exchange code for tokens
            tokens = await self._exchange_code_for_tokens(auth_code, request)
            logger.info("Slack OAuth2 authentication successful")
            return tokens

        except Exception as e:
            logger.error(f"Slack OAuth2 authentication failed: {e}")
            return None

    def _build_oauth_url(self, request: LoginRequest) -> str:
        """Build Slack OAuth2 authorization URL."""
        params = {
            "client_id": request.client_id,
            "scope": ",".join(request.scopes) if request.scopes else "channels:read,chat:write,users:read",
            "redirect_uri": request.redirect_uri,
            "response_type": "code",
        }
        
        if request.state:
            params["state"] = request.state

        return f"https://slack.com/oauth/v2/authorize?{urlencode(params)}"

    async def _handle_signin_if_needed(self, page: Page, request: LoginRequest) -> None:
        """Handle Slack sign-in if required during OAuth2 flow."""
        if "signin" not in page.url and "login" not in page.url:
            return

        logger.info("Handling Slack sign-in for OAuth2 flow...")
        
        # Fill email
        email_input = await page.query_selector('input[type="email"], input[name="email"]')
        if email_input:
            await email_input.fill(request.email)
            await page.click('button[type="submit"], button:has-text("Continue")')
            await page.wait_for_timeout(2000)

        # Fill password if needed
        if request.password:
            password_input = await page.query_selector('input[type="password"]')
            if password_input:
                await password_input.fill(request.password)
                await page.click('button[type="submit"], button:has-text("Sign In")')
                await page.wait_for_timeout(3000)

    async def _handle_authorization(self, page: Page) -> None:
        """Handle Slack authorization/consent page."""
        logger.info("Handling Slack authorization...")
        
        # Look for authorize button
        authorize_button = await page.query_selector(
            'button[data-qa="oauth_authorize_button"], button:has-text("Allow"), button:has-text("Authorize")'
        )
        
        if authorize_button:
            await authorize_button.click()
            await page.wait_for_timeout(2000)
        else:
            logger.warning("No authorize button found")

    async def _wait_for_callback(self, page: Page, redirect_uri: str) -> str:
        """Wait for OAuth2 callback redirect."""
        logger.info(f"Waiting for OAuth2 callback to: {redirect_uri}")
        
        await page.wait_for_function(
            f"window.location.href.startsWith('{redirect_uri}')",
            timeout=60000
        )
        
        return page.url

    def _extract_code(self, callback_url: str) -> Optional[str]:
        """Extract authorization code from callback URL."""
        try:
            parsed_url = urlparse(callback_url)
            query_params = parse_qs(parsed_url.query)
            
            if "code" in query_params:
                return query_params["code"][0]
            
            if "error" in query_params:
                error = query_params["error"][0]
                logger.error(f"Slack OAuth2 error: {error}")
            
            return None
        except Exception as e:
            logger.error(f"Error extracting auth code: {e}")
            return None

    async def _exchange_code_for_tokens(self, auth_code: str, request: LoginRequest) -> Optional[OAuthTokens]:
        """Exchange authorization code for access tokens."""
        try:
            token_data = await exchange_code_for_token(
                token_url="https://slack.com/api/oauth.v2.access",
                client_id=request.client_id,
                client_secret=request.client_secret,
                redirect_uri=request.redirect_uri,
                code=auth_code,
            )

            if not token_data.get("ok"):
                logger.error(f"Slack token exchange failed: {token_data.get('error')}")
                return None

            # Convert to OAuthTokens
            tokens = OAuthTokens(
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
                token_type="Bearer",
                expires_in=token_data.get("expires_in"),
                scope=token_data.get("scope"),
            )

            # Calculate expires_at
            if tokens.expires_in:
                from datetime import datetime, timedelta
                tokens.expires_at = datetime.utcnow() + timedelta(seconds=tokens.expires_in)

            return tokens
            
        except Exception as e:
            logger.error(f"Token exchange failed: {e}")
            return None

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Slack login following the base strategy pattern."""
        logger.info("Starting Slack login for email: %s", request.email)
        
        # Navigate to Slack
        await page.goto(SLACK_URL, wait_until="domcontentloaded")
        logger.info("Navigated to Slack login page")
        
        # Use base class method for filling credentials
        await self._fill_slack_credentials(page, request)
        
        # Submit the form
        await self._submit_slack_form(page)
        
        logger.info("Slack login process completed")

    async def _fill_slack_credentials(self, page: Page, request: LoginRequest) -> None:
        """Fill Slack-specific credentials."""
        # Fill email
        email_input = await page.query_selector('input[type="email"]')
        if email_input:
            await email_input.fill(request.email)
            logger.info("Email filled successfully")
            
            # Click continue/next button
            continue_button = await page.query_selector(
                'button[type="submit"], button:has-text("Continue"), button[data-qa="signin_email_button"]'
            )
            if continue_button:
                await continue_button.click()
                await page.wait_for_timeout(2000)
                logger.info("Continue button clicked")
        
        # Fill password if provided
        if request.password:
            password_input = await page.query_selector('input[type="password"]')
            if password_input:
                await password_input.fill(request.password)
                logger.info("Password filled successfully")

    async def _submit_slack_form(self, page: Page) -> None:
        """Submit Slack login form."""
        submit_button = await page.query_selector(
            'button[type="submit"], button:has-text("Sign In"), button[data-qa="signin_password_button"]'
        )
        if submit_button:
            await submit_button.click()
            await page.wait_for_timeout(3000)
            logger.info("Login form submitted")
        else:
            # Fallback: press Enter on password field
            try:
                await page.press('input[type="password"]', "Enter")
                await page.wait_for_timeout(3000)
                logger.info("Login form submitted via Enter key")
            except Exception:
                pass

    async def is_success(self, page: Page) -> bool:
        """Check if Slack login was successful."""
        logger.info("Checking if Slack login was successful...")
        logger.info(f"Current URL: {page.url}")
        
        # Slack-specific success indicators
        success_indicators = [
            # URL-based checks
            lambda: "slack.com" in page.url and "/messages" in page.url,
            lambda: "slack.com" in page.url and "/client" in page.url,
            
            # Element-based checks
            lambda: page.query_selector('[data-qa="workspace_menu"]'),
            lambda: page.query_selector('[data-qa="channel_sidebar"]'),
            lambda: page.query_selector('.p-workspace__sidebar'),
            
            # Text-based checks
            lambda: page.get_by_text("Welcome to Slack").is_visible(),
            lambda: page.get_by_text("You're signed in").is_visible(),
        ]
        
        for i, indicator in enumerate(success_indicators):
            try:
                logger.info(f"Testing success indicator {i+1}/{len(success_indicators)}")
                result = await indicator()
                if result:
                    logger.info(f"Success indicator {i+1} matched! Login successful.")
                    return True
                else:
                    logger.info(f"Success indicator {i+1} did not match")
            except Exception as e:
                logger.info(f"Success indicator {i+1} failed with error: {e}")
                continue
        
        # Fallback to base class method
        logger.info("No Slack-specific success indicators matched, trying base class method...")
        return await super().is_success(page)

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Slack session cookies."""
        logger.info("Extracting Slack session cookies...")
        browser_cookies = await page.context.cookies()
        logger.info(f"Found {len(browser_cookies)} total cookies")
        
        # Focus on important Slack cookies
        important_cookies = {"d", "b", "x", "session", "token", "user_session"}
        
        session_cookies = []
        for cookie in browser_cookies:
            # Include all slack.com cookies and important ones
            if "slack.com" in cookie["domain"] or cookie["name"] in important_cookies:
                logger.info(f"Extracting cookie: {cookie['name']} from {cookie['domain']}")
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
        
        logger.info(f"Extracted {len(session_cookies)} relevant cookies")
        
        # Fallback to base class method if no cookies found
        if not session_cookies:
            logger.info("No Slack-specific cookies found, using base class method...")
            return await super().extract_cookies(page)
        
        return session_cookies
