"""Base classes for authentication strategies."""

import asyncio
from abc import ABC, abstractmethod
from typing import List, Tuple, Protocol, Optional
from playwright.async_api import Page
from ..models import LoginRequest, SessionCookie, AuthProvider


class CaptchaSolver(Protocol):
    """Protocol for CAPTCHA solving implementations."""
    async def solve(self, page: Page) -> bool: ...


class TwoFAStrategy(Protocol):
    """Protocol for 2FA handling implementations."""
    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool: ...


class ManualCaptchaSolver:
    """CAPTCHA solver that waits for manual intervention."""
    
    async def solve(self, page: Page) -> bool:
        """Wait for user to manually solve CAPTCHA."""
        if not await self._has_captcha(page):
            return True
            
        print("CAPTCHA detected. Please solve it manually in the browser...")
        
        # Wait up to 60 seconds for CAPTCHA to be solved
        for _ in range(60):
            await asyncio.sleep(1)
            if not await self._has_captcha(page):
                print("CAPTCHA solved successfully!")
                return True
        
        print("CAPTCHA solving timed out")
        return False
    
    async def _has_captcha(self, page: Page) -> bool:
        """Check if CAPTCHA is present."""
        captcha_selectors = [
            'iframe[src*="recaptcha"]',
            '.g-recaptcha',
            '.h-captcha',
            '[data-sitekey]',
            'div[class*="captcha"]',
            '[data-callback*="captcha"]',
            'div[id*="captcha"]',
            '.captcha',
            '[aria-label*="captcha"]'
        ]
        
        for selector in captcha_selectors:
            try:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return True
            except Exception:
                continue
        return False


class ManualTwoFAHandler:
    """2FA handler that waits for manual code entry."""
    
    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Wait for user to manually enter 2FA code."""
        if not await self._has_2fa(page):
            return True
            
        print(f"2FA required for {request.email}. Please enter the code manually...")
        
        # Wait up to 120 seconds for 2FA to be completed
        for _ in range(120):
            await asyncio.sleep(1)
            if not await self._has_2fa(page):
                print("2FA completed successfully!")
                return True
        
        print("2FA verification timed out")
        return False
    
    async def _has_2fa(self, page: Page) -> bool:
        """Check if 2FA is required."""
        twofa_selectors = [
            'input[placeholder*="code"]',
            'input[placeholder*="verification"]',
            'input[type="tel"][maxlength="6"]',
            'input[autocomplete="one-time-code"]',
            '[data-testid*="2fa"]',
            '[data-testid*="verification"]',
            '[data-testid*="totp"]',
            'text=Enter verification code',
            'text=Two-factor authentication',
            'text=Enter the 6-digit code',
            'text=Authentication required'
        ]
        
        for selector in twofa_selectors:
            try:
                if selector.startswith('text='):
                    element = page.get_by_text(selector[5:])
                    if await element.is_visible():
                        return True
                else:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        return True
            except Exception:
                continue
        return False


class NoopCaptchaSolver:
    """No-operation CAPTCHA solver that always succeeds."""
    async def solve(self, page: Page) -> bool:
        return True


class NoopTwoFA:
    """No-operation 2FA handler that always succeeds."""
    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        return True


class AuthStrategy(ABC):
    """Base authentication strategy with pluggable CAPTCHA and 2FA support."""
    
    def __init__(
        self,
        captcha_solver: Optional[CaptchaSolver] = None,
        twofa_strategy: Optional[TwoFAStrategy] = None,
    ) -> None:
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
            'text=Invalid credentials',
            'text=Login failed',
            'text=Incorrect email or password',
            'text=Authentication failed',
            '[data-testid*="error"]',
            '.error',
            '.alert-error'
        ]
        
        for selector in error_indicators:
            try:
                if selector.startswith('text='):
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
            if any(keyword in cookie['name'].lower() for keyword in ['session', 'auth', 'token', 'sid']):
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
            current_domain = page.url.split('//')[1].split('/')[0]
            for cookie in browser_cookies:
                if current_domain in cookie['domain']:
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

    async def handle_2fa(self, page: Page, request: LoginRequest) -> bool:
        """Handle 2FA if required."""
        return await self.twofa_strategy.handle_2fa(page, request)

    async def authenticate(self, page: Page, request: LoginRequest) -> Tuple[bool, List[SessionCookie], str]:
        """Main authentication flow."""
        try:
            # Step 1: Perform login
            await self.login(page, request)
            
            # Step 2: Handle CAPTCHA
            if not await self.handle_captcha(page):
                return False, [], "CAPTCHA could not be solved"
            
            # Step 3: Handle 2FA
            if not await self.handle_2fa(page, request):
                return False, [], "2FA could not be completed"
            
            # Step 4: Check success
            if not await self.is_success(page):
                return False, [], "Login failed - invalid credentials or other error"
            
            # Step 5: Extract cookies
            cookies = await self.extract_cookies(page)
            if not cookies:
                return False, [], "No valid session cookies found"
            
            return True, cookies, "Login successful"
            
        except Exception as e:
            return False, [], f"Authentication error: {str(e)}"


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
            'input[placeholder*="Email"]'
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
                'input[placeholder*="Password"]'
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
            'button:has-text("Submit")'
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
            await page.press('input[type="password"]', 'Enter')
        except Exception:
            pass
