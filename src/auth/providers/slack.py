"""Slack authentication strategy."""

import asyncio
from typing import List, Tuple

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import SLACK_URL


class SlackAuthStrategy(AuthStrategy):
    """Slack authentication strategy with multiple login methods."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.SLACK

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Slack login."""
        # Navigate to Slack sign-in page
        await page.goto(SLACK_URL, wait_until="domcontentloaded")

        # Wait for page to load
        await page.wait_for_selector(
            'input[type="email"], input[data-qa="signin_domain_input"]', timeout=10000
        )

        # Check if we need to enter workspace domain first
        domain_input = await page.query_selector('input[data-qa="signin_domain_input"]')
        if domain_input and await domain_input.is_visible():
            # Extract workspace from email if provided
            if "@" in request.email:
                workspace = request.email.split("@")[1].split(".")[0]
                await page.fill('input[data-qa="signin_domain_input"]', workspace)
                await page.click('button[data-qa="submit_team_domain_button"]')
                await page.wait_for_load_state("domcontentloaded")

        # Wait for email input
        await page.wait_for_selector('input[type="email"]', timeout=10000)

        # Fill email
        await page.fill('input[type="email"]', request.email)

        # Check if passwordless login is available
        passwordless_button = await page.query_selector(
            'button[data-qa="signin_send_confirmation_button"]'
        )
        if passwordless_button and await passwordless_button.is_visible():
            if not request.password:
                # Use passwordless login
                await passwordless_button.click()
                print(
                    "Passwordless login initiated. Check your email for the sign-in link."
                )
                await page.wait_for_timeout(5000)
                return

        # Continue with password login
        next_button = await page.query_selector(
            'button[data-qa="signin_email_button"], button:has-text("Continue")'
        )
        if next_button and await next_button.is_visible():
            await next_button.click()
            await page.wait_for_load_state("domcontentloaded")

        # Wait for password field
        await page.wait_for_selector('input[type="password"]', timeout=10000)

        if not request.password:
            raise ValueError("Password is required for this login method")

        # Fill password
        await page.fill('input[type="password"]', request.password)

        # Submit login form
        submit_button = await page.query_selector(
            'button[data-qa="signin_password_button"], button[type="submit"], button:has-text("Sign In")'
        )
        if submit_button:
            await submit_button.click()
        else:
            await page.press('input[type="password"]', "Enter")

        # Wait for potential redirects
        await page.wait_for_timeout(3000)

    async def is_success(self, page: Page) -> bool:
        """Check if login was successful."""
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

        for indicator in success_indicators:
            try:
                result = await indicator()
                if result:
                    return True
            except:
                continue

        return False

    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract Slack session cookies."""
        browser_cookies = await page.context.cookies()

        # Focus on important Slack cookies
        important_cookies = {"d", "b", "x", "session", "token"}

        session_cookies = []
        for cookie in browser_cookies:
            # Include all slack.com cookies and important ones
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

        return session_cookies
