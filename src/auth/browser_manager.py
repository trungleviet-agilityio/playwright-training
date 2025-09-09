"""Browser management for Playwright."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from playwright.async_api import Browser, Page, async_playwright

from ..config import settings


class BrowserManager:
    """Manages browser instances."""

    @asynccontextmanager
    async def get_page(self, headless: bool = None) -> AsyncGenerator[Page, None]:
        """Get a browser page with automatic cleanup."""
        if headless is None:
            headless = settings.headless

        # Ubuntu-optimized Chromium args
        browser_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-web-security",
            "--disable-infobars",
            "--disable-extensions",
            "--start-maximized",
            "--window-size=1280,720",
            "--disable-dev-shm-usage",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--disable-default-apps",
            "--disable-sync",
            "--disable-translate",
            "--hide-scrollbars",
            "--mute-audio",
            "--no-first-run",
            "--disable-logging",
            "--disable-gpu-logging",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-background-networking",
            "--disable-client-side-phishing-detection",
            "--disable-hang-monitor",
            "--disable-prompt-on-repost",
            "--metrics-recording-only",
            "--no-default-browser-check",
            "--safebrowsing-disable-auto-update",
            "--password-store=basic",
            "--use-mock-keychain",
            "--disable-component-extensions-with-background-pages",
            "--force-color-profile=srgb",
            "--memory-pressure-off",
            "--max_old_space_size=4096",
            "--disable-setuid-sandbox",
            "--disable-accelerated-2d-canvas",
            "--disable-accelerated-jpeg-decoding",
            "--disable-accelerated-mjpeg-decode",
            "--disable-accelerated-video-decode",
            "--disable-gpu-compositing",
            "--disable-gpu-rasterization",
            "--disable-gpu-sandbox",
            "--single-process",
        ]

        # Ubuntu-compatible user agent
        user_agent = (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        async with async_playwright() as p:
            # Prefer hosted browser if provided
            if settings.browser_ws_endpoint:
                browser = await p.chromium.connect_over_cdp(
                    settings.browser_ws_endpoint
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent=user_agent,
                    java_script_enabled=True,
                    accept_downloads=False,
                    ignore_https_errors=True,
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"Linux"',
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                    },
                )
            else:
                browser = await p.chromium.launch(headless=headless, args=browser_args)
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent=user_agent,
                    java_script_enabled=True,
                    accept_downloads=False,
                    ignore_https_errors=True,
                    extra_http_headers={
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept-Encoding": "gzip, deflate, br",
                        "Cache-Control": "no-cache",
                        "Pragma": "no-cache",
                        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        "Sec-Ch-Ua-Mobile": "?0",
                        "Sec-Ch-Ua-Platform": '"Linux"',
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                        "Upgrade-Insecure-Requests": "1",
                    },
                )

            # Simplified stealth script - no duplicate definitions
            await context.add_init_script(
                """
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Mock plugins only once
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format"},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        }
                    ],
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // Mock chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                // Mock platform
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Linux x86_64',
                });
                
                // Mock hardware concurrency
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 4,
                });
                
                // Mock device memory
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8,
                });
                
                // Remove automation indicators
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            """
            )

            page = await context.new_page()

            try:
                yield page
            finally:
                await context.close()
                # Only close when locally launched
                if not settings.browser_ws_endpoint:
                    await browser.close()
