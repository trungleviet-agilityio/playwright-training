"""GitHub authentication strategy."""

import logging
from typing import List

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import GITHUB_URL

# Set up logger for this module
logger = logging.getLogger(__name__)


class GitHubAuthStrategy(AuthStrategy): 
    """GitHub authentication strategy."""
    
    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.GITHUB
    
    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform GitHub login."""
        logger.info(f"Starting GitHub authentication for email: {request.email}")
        
        # Navigate to GitHub sign-in
        logger.info(f"Navigating to GitHub URL: {GITHUB_URL}")
        await page.goto(GITHUB_URL, wait_until="domcontentloaded")
        logger.info("Successfully navigated to GitHub sign-in page")
        
        # Wait for login form
        logger.info("Waiting for login form...")
        await page.wait_for_selector('input[name="login"]', timeout=10000)
        logger.info("Login form found")
        
        # Fill username/email
        logger.info(f"Filling username/email field with: {request.email}")
        await page.fill('input[name="login"]', request.email)
        logger.info("Username/email field filled successfully")
        
        if not request.password:
            logger.error("Password is required for GitHub login")
            raise ValueError("Password is required for GitHub login")
        
        # Fill password
        logger.info("Filling password field...")
        await page.fill('input[name="password"]', request.password)
        logger.info("Password field filled successfully")
        
        # Submit form
        logger.info("Submitting login form...")
        await page.click('input[type="submit"], button[type="submit"]')
        logger.info("Login form submitted successfully")
        
        # Wait for potential redirects or 2FA
        logger.info("Waiting for potential redirects or 2FA...")
        await page.wait_for_timeout(3000)
        logger.info("GitHub login process completed")
    
    async def is_success(self, page: Page) -> bool:
        """Check if GitHub login was successful."""
        logger.info("Checking if GitHub login was successful...")
        logger.info(f"Current URL: {page.url}")
        
        success_indicators = [
            # GitHub dashboard
            lambda: "github.com" in page.url and "/dashboard" in page.url,
            # GitHub profile elements
            lambda: page.query_selector('[data-test-selector="nav-avatar"]'),
            lambda: page.query_selector('.Header-link--profile'),
            # Repository elements
            lambda: page.query_selector('[data-test-selector="dashboard"]'),
            lambda: page.get_by_text("Create repository").is_visible(),
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
        """Extract GitHub session cookies."""
        logger.info("Extracting GitHub session cookies...")
        browser_cookies = await page.context.cookies()
        logger.info(f"Found {len(browser_cookies)} total cookies")
        
        # Focus on important GitHub cookies
        important_cookies = {'user_session', '_gh_sess', '__Host-user_session_same_site'}
        
        session_cookies = []
        for cookie in browser_cookies:
            # Include all github.com cookies and important ones
            if 'github.com' in cookie['domain'] or cookie['name'] in important_cookies:
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
