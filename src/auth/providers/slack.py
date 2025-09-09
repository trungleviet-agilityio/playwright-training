"""Slack authentication strategy."""

import asyncio
import logging
from typing import List, Tuple

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import SLACK_URL

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
        
        # Navigate to Slack sign-in page
        logger.info(f"Navigating to Slack URL: {SLACK_URL}")
        await page.goto(SLACK_URL, wait_until="domcontentloaded")
        logger.info("Successfully navigated to Slack sign-in page")

        # Wait for page to load
        logger.info("Waiting for page elements to load...")
        await page.wait_for_selector(
            'input[type="email"], input[data-qa="signin_domain_input"]', timeout=10000
        )
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

        # Fill email
        logger.info(f"Filling email field with: {request.email}")
        await page.fill('input[type="email"]', request.email)
        logger.info("Email field filled successfully")

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
        next_button = await page.query_selector(
            'button[data-qa="signin_email_button"], button:has-text("Continue")'
        )
        if next_button and await next_button.is_visible():
            logger.info("Continue button found, clicking...")
            await next_button.click()
            await page.wait_for_load_state("domcontentloaded")
            logger.info("Continue button clicked successfully")
        else:
            logger.info("No continue button found, trying Enter key")

        # Wait for password field
        logger.info("Waiting for password input field...")
        await page.wait_for_selector('input[type="password"]', timeout=10000)
        logger.info("Password input field found")

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
