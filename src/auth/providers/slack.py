"""Comprehensive Slack authentication strategy - Email → CAPTCHA → OTP → Access Token + OAuth v2 Flow."""

import logging
import asyncio
import json
import requests
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from src.models import AuthProvider, LoginRequest, SessionCookie, OAuthTokens
from src.auth.base import HybridBaseStrategy, AuthMethod
from src.auth.captcha.factory import CaptchaSolverFactory, CaptchaSolverType
from src.config import settings

logger = logging.getLogger(__name__)


class SlackAuthStrategy(HybridBaseStrategy):
    """Comprehensive Slack authentication strategy with OAuth v2 support"""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.SLACK

    @property
    def supported_methods(self) -> List[AuthMethod]:
        return [AuthMethod.PASSWORD, AuthMethod.HYBRID, AuthMethod.OAUTH2]

    @property
    def default_method(self) -> AuthMethod:
        return AuthMethod.HYBRID

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Simplified Slack login flow: Email → CAPTCHA → OTP → Success."""
        logger.info("🚀 Starting simplified Slack authentication flow")
        logger.info(f"📧 Email: {request.email}")
        
        # Step 1: Navigate to Slack login
        await page.goto("https://slack.com/signin", wait_until="domcontentloaded", timeout=30000)
        logger.info("✅ Navigated to Slack login page")
        
        # Step 2: Fill email and trigger CAPTCHA
        await self._fill_email_and_trigger_captcha(page, request.email)
        
        # Step 3: Solve CAPTCHA
        await self._solve_captcha(page)
        
        # Step 4: Fill password
        if request.password:
            await self._fill_password(page, request.password)
        
        # Step 5: Handle 2FA/OTP
        await self._handle_otp(page, request)
        
        logger.info("🎉 Slack authentication flow completed")

    async def _fill_email_and_trigger_captcha(self, page: Page, email: str) -> None:
        """Fill email and trigger CAPTCHA."""
        logger.info("📧 Filling email and triggering CAPTCHA...")
        
        # Wait for email input
        try:
            await page.wait_for_selector('input[type="email"]', timeout=10000)
        except PlaywrightTimeoutError:
            logger.error("❌ Email input not found")
            raise
        
        # Fill email
        email_input = await page.query_selector('input[type="email"]')
        if email_input:
            await email_input.fill(email)
            logger.info(f"✅ Email filled: {email}")
            await page.wait_for_timeout(1000)
        
        # Click continue to trigger CAPTCHA
        continue_selectors = [
            'button[data-qa="signin_email_button"]',
            'button:has-text("Continue")',
            'button:has-text("Sign In With Email")',
            'button[type="submit"]'
        ]
        
        for selector in continue_selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    await button.click()
                    logger.info(f"✅ Continue button clicked: {selector}")
                    await page.wait_for_timeout(3000)
                    break
            except Exception as e:
                logger.debug(f"Continue button {selector} failed: {e}")
                continue

    async def _solve_captcha(self, page: Page) -> None:
        """Solve CAPTCHA using Browserbase following official documentation patterns."""
        logger.info("🤖 Solving CAPTCHA with Browserbase...")
        
        # Wait a bit for CAPTCHA to appear
        await page.wait_for_timeout(3000)
        
        # Check if CAPTCHA is present
        captcha_elements = await page.query_selector_all('iframe[src*="recaptcha"]')
        if not captcha_elements:
            logger.info("ℹ️ No CAPTCHA detected - continuing without solving")
            return
        
        logger.info(f"🎯 Found {len(captcha_elements)} CAPTCHA elements")
        
        # Take screenshot before solving
        await page.screenshot(path="captcha_before.png")
        
        # Browserbase will automatically solve CAPTCHAs when solveCaptchas is enabled
        # We just need to wait for the official Browserbase events
        try:
            logger.info("🤖 Waiting for Browserbase to solve CAPTCHA automatically...")
            
            # Click the CAPTCHA checkbox to trigger Browserbase solving
            checkbox = await page.query_selector('.recaptcha-checkbox')
            if checkbox:
                await checkbox.click()
                logger.info("🖱️ Clicked reCAPTCHA checkbox to trigger Browserbase")
                await page.wait_for_timeout(2000)
            
            # Wait for Browserbase to solve (up to 30 seconds as per documentation)
            timeout_seconds = 30
            for i in range(timeout_seconds):
                await asyncio.sleep(1)
                
                # Check if CAPTCHA is still present
                still_present = await page.query_selector('iframe[src*="recaptcha"]')
                if not still_present:
                    logger.info("✅ CAPTCHA solved by Browserbase!")
                    await page.screenshot(path="captcha_after.png")
                    return
                
                # Check for image selection challenge
                image_challenge = await page.query_selector('div[class*="rc-imageselect"]')
                if image_challenge:
                    logger.info("🎯 Image selection challenge detected - Browserbase should be solving this")
                    await page.screenshot(path="captcha_image_challenge.png")
                    # Wait a bit more for Browserbase to solve image challenge
                    await asyncio.sleep(5)
                    
                    # Check again
                    still_present = await page.query_selector('iframe[src*="recaptcha"]')
                    if not still_present:
                        logger.info("✅ Image challenge solved by Browserbase!")
                        await page.screenshot(path="captcha_after.png")
                        return
                
                if i % 5 == 0 and i > 0:
                    logger.info(f"⏳ Still waiting for Browserbase... {i}s elapsed")
            
            logger.warning("⏰ Browserbase timeout - CAPTCHA may need manual intervention")
            
        except Exception as e:
            logger.error(f"❌ Browserbase error: {e}")
        
        # If Browserbase doesn't solve it automatically, we'll let the user handle it
        logger.info("🤖 Browserbase automatic solving completed or timed out")
        await page.screenshot(path="captcha_after.png")

    async def _fill_password(self, page: Page, password: str) -> None:
        """Fill password."""
        logger.info("🔒 Filling password...")
        
        try:
            await page.wait_for_selector('input[type="password"]', timeout=10000)
        except PlaywrightTimeoutError:
            logger.info("ℹ️ No password field found")
            return
        
        password_input = await page.query_selector('input[type="password"]')
        if password_input:
            await password_input.fill(password)
            logger.info("✅ Password filled")
            await page.wait_for_timeout(1000)
            
            # Submit password form
            submit_selectors = [
                'button[data-qa="signin_password_button"]',
                'button:has-text("Sign In")',
                'button[type="submit"]'
            ]
            
            for selector in submit_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        await button.click()
                        logger.info(f"✅ Password submitted: {selector}")
                        await page.wait_for_timeout(3000)
                        break
                except Exception as e:
                    logger.debug(f"Submit button {selector} failed: {e}")
                    continue

    async def _handle_otp(self, page: Page, request: LoginRequest) -> None:
        """Handle OTP/2FA."""
        logger.info("🔐 Checking for OTP/2FA...")
        
        # Check for OTP input
        otp_selectors = [
            'input[name="totpPin"]',
            'input[type="tel"]',
            'input[placeholder*="code"]',
            'input[placeholder*="verification"]',
            'input[data-qa="totp_input"]'
        ]
        
        otp_found = False
        for selector in otp_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    otp_found = True
                    logger.info(f"🎯 OTP input found: {selector}")
                    break
            except Exception:
                continue
        
        if not otp_found:
            logger.info("✅ No OTP required")
            return
        
        # Handle TOTP if secret provided
        if request.totp_secret:
            logger.info("🤖 Using TOTP secret for OTP...")
            await self._handle_totp_otp(page, request.totp_secret)
        else:
            logger.info("⏳ Manual OTP required - waiting for user input...")
            await self._wait_for_manual_otp(page)

    async def _handle_totp_otp(self, page: Page, totp_secret: str) -> None:
        """Handle TOTP-based OTP."""
        try:
            import pyotp
            
            # Generate TOTP code
            totp = pyotp.TOTP(totp_secret)
            totp_code = totp.now()
            logger.info(f"🔑 Generated TOTP code: {totp_code}")
            
            # Fill OTP code
            otp_selectors = [
                'input[name="totpPin"]',
                'input[type="tel"]',
                'input[placeholder*="code"]',
                'input[placeholder*="verification"]'
            ]
            
            for selector in otp_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.fill(totp_code)
                        logger.info(f"✅ OTP code filled: {selector}")
                        
                        # Submit OTP form
                        submit_selectors = [
                            'button:has-text("Verify")',
                            'button:has-text("Continue")',
                            'button[type="submit"]'
                        ]
                        
                        for submit_selector in submit_selectors:
                            try:
                                submit_button = await page.query_selector(submit_selector)
                                if submit_button and await submit_button.is_visible():
                                    await submit_button.click()
                                    logger.info(f"✅ OTP submitted: {submit_selector}")
                                    await page.wait_for_timeout(3000)
                                    return
                            except Exception:
                                continue
                        break
                except Exception:
                    continue
                    
        except ImportError:
            logger.error("❌ PyOTP library not installed")
        except Exception as e:
            logger.error(f"❌ TOTP OTP failed: {e}")

    async def _wait_for_manual_otp(self, page: Page) -> None:
        """Wait for manual OTP input."""
        logger.info("⏳ Waiting up to 120 seconds for manual OTP...")
        
        for attempt in range(120):
            await asyncio.sleep(1)
            
            # Check if OTP input is still visible
            otp_selectors = [
                'input[name="totpPin"]',
                'input[type="tel"]',
                'input[placeholder*="code"]',
                'input[placeholder*="verification"]'
            ]
            
            still_visible = False
            for selector in otp_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        still_visible = True
                        break
                except Exception:
                    continue
            
            if not still_visible:
                logger.info("✅ OTP appears to be completed")
                return
            
            if attempt % 10 == 0 and attempt > 0:
                logger.info(f"⏳ Still waiting for OTP... ({attempt}s)")
        
        logger.warning("⏰ OTP timeout after 120 seconds")

    async def is_success(self, page: Page) -> bool:
        """Check if login was successful."""
        logger.info("🔍 Checking login success...")
        
        # Slack success indicators
        success_indicators = [
            lambda: "slack.com" in page.url and "/messages" in page.url,
            lambda: "slack.com" in page.url and "/client" in page.url,
            lambda: page.query_selector('[data-qa="workspace_menu"]'),
            lambda: page.query_selector('[data-qa="channel_sidebar"]'),
            lambda: page.get_by_text("Welcome to Slack").is_visible()
        ]
        
        for i, indicator in enumerate(success_indicators):
            try:
                result = await indicator()
                if result:
                    logger.info(f"✅ Success indicator {i+1} matched!")
                    return True
            except Exception as e:
                logger.debug(f"Success indicator {i+1} failed: {e}")
                continue
        
        logger.info("❌ No success indicators matched")
        return False

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract session cookies."""
        logger.info("🍪 Extracting session cookies...")
        
        browser_cookies = await page.context.cookies()
        important_cookies = {"d", "b", "x", "session", "token", "user_session"}
        
        session_cookies = []
        for cookie in browser_cookies:
            if "slack.com" in cookie["domain"] or cookie["name"] in important_cookies:
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
        
        logger.info(f"✅ Extracted {len(session_cookies)} cookies")
        return session_cookies

    # OAuth2 methods (comprehensive implementation)
    async def oauth2_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Comprehensive OAuth2 login with Browserbase integration."""
        logger.info("🔄 Starting Slack OAuth v2 flow with Browserbase integration")
        
        try:
            # Step 1: Construct OAuth authorize URL
            authorize_url = self._build_oauth_url(request)
            logger.info(f"🔗 OAuth URL: {authorize_url}")
            
            # Step 2: Navigate to OAuth authorize page
            await page.goto(authorize_url, wait_until="domcontentloaded", timeout=30000)
            logger.info("✅ Navigated to Slack OAuth authorize page")
            
            # Step 3: Handle login flow (email → CAPTCHA → password → 2FA)
            await self._handle_oauth_login_flow(page, request)
            
            # Step 4: Handle app authorization
            await self._handle_app_authorization(page)
            
            # Step 5: Capture authorization code from redirect
            auth_code = await self._capture_auth_code(page)
            
            # Step 6: Exchange code for tokens
            oauth_tokens = await self._exchange_code_for_tokens(auth_code, request)
            
            logger.info("🎉 OAuth v2 flow completed successfully")
            return oauth_tokens
            
        except Exception as e:
            logger.error(f"❌ OAuth v2 flow failed: {e}")
            return None

    def _build_oauth_url(self, request: LoginRequest) -> str:
        """Build Slack OAuth v2 authorize URL."""
        base_url = "https://slack.com/oauth/v2/authorize"
        
        # Get OAuth parameters from request or settings
        client_id = getattr(request, 'client_id', None) or settings.slack_client_id
        scopes = getattr(request, 'scopes', None) or settings.slack_scopes.split(',')
        redirect_uri = getattr(request, 'redirect_uri', None) or settings.slack_redirect_uri
        team_id = getattr(request, 'team_id', None)
        
        # Ensure scopes is a list
        if isinstance(scopes, str):
            scopes = scopes.split(',')
        scopes_str = ','.join(scopes) if scopes else settings.slack_scopes
        
        if not client_id:
            raise ValueError("Slack client_id is required for OAuth flow")
        
        params = {
            'client_id': client_id,
            'scope': scopes_str,
            'redirect_uri': redirect_uri,
            'response_type': 'code'
        }
        
        if team_id:
            params['team'] = team_id
        
        # Build query string
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{base_url}?{query_string}"

    async def _handle_oauth_login_flow(self, page: Page, request: LoginRequest) -> None:
        """Handle the login portion of OAuth flow."""
        logger.info("🔐 Handling OAuth login flow...")
        
        # Check if we're already logged in
        if await self._is_already_logged_in(page):
            logger.info("✅ Already logged in to Slack")
            return
        
        # Fill email and trigger CAPTCHA
        await self._fill_email_and_trigger_captcha(page, request.email)
        
        # Solve CAPTCHA
        await self._solve_captcha(page)
        
        # Fill password
        if request.password:
            await self._fill_password(page, request.password)
        
        # Handle 2FA/OTP
        await self._handle_otp(page, request)
        
        # Wait for redirect to authorization page
        await page.wait_for_timeout(3000)

    async def _is_already_logged_in(self, page: Page) -> bool:
        """Check if user is already logged in to Slack."""
        try:
            # Look for elements that indicate we're already logged in
            logged_in_indicators = [
                '[data-qa="oauth_submit_button"]',  # Authorize button
                'button:has-text("Allow")',
                'button:has-text("Authorize")',
                'button:has-text("Continue")'
            ]
            
            for indicator in logged_in_indicators:
                element = await page.query_selector(indicator)
                if element and await element.is_visible():
                    logger.info("✅ Already logged in - found authorization button")
                    return True
            
            return False
        except Exception as e:
            logger.debug(f"Error checking login status: {e}")
            return False

    async def _handle_app_authorization(self, page: Page) -> None:
        """Handle the app authorization step."""
        logger.info("📱 Handling app authorization...")
        
        # Wait for authorization page to load
        await page.wait_for_timeout(3000)
        
        # Look for authorization button
        auth_selectors = [
            'button[data-qa="oauth_submit_button"]',
            'button:has-text("Allow")',
            'button:has-text("Authorize")',
            'button:has-text("Continue")',
            'button[type="submit"]'
        ]
        
        for selector in auth_selectors:
            try:
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    logger.info(f"✅ Found authorization button: {selector}")
                    await button.click()
                    logger.info("✅ Authorization button clicked")
                    await page.wait_for_timeout(3000)
                    return
            except Exception as e:
                logger.debug(f"Authorization button {selector} failed: {e}")
                continue
        
        logger.warning("⚠️ No authorization button found - may already be authorized")

    async def _capture_auth_code(self, page: Page) -> str:
        """Capture authorization code from redirect URL."""
        logger.info("🔍 Capturing authorization code...")
        
        # Wait for redirect to callback URL
        max_wait = 30
        for attempt in range(max_wait):
            current_url = page.url
            logger.debug(f"Current URL: {current_url}")
            
            # Check if we're at the callback URL
            if settings.slack_redirect_uri in current_url or "code=" in current_url:
                logger.info("✅ Redirected to callback URL")
                break
            
            await asyncio.sleep(1)
        
        # Parse the authorization code from URL
        parsed_url = urlparse(page.url)
        query_params = parse_qs(parsed_url.query)
        
        auth_code = query_params.get('code', [None])[0]
        if not auth_code:
            # Try to get from fragment
            fragment = parsed_url.fragment
            if fragment:
                fragment_params = parse_qs(fragment)
                auth_code = fragment_params.get('code', [None])[0]
        
        if not auth_code:
            raise ValueError(f"Failed to capture auth code from URL: {page.url}")
        
        logger.info(f"✅ Authorization code captured: {auth_code[:10]}...")
        return auth_code

    async def _exchange_code_for_tokens(self, auth_code: str, request: LoginRequest) -> OAuthTokens:
        """Exchange authorization code for access tokens."""
        logger.info("🔄 Exchanging authorization code for tokens...")
        
        # Get OAuth parameters
        client_id = getattr(request, 'client_id', None) or settings.slack_client_id
        client_secret = getattr(request, 'client_secret', None) or settings.slack_client_secret
        redirect_uri = getattr(request, 'redirect_uri', None) or settings.slack_redirect_uri
        
        if not client_id or not client_secret:
            raise ValueError("Slack client_id and client_secret are required for token exchange")
        
        # Prepare token exchange request
        token_url = "https://slack.com/api/oauth.v2.access"
        payload = {
            'code': auth_code,
            'client_id': client_id,
            'client_secret': client_secret,
            'redirect_uri': redirect_uri
        }
        
        # Make token exchange request
        response = requests.post(token_url, data=payload, timeout=30)
        
        if response.status_code != 200:
            raise ValueError(f"Token exchange failed with status {response.status_code}: {response.text}")
        
        token_data = response.json()
        
        if not token_data.get('ok'):
            error = token_data.get('error', 'Unknown error')
            raise ValueError(f"Token exchange failed: {error}")
        
        # Create OAuthTokens object
        oauth_tokens = OAuthTokens(
            access_token=token_data.get('access_token'),
            refresh_token=token_data.get('refresh_token'),
            token_type=token_data.get('token_type', 'Bearer'),
            expires_in=token_data.get('expires_in'),
            scope=token_data.get('scope'),
            team_id=token_data.get('team', {}).get('id') if token_data.get('team') else None,
            team_name=token_data.get('team', {}).get('name') if token_data.get('team') else None,
            user_id=token_data.get('authed_user', {}).get('id') if token_data.get('authed_user') else None,
            bot_user_id=token_data.get('bot_user_id'),
            app_id=token_data.get('app_id')
        )
        
        logger.info("✅ OAuth tokens obtained successfully")
        logger.info(f"   - Access Token: {oauth_tokens.access_token[:20]}...")
        logger.info(f"   - Team: {oauth_tokens.team_name} ({oauth_tokens.team_id})")
        logger.info(f"   - User: {oauth_tokens.user_id}")
        logger.info(f"   - Bot User: {oauth_tokens.bot_user_id}")
        
        return oauth_tokens

    async def google_login(self, page: Page, request: LoginRequest) -> Optional[OAuthTokens]:
        """Google login via Slack (redirects to Google OAuth)."""
        logger.info("🔄 Google login via Slack OAuth flow")
        
        # For Google login, we'll use the OAuth flow with Google as the identity provider
        # This would require additional configuration for Google OAuth
        logger.info("🔄 Google login not fully implemented - use OAuth2 flow instead")
        return None

    # Utility methods for OAuth flow
    async def get_oauth_url(self, request: LoginRequest) -> str:
        """Get the OAuth authorization URL for manual use."""
        return self._build_oauth_url(request)

    async def exchange_code_for_tokens_standalone(self, auth_code: str, request: LoginRequest) -> Optional[OAuthTokens]:
        """Exchange authorization code for tokens without browser automation."""
        try:
            return await self._exchange_code_for_tokens(auth_code, request)
        except Exception as e:
            logger.error(f"❌ Standalone token exchange failed: {e}")
            return None
