"""Slack authentication strategy."""

import asyncio
import logging
from typing import List, Tuple

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import SLACK_URL, SLACK_ALT_URLS
from src.config import settings

# Try to import captcha solver, but make it optional
try:
    from twocaptcha import TwoCaptcha
    import asyncio
    CAPTCHA_AVAILABLE = True
except ImportError as e:
    logging.warning(f"2captcha library not available: {e}")
    CAPTCHA_AVAILABLE = False

# Set up logger for this module
logger = logging.getLogger(__name__)


class SlackAuthStrategy(AuthStrategy):
    """Slack authentication strategy with multiple login methods."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.SLACK

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Slack login."""
        logger.info(f"Starting Slack authentication for email: {request.email}")
        
        # Set additional headers to appear more like a real browser
        await page.set_extra_http_headers({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="131", "Google Chrome";v="131"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        })
        
        # Navigate to Slack sign-in page
        logger.info(f"Navigating to Slack URL: {SLACK_URL}")
        await page.goto(SLACK_URL, wait_until="domcontentloaded")
        logger.info("Successfully navigated to Slack sign-in page")
        
        # Check if we got the browser not supported message and try alternative URLs
        try:
            browser_not_supported = await page.get_by_text("We're very sorry, but your browser is not supported!").is_visible()
            if browser_not_supported:
                logger.warning("Slack detected unsupported browser, trying alternative URLs...")
                for alt_url in SLACK_ALT_URLS:
                    try:
                        logger.info(f"Trying alternative URL: {alt_url}")
                        await page.goto(alt_url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(2000)  # Wait for page to load
                        
                        # Check if this URL works better
                        browser_not_supported_alt = await page.get_by_text("We're very sorry, but your browser is not supported!").is_visible()
                        if not browser_not_supported_alt:
                            logger.info(f"Successfully navigated to working URL: {alt_url}")
                            break
                    except Exception as e:
                        logger.info(f"Failed to load {alt_url}: {e}")
                        continue
        except Exception as e:
            logger.info(f"Browser compatibility check failed: {e}")

        # Wait for page to load
        logger.info("Waiting for page elements to load...")
        try:
            await page.wait_for_selector(
                'input[type="email"], input[data-qa="signin_domain_input"]', timeout=30000
            )
            logger.info("Email input field found successfully")
        except Exception as e:
            logger.error(f"Failed to find email input: {e}")
            # Try to find any input field
            logger.info("Trying to find any input field...")
            try:
                await page.wait_for_selector('input', timeout=10000)
                logger.info("Found generic input field")
            except Exception as e2:
                logger.error(f"Failed to find any input field: {e2}")
                # Take screenshot for debugging
                await page.screenshot(path="slack_error_no_input.png")
                logger.info("Screenshot saved as slack_error_no_input.png")
                raise ValueError("Could not find email input field on Slack login page")
        logger.info("Page elements loaded successfully")

        # Check if we need to enter workspace domain first
        logger.info("Checking for workspace domain input...")
        domain_input = await page.query_selector('input[data-qa="signin_domain_input"]')
        if domain_input and await domain_input.is_visible():
            logger.info("Workspace domain input found, extracting workspace from email")
            # Extract workspace from email if provided
            if "@" in request.email:
                workspace = request.email.split("@")[1].split(".")[0]
                logger.info(f"Extracted workspace: {workspace}")
                await page.fill('input[data-qa="signin_domain_input"]', workspace)
                await page.click('button[data-qa="submit_team_domain_button"]')
                await page.wait_for_load_state("domcontentloaded")
                logger.info("Workspace domain submitted successfully")
        else:
            logger.info("No workspace domain input found, proceeding with email input")

        # Wait for email input
        logger.info("Waiting for email input field...")
        await page.wait_for_selector('input[type="email"]', timeout=10000)
        logger.info("Email input field found")

        # Check if email is already filled and fill if needed
        logger.info(f"Checking email field for: {request.email}")
        email_input = await page.query_selector('input[type="email"]')
        if email_input:
            current_value = await email_input.input_value()
            logger.info(f"Current email field value: '{current_value}'")
            
            if current_value.strip() != request.email.strip():
                logger.info(f"Filling email field with: {request.email}")
                await page.fill('input[type="email"]', request.email)
                logger.info("Email field filled successfully")
            else:
                logger.info("Email field already contains the correct email")
        else:
            logger.error("Email input field not found")
            raise ValueError("Email input field not found on Slack login page")
        
        # Handle reCAPTCHA - it often appears after user interaction
        logger.info("Checking for reCAPTCHA after email interaction...")
        await self._handle_recaptcha_if_present(page)

        # Check if passwordless login is available
        logger.info("Checking for passwordless login option...")
        passwordless_button = await page.query_selector(
            'button[data-qa="signin_send_confirmation_button"]'
        )
        if passwordless_button and await passwordless_button.is_visible():
            logger.info("Passwordless login button found")
            if not request.password:
                # Use passwordless login
                logger.info("No password provided, using passwordless login")
                await passwordless_button.click()
                logger.info("Passwordless login initiated. Check your email for the sign-in link.")
                await page.wait_for_timeout(5000)
                return
            else:
                logger.info("Password provided, continuing with password login")

        # Continue with password login
        logger.info("Looking for continue/next button...")
        
        # Try multiple button selectors
        button_selectors = [
            'button[data-qa="signin_email_button"]',
            'button:has-text("Continue")',
            'button:has-text("Sign In With Email")',
            'button[type="submit"]',
            'input[type="submit"]',
            'button[class*="signin"]',
            'button[class*="submit"]'
        ]
        
        next_button = None
        for selector in button_selectors:
            try:
                logger.info(f"Trying button selector: {selector}")
                button = await page.query_selector(selector)
                if button and await button.is_visible():
                    next_button = button
                    logger.info(f"Found button with selector: {selector}")
                    break
            except Exception as e:
                logger.info(f"Selector {selector} failed: {e}")
                continue
        
        if next_button:
            logger.info("Continue button found, clicking...")
            await next_button.click()
            await page.wait_for_load_state("domcontentloaded")
            logger.info("Continue button clicked successfully")
            
            # Check for reCAPTCHA after clicking continue
            logger.info("Checking for reCAPTCHA after clicking continue...")
            await self._handle_recaptcha_if_present(page)
        else:
            logger.info("No continue button found, trying Enter key")
            await page.press('input[type="email"]', "Enter")
            
            # Check for reCAPTCHA after pressing Enter
            logger.info("Checking for reCAPTCHA after pressing Enter...")
            await self._handle_recaptcha_if_present(page)

        # Wait for password field after reCAPTCHA is solved
        logger.info("Waiting for password input field after reCAPTCHA...")
        try:
            # Wait a bit for page to settle after reCAPTCHA
            await page.wait_for_timeout(2000)
            
            # Check current page state
            current_url = page.url
            page_title = await page.title()
            logger.info(f"Current URL after reCAPTCHA: {current_url}")
            logger.info(f"Current page title: {page_title}")
            
            # Take screenshot for debugging
            await page.screenshot(path="after_recaptcha.png")
            logger.info("Screenshot saved as after_recaptcha.png")
            
            # Try to find password field with multiple selectors
            password_selectors = [
                'input[type="password"]',
                'input[data-qa="signin_password_input"]',
                'input[name="password"]',
                'input[placeholder*="password" i]',
                'input[placeholder*="Password" i]'
            ]
            
            password_found = False
            for selector in password_selectors:
                try:
                    logger.info(f"Looking for password field with selector: {selector}")
                    await page.wait_for_selector(selector, timeout=5000)
                    logger.info(f"Password field found with selector: {selector}")
                    password_found = True
                    break
                except Exception as e:
                    logger.info(f"Password selector {selector} failed: {e}")
                    continue
            
            if not password_found:
                logger.error("Password field not found with any selector")
                
                # Debug: Log all input elements on the page
                all_inputs = await page.query_selector_all('input')
                logger.info(f"Found {len(all_inputs)} input elements on the page:")
                for i, input_el in enumerate(all_inputs):
                    try:
                        input_type = await input_el.get_attribute('type')
                        input_name = await input_el.get_attribute('name')
                        input_placeholder = await input_el.get_attribute('placeholder')
                        input_id = await input_el.get_attribute('id')
                        logger.info(f"Input {i}: type={input_type}, name={input_name}, placeholder={input_placeholder}, id={input_id}")
                    except Exception as e:
                        logger.info(f"Input {i}: error getting attributes: {e}")
                
                # Check if we're on a different page (success page?)
                if "slack.com" in current_url and ("/messages" in current_url or "/client" in current_url):
                    logger.info("Appears to be on Slack workspace page - login might be successful!")
                    return
                else:
                    # Check if we're on a 2FA page or other authentication step
                    page_content = await page.content()
                    if "two-factor" in page_content.lower() or "2fa" in page_content.lower():
                        logger.info("Appears to be on 2FA page - reCAPTCHA solved but 2FA required")
                        await self._handle_2fa(page, request)
                        return
                    elif "password" in page_content.lower():
                        logger.info("Page contains 'password' but field not found - might be a different form")
                        raise ValueError("Password field not found after reCAPTCHA solving")
                    else:
                        logger.info("Page doesn't seem to require password - might be successful")
                        return
                    
        except Exception as e:
            logger.error(f"Error waiting for password field: {e}")
            raise ValueError(f"Could not find password field after reCAPTCHA: {e}")

        if not request.password:
            logger.error("Password is required for this login method")
            raise ValueError("Password is required for this login method")

        # Fill password
        logger.info("Filling password field...")
        await page.fill('input[type="password"]', request.password)
        logger.info("Password field filled successfully")

        # Submit login form
        logger.info("Looking for submit button...")
        submit_button = await page.query_selector(
            'button[data-qa="signin_password_button"], button[type="submit"], button:has-text("Sign In")'
        )
        if submit_button:
            logger.info("Submit button found, clicking...")
            await submit_button.click()
            logger.info("Submit button clicked successfully")
        else:
            logger.info("No submit button found, using Enter key")
            await page.press('input[type="password"]', "Enter")

        # Wait for potential redirects
        logger.info("Waiting for potential redirects...")
        await page.wait_for_timeout(3000)
        logger.info("Slack login process completed")

    async def _handle_recaptcha_if_present(self, page: Page) -> None:
        """Handle reCAPTCHA if it appears on the page."""
        try:
            # Wait a bit for reCAPTCHA to potentially appear after user interaction
            await page.wait_for_timeout(2000)
            
            # Check for reCAPTCHA indicators
            recaptcha_indicators = [
                'iframe[src*="recaptcha"]',
                '.g-recaptcha',
                '[data-sitekey]',
                'div[class*="recaptcha"]',
                'div[id*="recaptcha"]',
                'div[class*="recaptcha-checkbox"]',
                'span[class*="recaptcha-checkbox"]',
                'div[class*="g-recaptcha"]'
            ]
            
            recaptcha_found = False
            for indicator in recaptcha_indicators:
                element = await page.query_selector(indicator)
                if element and await element.is_visible():
                    recaptcha_found = True
                    logger.info(f"reCAPTCHA detected with selector: {indicator}")
                    break
            
            # Also check for "I'm not a robot" text
            if not recaptcha_found:
                try:
                    robot_text = await page.get_by_text("I'm not a robot").is_visible()
                    if robot_text:
                        recaptcha_found = True
                        logger.info("reCAPTCHA detected by 'I'm not a robot' text")
                except Exception:
                    pass
            
            if recaptcha_found:
                logger.info("reCAPTCHA detected - attempting automated solution...")
                await self._solve_recaptcha(page)
                logger.info("reCAPTCHA solved successfully!")
            else:
                logger.info("No reCAPTCHA detected")
        except Exception as e:
            logger.error(f"reCAPTCHA handling failed: {e}")
            raise ValueError(f"reCAPTCHA could not be solved automatically: {e}")

    async def _solve_recaptcha(self, page: Page) -> None:
        """Solve reCAPTCHA using automated 2captcha service."""
        if not CAPTCHA_AVAILABLE:
            logger.error("2captcha library not available - cannot solve reCAPTCHA automatically")
            raise ValueError("2captcha library not available - reCAPTCHA cannot be solved automatically")
        
        if not settings.captcha_2captcha or not settings.captcha_2captcha.strip():
            logger.error("2captcha API key not configured - cannot solve reCAPTCHA automatically")
            raise ValueError("2captcha API key not configured - reCAPTCHA cannot be solved automatically")
        
        logger.info("Using automated 2captcha service for reCAPTCHA solving...")
        await self._solve_recaptcha_with_2captcha(page)
        logger.info("reCAPTCHA solved successfully with 2captcha")

    async def _solve_recaptcha_with_2captcha(self, page: Page) -> None:
        """Solve reCAPTCHA using 2captcha async library."""
        try:
            logger.info("Initializing 2captcha async solver...")
            
            # Get the current URL and site key
            current_url = page.url
            logger.info(f"Current URL: {current_url}")
            
            # Find the reCAPTCHA site key with multiple methods
            site_key = await page.evaluate("""
                () => {
                    // Method 1: Direct data-sitekey attribute
                    let recaptchaElement = document.querySelector('[data-sitekey]');
                    if (recaptchaElement) {
                        return recaptchaElement.getAttribute('data-sitekey');
                    }
                    
                    // Method 2: Check iframe src for sitekey parameter
                    const iframe = document.querySelector('iframe[src*="recaptcha"]');
                    if (iframe) {
                        const src = iframe.src;
                        const match = src.match(/[?&]k=([^&]+)/);
                        if (match) {
                            return decodeURIComponent(match[1]);
                        }
                    }
                    
                    // Method 3: Check for grecaptcha widget
                    if (window.grecaptcha && window.grecaptcha.getResponse) {
                        const widgets = document.querySelectorAll('.g-recaptcha');
                        for (let widget of widgets) {
                            const sitekey = widget.getAttribute('data-sitekey');
                            if (sitekey) return sitekey;
                        }
                    }
                    
                    return null;
                }
            """)
            
            if not site_key:
                logger.error("Could not find reCAPTCHA site key")
                raise ValueError("reCAPTCHA site key not found")
            
            logger.info(f"Found reCAPTCHA site key: {site_key}")
            
            # Initialize 2captcha solver
            solver = TwoCaptcha(settings.captcha_2captcha)
            
            # Submit reCAPTCHA to 2captcha (run in thread pool to avoid blocking)
            logger.info("Submitting reCAPTCHA to 2captcha service...")
            result = await asyncio.get_event_loop().run_in_executor(
                None, 
                lambda: solver.recaptcha(sitekey=site_key, url=current_url)
            )

            logger.info(f"2captcha result: {result}")
            captcha_id = result['captchaId']
            
            # Wait for solution (run in thread pool to avoid blocking)
            logger.info("Waiting for 2captcha solution...")
            solution = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: solver.get_result(captcha_id)
            )
            logger.info(f"2captcha solution: {solution}")
            
            # Inject the solution into the page
            await page.evaluate(f"""
                () => {{
                    const responseElement = document.querySelector('[name="g-recaptcha-response"]');
                    if (responseElement) {{
                        responseElement.value = '{solution}';
                        responseElement.style.display = 'block';
                    }}
                    
                    // Trigger reCAPTCHA callback if it exists
                    if (window.grecaptcha && window.grecaptcha.getResponse) {{
                        const widgetId = window.grecaptcha.getResponse();
                        if (window.grecaptchaCallback) {{
                            window.grecaptchaCallback('{solution}');
                        }}
                    }}
                }}
            """)
            
            logger.info("reCAPTCHA solution injected successfully!")
            
            # Wait for page to potentially redirect or change after reCAPTCHA
            logger.info("Waiting for page to settle after reCAPTCHA solution...")
            await page.wait_for_timeout(3000)
            
            # Check if page has redirected
            new_url = page.url
            if new_url != current_url:
                logger.info(f"Page redirected after reCAPTCHA: {new_url}")
                # Check if we're on a success page
                if "slack.com" in new_url and ("/messages" in new_url or "/client" in new_url):
                    logger.info("Redirected to Slack workspace - login successful!")
                    return
            
        except Exception as e:
            logger.error(f"2captcha solving error: {e}")
            raise

    async def _handle_2fa(self, page: Page, request: LoginRequest) -> None:
        """Handle 2FA authentication."""
        logger.info("Handling 2FA authentication...")
        
        # Look for 2FA input field
        twofa_selectors = [
            'input[type="text"][placeholder*="code" i]',
            'input[type="text"][placeholder*="verification" i]',
            'input[type="text"][placeholder*="2fa" i]',
            'input[type="text"][placeholder*="two-factor" i]',
            'input[name*="code"]',
            'input[name*="verification"]',
            'input[id*="code"]',
            'input[id*="verification"]',
            'input[data-qa*="code"]',
            'input[data-qa*="verification"]'
        ]
        
        twofa_input = None
        for selector in twofa_selectors:
            try:
                logger.info(f"Looking for 2FA input with selector: {selector}")
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    twofa_input = element
                    logger.info(f"2FA input found with selector: {selector}")
                    break
            except Exception as e:
                logger.info(f"2FA selector {selector} failed: {e}")
                continue
        
        if not twofa_input:
            logger.error("2FA input field not found")
            raise ValueError("2FA input field not found")
        
        # Check if we have a 2FA code in the request
        if hasattr(request, 'otp_code') and request.otp_code:
            logger.info("Using provided 2FA code")
            await twofa_input.fill(request.otp_code)
        else:
            logger.error("2FA code not provided in request")
            raise ValueError("2FA code is required but not provided in request (use 'otp_code' field)")
        
        # Look for submit button
        submit_selectors = [
            'button[type="submit"]',
            'button:has-text("Verify")',
            'button:has-text("Submit")',
            'button:has-text("Continue")',
            'button[data-qa*="submit"]',
            'button[data-qa*="verify"]'
        ]
        
        submit_button = None
        for selector in submit_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    submit_button = element
                    logger.info(f"2FA submit button found with selector: {selector}")
                    break
            except Exception as e:
                logger.info(f"2FA submit selector {selector} failed: {e}")
                continue
        
        if submit_button:
            logger.info("Clicking 2FA submit button...")
            await submit_button.click()
            await page.wait_for_load_state("domcontentloaded")
            logger.info("2FA submit button clicked successfully")
        else:
            logger.info("No 2FA submit button found, trying Enter key")
            await page.press('input[type="text"]', "Enter")
        
        # Wait for potential redirects
        logger.info("Waiting for 2FA processing...")
        await page.wait_for_timeout(3000)
        logger.info("2FA handling completed")

    async def is_success(self, page: Page) -> bool:
        """Check if login was successful."""
        logger.info("Checking if Slack login was successful...")
        logger.info(f"Current URL: {page.url}")
        
        success_indicators = [
            # Slack workspace URL pattern
            lambda: "slack.com" in page.url and "/messages" in page.url,
            # Slack app elements
            lambda: page.query_selector('[data-qa="workspace_menu"]'),
            lambda: page.query_selector('[data-qa="channel_sidebar"]'),
            lambda: page.query_selector(".p-workspace__sidebar"),
            # Success page elements
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

        logger.warning("No success indicators matched. Login may have failed.")
        return False

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Slack session cookies."""
        logger.info("Extracting Slack session cookies...")
        browser_cookies = await page.context.cookies()
        logger.info(f"Found {len(browser_cookies)} total cookies")

        # Focus on important Slack cookies
        important_cookies = {"d", "b", "x", "session", "token"}

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
        return session_cookies
