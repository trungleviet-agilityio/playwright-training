"""Google authentication strategy."""

from typing import List

from playwright.async_api import Page

from src.models import AuthProvider, LoginRequest, SessionCookie
from src.auth.base import AuthStrategy
from src.constants import GOOGLE_URL


class GoogleAuthStrategy(AuthStrategy):
    """Google authentication strategy with enhanced stealth."""

    @property
    def provider(self) -> AuthProvider:
        return AuthProvider.GOOGLE

    async def login(self, page: Page, request: LoginRequest) -> None:
        """Perform Google login with enhanced anti-detection."""
        # Navigate to Google sign-in
        await page.goto(GOOGLE_URL, wait_until="domcontentloaded")

        # Wait for email input
        await page.wait_for_selector('input[type="email"]', timeout=10000)

        # Fill email with human-like typing
        await page.fill('input[type="email"]', request.email)
        await page.wait_for_timeout(500)

        # Click Next button
        next_button = await page.query_selector(
            'button:has-text("Next"), #identifierNext'
        )
        if next_button:
            await next_button.click()
        else:
            await page.press('input[type="email"]', "Enter")

        # Wait and check for security warnings
        await page.wait_for_timeout(2000)

        # Handle "Couldn't sign you in" warning
        try:
            if await page.get_by_text("Couldn't sign you in").is_visible():
                print("Google security warning detected!")
                try_again_link = await page.query_selector('a:has-text("Try again")')
                if try_again_link:
                    await try_again_link.click()
                    await page.wait_for_timeout(3000)
                else:
                    print("Could not find 'Try again' link")
        except:
            pass

        # Wait for password field
        await page.wait_for_selector('input[type="password"]', timeout=30000)

        if not request.password:
            raise ValueError("Password is required for Google login")

        # Fill password
        await page.fill('input[type="password"]', request.password)
        await page.wait_for_timeout(500)

        # Submit password
        password_next = await page.query_selector(
            'button:has-text("Next"), #passwordNext'
        )
        if password_next:
            await password_next.click()
        else:
            await page.press('input[type="password"]', "Enter")

        # Wait for potential redirects or additional verification
        await page.wait_for_timeout(5000)

    async def is_success(self, page: Page) -> bool:
        """Check if Google login was successful."""
        success_indicators = [
            # Google account page
            lambda: "myaccount.google.com" in page.url,
            # Google services page
            lambda: page.query_selector('[data-g-label="Account"]'),
            lambda: page.query_selector(".gb_A"),  # Google apps menu
            # Profile elements
            lambda: page.query_selector('[aria-label*="Google Account"]'),
            lambda: page.get_by_text("Welcome").is_visible(),
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
        """Extract Google session cookies."""
        browser_cookies = await page.context.cookies()

        # Focus on important Google cookies
        important_cookies = {
            "SID",
            "HSID",
            "SSID",
            "SAPISID",
            "APISID",
            "session_state",
        }

        session_cookies = []
        for cookie in browser_cookies:
            # Include all google.com cookies and important ones
            if "google.com" in cookie["domain"] or cookie["name"] in important_cookies:
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
