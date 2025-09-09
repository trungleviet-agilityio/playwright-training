"""GitHub authentication strategy."""

from typing import List

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import GITHUB_URL


class GitHubAuthStrategy(AuthStrategy): 
    """GitHub authentication strategy."""
    
    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.GITHUB
    
    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform GitHub login."""
        # Navigate to GitHub sign-in
        await page.goto(GITHUB_URL, wait_until="domcontentloaded")
        
        # Wait for login form
        await page.wait_for_selector('input[name="login"]', timeout=10000)
        
        # Fill username/email
        await page.fill('input[name="login"]', request.email)
        
        if not request.password:
            raise ValueError("Password is required for GitHub login")
        
        # Fill password
        await page.fill('input[name="password"]', request.password)
        
        # Submit form
        await page.click('input[type="submit"], button[type="submit"]')
        
        # Wait for potential redirects or 2FA
        await page.wait_for_timeout(3000)
    
    async def is_success(self, page: Page) -> bool:
        """Check if GitHub login was successful."""
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
        
        for indicator in success_indicators:
            try:
                result = await indicator()
                if result:
                    return True
            except:
                continue
        
        return False
    
    async def extract_cookies(self, page: Page) -> List[SessionCookie]:
        """Extract GitHub session cookies."""
        browser_cookies = await page.context.cookies()
        
        # Focus on important GitHub cookies
        important_cookies = {'user_session', '_gh_sess', '__Host-user_session_same_site'}
        
        session_cookies = []
        for cookie in browser_cookies:
            # Include all github.com cookies and important ones
            if 'github.com' in cookie['domain'] or cookie['name'] in important_cookies:
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
