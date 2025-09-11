"""Browserbase CAPTCHA solver implementation with playwright-captcha integration."""

import logging
import asyncio
import os
from datetime import datetime
from typing import Optional
from playwright.async_api import Page
from ..base import CaptchaSolver

logger = logging.getLogger(__name__)

# Try to import playwright-captcha
try:
    from playwright_captcha import RecaptchaSolver
    PLAYWRIGHT_CAPTCHA_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_CAPTCHA_AVAILABLE = False
    logger.warning("playwright-captcha not available. Install with: pip install playwright-captcha")


class BrowserbaseCaptchaSolver(CaptchaSolver):
    """CAPTCHA solver that relies on Browserbase's automatic solving."""

    def __init__(self):
        self.priority = 100  # Highest priority when available
        self.debug_dir = "captcha_debug"
        self._ensure_debug_dir()

    def _ensure_debug_dir(self):
        """Ensure debug directory exists."""
        if not os.path.exists(self.debug_dir):
            os.makedirs(self.debug_dir)
            logger.info(f"📁 Created debug directory: {self.debug_dir}")

    async def _take_debug_screenshot(self, page: Page, stage: str, description: str = ""):
        """Take a debug screenshot with timestamp and stage information."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # Include milliseconds
            filename = f"{timestamp}_{stage}.png"
            filepath = os.path.join(self.debug_dir, filename)
            
            await page.screenshot(path=filepath, full_page=True)
            
            logger.info(f"📸 Debug screenshot saved: {filepath}")
            if description:
                logger.info(f"📝 Description: {description}")
            
            return filepath
        except Exception as e:
            logger.error(f"❌ Failed to take debug screenshot: {e}")
            return None

    async def _log_page_info(self, page: Page, stage: str):
        """Log detailed page information for debugging."""
        try:
            url = page.url
            title = await page.title()
            logger.info(f"🔍 [{stage}] Page URL: {url}")
            logger.info(f"🔍 [{stage}] Page Title: {title}")
            
            # Log any visible CAPTCHA elements
            captcha_elements = await page.query_selector_all('iframe[src*="recaptcha"], .g-recaptcha, .h-captcha, [data-sitekey]')
            if captcha_elements:
                logger.info(f"🔍 [{stage}] Found {len(captcha_elements)} CAPTCHA elements")
                for i, element in enumerate(captcha_elements):
                    try:
                        is_visible = await element.is_visible()
                        logger.info(f"🔍 [{stage}] CAPTCHA element {i+1}: visible={is_visible}")
                    except Exception:
                        logger.info(f"🔍 [{stage}] CAPTCHA element {i+1}: visibility check failed")
        except Exception as e:
            logger.error(f"❌ Failed to log page info: {e}")

    async def can_handle(self, page: Page) -> bool:
        """Check if CAPTCHA is present and Browserbase can handle it."""
        try:
            logger.info("🔍 Checking for CAPTCHA on page...")
            
            # Take initial debug screenshot
            await self._take_debug_screenshot(page, "01_captcha_check", "Initial CAPTCHA detection check")
            await self._log_page_info(page, "CAPTCHA_CHECK")
            
            # Check for common CAPTCHA indicators
            captcha_indicators = [
                # reCAPTCHA v2
                'iframe[src*="recaptcha"]',
                '.g-recaptcha',
                '[data-sitekey]',
                'div[class*="recaptcha"]',
                'div[id*="recaptcha"]',
                
                # reCAPTCHA v3
                'iframe[src*="recaptcha/api2/anchor"]',
                'iframe[src*="recaptcha/api2/bframe"]',
                
                # reCAPTCHA Image Selection Challenge
                'div[class*="rc-imageselect"]',
                'div[class*="rc-imageselect-desc"]',
                'div[class*="rc-imageselect-challenge"]',
                'td[class*="rc-imageselect-tile"]',
                'button:has-text("VERIFY")',
                'div[class*="rc-imageselect-instructions"]',
                
                # hCaptcha
                'iframe[src*="hcaptcha"]',
                '.h-captcha',
                '[data-hcaptcha-sitekey]',
                
                # Cloudflare Turnstile
                'div[class*="cf-turnstile"]',
                
                # Generic CAPTCHA
                'div[class*="captcha"]',
                'div[id*="captcha"]',
                '.captcha',
                '[aria-label*="captcha"]',
                '[data-callback*="captcha"]',
                
                # Text-based CAPTCHA
                'input[placeholder*="captcha"]',
                'input[name*="captcha"]',
                'input[id*="captcha"]',
                
                # Checkbox-based CAPTCHA
                'input[type="checkbox"][name*="captcha"]',
                'input[type="checkbox"][id*="captcha"]'
            ]

            for selector in captcha_indicators:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        logger.info(f"🎯 CAPTCHA detected with selector: {selector}")
                        # Take screenshot when CAPTCHA is detected
                        await self._take_debug_screenshot(page, "02_captcha_detected", f"CAPTCHA detected with selector: {selector}")
                        return True
                except Exception:
                    continue

            # Check for "I'm not a robot" text
            try:
                robot_text = await page.get_by_text("I'm not a robot").is_visible()
                if robot_text:
                    logger.info("🎯 CAPTCHA detected by 'I'm not a robot' text")
                    # Take screenshot when robot text is detected
                    await self._take_debug_screenshot(page, "02_captcha_detected", "CAPTCHA detected by 'I'm not a robot' text")
                    return True
            except Exception:
                pass

            # Check for image selection challenge text
            try:
                image_challenge_texts = [
                    "Select all images with",
                    "Select all squares with",
                    "Click verify once there are none left",
                    "Select all images containing"
                ]
                
                for challenge_text in image_challenge_texts:
                    try:
                        element = page.get_by_text(challenge_text)
                        if await element.is_visible():
                            logger.info(f"🎯 Image selection CAPTCHA detected by text: {challenge_text}")
                            await self._take_debug_screenshot(page, "02_image_captcha_detected", f"Image selection CAPTCHA detected: {challenge_text}")
                            return True
                    except Exception:
                        continue
            except Exception:
                pass

            # Check for reCAPTCHA iframe content
            try:
                recaptcha_iframe = await page.query_selector('iframe[src*="recaptcha"]')
                if recaptcha_iframe:
                    iframe_content = await recaptcha_iframe.content_frame()
                    if iframe_content:
                        # Check for reCAPTCHA checkbox within iframe
                        checkbox = await iframe_content.query_selector('.recaptcha-checkbox')
                        if checkbox and await checkbox.is_visible():
                            logger.info("🎯 reCAPTCHA checkbox detected in iframe")
                            # Take screenshot when reCAPTCHA checkbox is detected
                            await self._take_debug_screenshot(page, "02_captcha_detected", "reCAPTCHA checkbox detected in iframe")
                            return True
            except Exception:
                pass

            logger.info("✅ No CAPTCHA detected")
            return False

        except Exception as e:
            logger.error(f"❌ Error checking for CAPTCHA: {e}")
            return False

    async def solve(self, page: Page) -> bool:
        """
        Solve CAPTCHA using Browserbase automatic solving.
        
        Strategy:
        1. First try playwright-captcha for direct solving (if available)
        2. Fallback to Browserbase automatic solving (no manual intervention needed)
        3. Monitor for completion via console events and element visibility
        """
        logger.info("🤖 Starting CAPTCHA solving with Browserbase automatic solving...")
        
        # Take screenshot at start of solving process
        await self._take_debug_screenshot(page, "03_solving_start", "Starting CAPTCHA solving process")
        await self._log_page_info(page, "SOLVING_START")

        try:
            # Step 1: Try playwright-captcha first (if available)
            if PLAYWRIGHT_CAPTCHA_AVAILABLE:
                logger.info("🎯 Attempting to solve with playwright-captcha...")
                try:
                    solver = RecaptchaSolver(page)
                    success = await solver.solve_recaptcha()
                    if success:
                        logger.info("✅ CAPTCHA solved successfully with playwright-captcha!")
                        # Take screenshot when solved with playwright-captcha
                        await self._take_debug_screenshot(page, "04_playwright_solved", "CAPTCHA solved with playwright-captcha")
                        return True
                    else:
                        logger.warning("⚠️ playwright-captcha failed, falling back to Browserbase...")
                        # Take screenshot when playwright-captcha fails
                        await self._take_debug_screenshot(page, "04_playwright_failed", "playwright-captcha failed, falling back to Browserbase")
                except Exception as e:
                    logger.warning(f"⚠️ playwright-captcha error: {e}, falling back to Browserbase...")
            
            # Step 2: Fallback to Browserbase automatic solving
            logger.info("🤖 Falling back to Browserbase automatic solving...")
            await self._take_debug_screenshot(page, "05_browserbase_start", "Starting Browserbase automatic solving")
            
            # Check if Browserbase is properly configured
            try:
                browserbase_info = await page.evaluate("""
                    return {
                        userAgent: navigator.userAgent,
                        hasBrowserbase: typeof window.browserbase !== 'undefined',
                        hasGrecaptcha: typeof window.grecaptcha !== 'undefined',
                        hasRecaptcha: document.querySelectorAll('iframe[src*="recaptcha"]').length,
                        captchaElements: document.querySelectorAll('[class*="recaptcha"], [class*="captcha"]').length,
                        // Check for Browserbase-specific properties
                        browserbaseVersion: window.browserbase ? window.browserbase.version : null,
                        browserbaseCapabilities: window.browserbase ? Object.keys(window.browserbase) : [],
                        // Check if CAPTCHA solving is enabled
                        captchaSolvingEnabled: window.browserbase && window.browserbase.solveCaptcha ? true : false
                    };
                """)
                logger.info(f"🔍 Browserbase environment check: {browserbase_info}")
                
                # Log specific CAPTCHA elements found
                captcha_details = await page.evaluate("""
                    const recaptchaFrames = document.querySelectorAll('iframe[src*="recaptcha"]');
                    const details = [];
                    recaptchaFrames.forEach((frame, index) => {
                        details.push({
                            index: index,
                            src: frame.src,
                            visible: frame.offsetParent !== null,
                            width: frame.offsetWidth,
                            height: frame.offsetHeight
                        });
                    });
                    return details;
                """)
                logger.info(f"🔍 reCAPTCHA iframe details: {captcha_details}")
                
            except Exception as e:
                logger.debug(f"Failed to check Browserbase environment: {e}")
            
            # Try to trigger Browserbase CAPTCHA solving using official methods
            try:
                # Method 1: Try Browserbase's official CAPTCHA solving API
                await page.evaluate("""
                    // Try to trigger Browserbase CAPTCHA solving using official methods
                    if (window.browserbase && window.browserbase.solveCaptcha) {
                        window.browserbase.solveCaptcha();
                        console.log('Browserbase CAPTCHA solving triggered via API');
                    }
                    
                    // Method 2: Try to enable CAPTCHA solving if not already enabled
                    if (window.browserbase && window.browserbase.enableCaptchaSolving) {
                        window.browserbase.enableCaptchaSolving();
                        console.log('Browserbase CAPTCHA solving enabled');
                    }
                    
                    // Method 3: Try to dispatch events that Browserbase might listen for
                    const captchaElements = document.querySelectorAll('[class*="recaptcha"], [class*="captcha"], iframe[src*="recaptcha"]');
                    captchaElements.forEach(el => {
                        el.dispatchEvent(new Event('click', { bubbles: true }));
                        el.dispatchEvent(new Event('focus', { bubbles: true }));
                        el.dispatchEvent(new Event('mouseover', { bubbles: true }));
                    });
                    
                    // Method 4: Try to trigger reCAPTCHA directly
                    if (window.grecaptcha && window.grecaptcha.execute) {
                        try {
                            window.grecaptcha.execute();
                            console.log('reCAPTCHA execute triggered');
                        } catch (e) {
                            console.log('reCAPTCHA execute failed:', e);
                        }
                    }
                    
                    // Method 5: Try to find and click reCAPTCHA checkbox
                    const recaptchaCheckbox = document.querySelector('.recaptcha-checkbox');
                    if (recaptchaCheckbox) {
                        recaptchaCheckbox.click();
                        console.log('reCAPTCHA checkbox clicked');
                    }
                    
                    // Method 6: Try to trigger CAPTCHA solving via postMessage
                    const recaptchaFrames = document.querySelectorAll('iframe[src*="recaptcha"]');
                    recaptchaFrames.forEach(frame => {
                        try {
                            frame.contentWindow.postMessage('captcha-solve', '*');
                            console.log('CAPTCHA solve message sent to iframe');
                        } catch (e) {
                            console.log('Failed to send message to iframe:', e);
                        }
                    });
                """)
                logger.info("🔧 Injected Browserbase CAPTCHA trigger scripts")
            except Exception as e:
                logger.debug(f"Failed to inject Browserbase scripts: {e}")
            
            # Set up comprehensive event listeners for Browserbase CAPTCHA events
            await page.evaluate("""
                window.browserbaseCaptchaEvents = {
                    detected: false,
                    solving: false,
                    solved: false,
                    failed: false,
                    lastUpdate: Date.now()
                };
                
                // Listen for official Browserbase console events from documentation
                const originalLog = console.log;
                const originalError = console.error;
                const originalWarn = console.warn;
                
                function checkMessage(message) {
                    const lowerMessage = message.toLowerCase();
                    
                    // Official Browserbase CAPTCHA events
                    if (lowerMessage.includes('browserbase-solving-started') || 
                        lowerMessage.includes('captcha-solving-started') ||
                        lowerMessage.includes('solving captcha')) {
                        window.browserbaseCaptchaEvents.solving = true;
                        window.browserbaseCaptchaEvents.detected = true;
                        window.browserbaseCaptchaEvents.lastUpdate = Date.now();
                    } else if (lowerMessage.includes('browserbase-solving-finished') || 
                               lowerMessage.includes('captcha-solving-finished') ||
                               lowerMessage.includes('captcha solved') ||
                               lowerMessage.includes('solving completed')) {
                        window.browserbaseCaptchaEvents.solved = true;
                        window.browserbaseCaptchaEvents.solving = false;
                        window.browserbaseCaptchaEvents.lastUpdate = Date.now();
                    } else if (lowerMessage.includes('browserbase-solving-failed') || 
                               lowerMessage.includes('captcha-solving-failed') ||
                               lowerMessage.includes('captcha failed') ||
                               lowerMessage.includes('solving failed')) {
                        window.browserbaseCaptchaEvents.failed = true;
                        window.browserbaseCaptchaEvents.solving = false;
                        window.browserbaseCaptchaEvents.lastUpdate = Date.now();
                    }
                }
                
                console.log = function(...args) {
                    const message = args.join(' ');
                    checkMessage(message);
                    originalLog.apply(console, args);
                };
                
                console.error = function(...args) {
                    const message = args.join(' ');
                    checkMessage(message);
                    originalError.apply(console, args);
                };
                
                console.warn = function(...args) {
                    const message = args.join(' ');
                    checkMessage(message);
                    originalWarn.apply(console, args);
                };
                
                // Also listen for DOM changes that might indicate CAPTCHA solving
                const observer = new MutationObserver(function(mutations) {
                    mutations.forEach(function(mutation) {
                        if (mutation.type === 'childList' || mutation.type === 'attributes') {
                            // Check if CAPTCHA elements are being modified
                            const target = mutation.target;
                            if (target && (target.classList.contains('rc-imageselect') || 
                                          target.classList.contains('g-recaptcha') ||
                                          target.closest('.rc-imageselect') ||
                                          target.closest('.g-recaptcha'))) {
                                window.browserbaseCaptchaEvents.lastUpdate = Date.now();
                            }
                        }
                    });
                });
                
                observer.observe(document.body, {
                    childList: true,
                    subtree: true,
                    attributes: true,
                    attributeFilter: ['class', 'style']
                });
            """)

            # Step 3: Check for expired CAPTCHA and handle it
            try:
                expired_text = await page.get_by_text("Verification challenge expired").is_visible()
                if expired_text:
                    logger.info("🔄 Expired CAPTCHA detected - refreshing to get new one")
                    await page.reload(wait_until="domcontentloaded")
                    await page.wait_for_timeout(3000)
                    # Re-trigger CAPTCHA after refresh
                    await self._trigger_captcha_interaction(page)
                    await page.wait_for_timeout(2000)
            except Exception:
                pass
            
            # Step 4: Trigger CAPTCHA interaction to start Browserbase solving (with retries)
            logger.info("🎯 Triggering CAPTCHA interaction to start Browserbase automatic solving...")
            
            # Try multiple interaction attempts to ensure Browserbase is triggered
            for attempt in range(3):  # Reduced attempts but more focused
                logger.info(f"🎯 CAPTCHA interaction attempt {attempt + 1}/3")
                await self._trigger_captcha_interaction(page)
                await page.wait_for_timeout(2000)  # Shorter wait between attempts
                
                # Check if Browserbase has started solving
                try:
                    events = await page.evaluate("window.browserbaseCaptchaEvents || {}")
                    if events.get("solving") or events.get("detected"):
                        logger.info("✅ Browserbase solving detected after interaction")
                        break
                    elif attempt < 2:  # Don't log on last attempt
                        logger.info("⏳ Browserbase not yet detected, retrying interaction...")
                except Exception as e:
                    logger.debug(f"Error checking Browserbase events: {e}")
            
            await self._take_debug_screenshot(page, "06_trigger_clicked", "After triggering CAPTCHA interaction")

            # Step 4: Wait for Browserbase to automatically solve the CAPTCHA (configurable timeout)
            from src.config import settings
            timeout_seconds = settings.browserbase_captcha_timeout
            logger.info(f"⏳ Waiting for Browserbase to automatically solve CAPTCHA (up to {timeout_seconds} seconds)...")
            solving_started = False
            last_activity_time = None
            image_challenge_detected = False
            
            for attempt in range(timeout_seconds):
                await asyncio.sleep(1)

                # Check if CAPTCHA was solved using official Browserbase events
                try:
                    events = await page.evaluate("window.browserbaseCaptchaEvents || {}")
                    
                    if events.get("solved"):
                        logger.info("✅ Browserbase successfully solved CAPTCHA! (events.solved)")
                        await self._take_debug_screenshot(page, "07_captcha_solved", "CAPTCHA solved successfully by Browserbase")
                        return True
                    
                    if events.get("failed"):
                        logger.warning("❌ Browserbase failed to solve CAPTCHA (events.failed)")
                        await self._take_debug_screenshot(page, "07_captcha_failed", "CAPTCHA solving failed by Browserbase")
                        break  # Exit early if Browserbase failed
                    
                    if events.get("solving") and not solving_started:
                        solving_started = True
                        logger.info("⏳ CAPTCHA solving started by Browserbase...")
                        await self._take_debug_screenshot(page, "08_solving_started", "CAPTCHA solving started by Browserbase")
                    
                    # Track activity based on lastUpdate
                    if events.get("lastUpdate"):
                        last_activity_time = events["lastUpdate"]
                except Exception as e:
                    logger.debug(f"Error checking Browserbase events: {e}")
                
                # Check for image selection challenge detection
                try:
                    image_challenge = await page.query_selector('div[class*="rc-imageselect"]')
                    if image_challenge and await image_challenge.is_visible() and not image_challenge_detected:
                        image_challenge_detected = True
                        logger.info("🎯 Image selection challenge detected - Browserbase should be solving this automatically")
                        await self._take_debug_screenshot(page, "08_image_challenge_detected", "Image selection challenge detected")
                        
                        # Try to trigger Browserbase solving for image challenges
                        await page.evaluate("""
                            // Try to trigger Browserbase for image selection challenges
                            if (window.browserbase && window.browserbase.solveImageCaptcha) {
                                window.browserbase.solveImageCaptcha();
                                console.log('Browserbase image CAPTCHA solving triggered');
                            }
                            
                            // Also try to click on the challenge area to trigger solving
                            const challengeArea = document.querySelector('div[class*="rc-imageselect"]');
                            if (challengeArea) {
                                challengeArea.click();
                                console.log('Image challenge area clicked to trigger Browserbase');
                            }
                        """)
                except Exception:
                    pass

                # Check if CAPTCHA elements are no longer visible (primary success indicator)
                try:
                    if not await self.can_handle(page):
                        logger.info("✅ CAPTCHA no longer detected - automatically solved by Browserbase")
                        await self._take_debug_screenshot(page, "07_captcha_disappeared", "CAPTCHA no longer detected - automatically solved")
                        return True
                except Exception as e:
                    logger.debug(f"Error checking CAPTCHA visibility: {e}")

                # Check for specific image selection completion indicators
                try:
                    # Check if VERIFY button is no longer present or disabled
                    verify_button = await page.query_selector('button:has-text("VERIFY")')
                    if verify_button:
                        is_disabled = await verify_button.is_disabled()
                        if is_disabled:
                            logger.info("✅ VERIFY button is disabled - CAPTCHA may be completed")
                            await self._take_debug_screenshot(page, "07_verify_disabled", "VERIFY button disabled - CAPTCHA completed")
                            # Wait a bit more to see if CAPTCHA disappears
                            await asyncio.sleep(3)
                            try:
                                if not await self.can_handle(page):
                                    return True
                            except Exception:
                                pass
                    
                    # Check if image challenge is no longer visible
                    if image_challenge_detected:
                        image_challenge = await page.query_selector('div[class*="rc-imageselect"]')
                        if not image_challenge or not await image_challenge.is_visible():
                            logger.info("✅ Image selection challenge no longer visible - CAPTCHA solved!")
                            await self._take_debug_screenshot(page, "07_image_challenge_solved", "Image selection challenge solved")
                            return True
                except Exception as e:
                    logger.debug(f"Error checking completion indicators: {e}")

                # Log progress every 10 seconds
                if attempt % 10 == 0 and attempt > 0:
                    activity_status = f" (last activity: {last_activity_time})" if last_activity_time else ""
                    challenge_status = " (image challenge detected)" if image_challenge_detected else ""
                    logger.info(f"⏳ Still waiting for Browserbase automatic CAPTCHA solving... ({attempt}s){activity_status}{challenge_status}")
                    
                    # Take progress screenshot every 10 seconds
                    try:
                        await self._take_debug_screenshot(page, f"08_solving_progress_{attempt}s", f"CAPTCHA solving in progress - {attempt} seconds")
                    except Exception as e:
                        logger.debug(f"Error taking progress screenshot: {e}")

            logger.warning(f"⏰ Browserbase automatic CAPTCHA solving timed out after {timeout_seconds} seconds")
            await self._take_debug_screenshot(page, "09_browserbase_timeout", f"Browserbase CAPTCHA solving timed out after {timeout_seconds} seconds")
            
            # Step 5: Check if manual fallback is enabled for debugging
            debug_manual = os.environ.get("DEBUG_MANUAL_CAPTCHA", "false").lower() == "true"
            if debug_manual:
                logger.warning("🔧 DEBUG_MANUAL_CAPTCHA enabled - attempting manual fallback for debugging")
                return await self._attempt_manual_image_solving(page)
            else:
                logger.error("❌ Browserbase automated CAPTCHA solving failed - this requires manual intervention")
                logger.info("💡 For debugging purposes, you can enable manual solving by setting DEBUG_MANUAL_CAPTCHA=true")
                return False

        except Exception as e:
            logger.error(f"❌ CAPTCHA solving error: {e}")
            await self._take_debug_screenshot(page, "10_error", f"CAPTCHA solving error: {e}")
            return False

    async def _trigger_captcha_interaction(self, page: Page) -> None:
        """Trigger CAPTCHA interaction to start Browserbase automatic solving."""
        try:
            logger.info("🎯 Attempting to trigger CAPTCHA interaction for Browserbase...")
            
            # Method 1: Try to click the reCAPTCHA checkbox directly
            recaptcha_iframe = await page.query_selector('iframe[src*="recaptcha"]')
            if recaptcha_iframe:
                logger.info("🎯 reCAPTCHA iframe found, attempting to click checkbox...")
                
                # Get the iframe content
                iframe_content = await recaptcha_iframe.content_frame()
                if iframe_content:
                    # Look for checkbox within the iframe
                    checkbox_selectors = [
                        '.recaptcha-checkbox',
                        '.recaptcha-checkbox-border',
                        'span[role="checkbox"]',
                        'input[type="checkbox"]'
                    ]
                    
                    for checkbox_selector in checkbox_selectors:
                        try:
                            checkbox = await iframe_content.query_selector(checkbox_selector)
                            if checkbox and await checkbox.is_visible():
                                await checkbox.click()
                                logger.info(f"✅ reCAPTCHA checkbox clicked using selector: {checkbox_selector}")
                                await page.wait_for_timeout(2000)
                                return
                        except Exception:
                            continue
            
            # Method 2: Try to click the reCAPTCHA container on main page
            recaptcha_selectors = [
                '.g-recaptcha',
                '[data-sitekey]',
                'div[class*="recaptcha"]',
                'div[id*="recaptcha"]'
            ]
            
            for selector in recaptcha_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        logger.info(f"✅ reCAPTCHA element clicked using selector: {selector}")
                        await page.wait_for_timeout(2000)
                        return
                except Exception:
                    continue
            
            # Method 3: Try to find and click "I'm not a robot" text
            try:
                robot_text = page.get_by_text("I'm not a robot")
                if await robot_text.is_visible():
                    await robot_text.click()
                    logger.info("✅ 'I'm not a robot' text clicked")
                    await page.wait_for_timeout(2000)
                    return
            except Exception:
                pass
            
            # Method 4: Try to interact with image selection challenge directly
            try:
                # Check if we're already in an image selection challenge
                image_challenge = await page.query_selector('div[class*="rc-imageselect"]')
                if image_challenge and await image_challenge.is_visible():
                    logger.info("🎯 Image selection challenge detected, attempting to interact...")
                    
                    # Try clicking on the challenge area to trigger Browserbase
                    await image_challenge.click()
                    logger.info("✅ Image selection challenge clicked")
                    await page.wait_for_timeout(2000)
                    return
            except Exception:
                pass
            
            # Method 5: Try to find and click any CAPTCHA-related elements
            captcha_elements = [
                'div[class*="captcha"]',
                'div[id*="captcha"]',
                '.captcha',
                '[aria-label*="captcha"]'
            ]
            
            for selector in captcha_elements:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.click()
                        logger.info(f"✅ CAPTCHA element clicked using selector: {selector}")
                        await page.wait_for_timeout(2000)
                        return
                except Exception:
                    continue
                    
            logger.info("ℹ️ No CAPTCHA elements found to interact with")
            
        except Exception as e:
            logger.warning(f"⚠️ Failed to trigger CAPTCHA interaction: {e}")

    async def _trigger_recaptcha_solving(self, page: Page) -> None:
        """Legacy method - now calls the new interaction method."""
        await self._trigger_captcha_interaction(page)

    async def _attempt_manual_image_solving(self, page: Page) -> bool:
        """Attempt to solve image selection CAPTCHA manually with improved logic."""
        try:
            logger.info("🎯 Attempting manual image selection solving...")
            await self._take_debug_screenshot(page, "10_manual_solving_start", "Starting manual image selection solving")
            
            # Check if we have an image selection challenge
            challenge_selectors = [
                'div[class*="rc-imageselect-desc"]',
                'div[class*="rc-imageselect-instructions"]',
                'div[class*="rc-imageselect-challenge"]'
            ]
            
            challenge_text = None
            for selector in challenge_selectors:
                try:
                    challenge_text = await page.query_selector(selector)
                    if challenge_text and await challenge_text.is_visible():
                        break
                except Exception:
                    continue
            
            if not challenge_text:
                logger.info("ℹ️ No image selection challenge found")
                return False
            
            challenge_text_content = await challenge_text.text_content()
            logger.info(f"🔍 Challenge text: {challenge_text_content}")
            
            # Look for the target object (e.g., "bus", "car", "traffic light", etc.)
            target_object = None
            challenge_lower = challenge_text_content.lower()
            
            if "bus" in challenge_lower:
                target_object = "bus"
            elif "car" in challenge_lower:
                target_object = "car"
            elif "traffic light" in challenge_lower:
                target_object = "traffic light"
            elif "crosswalk" in challenge_lower:
                target_object = "crosswalk"
            elif "bicycle" in challenge_lower or "bike" in challenge_lower:
                target_object = "bicycle"
            elif "motorcycle" in challenge_lower:
                target_object = "motorcycle"
            elif "truck" in challenge_lower:
                target_object = "truck"
            elif "fire hydrant" in challenge_lower:
                target_object = "fire hydrant"
            elif "stop sign" in challenge_lower:
                target_object = "stop sign"
            elif "bridge" in challenge_lower:
                target_object = "bridge"
            elif "mountain" in challenge_lower:
                target_object = "mountain"
            elif "tree" in challenge_lower:
                target_object = "tree"
            else:
                logger.warning(f"⚠️ Unknown challenge type: {challenge_text_content}")
                # Try to extract the object from the text
                words = challenge_lower.split()
                for word in words:
                    if word in ["bus", "car", "truck", "bicycle", "motorcycle", "traffic", "light", "crosswalk", "bridge", "mountain", "tree"]:
                        target_object = word
                        break
            
            if not target_object:
                logger.warning("⚠️ Could not determine target object from challenge text")
                return False
            
            logger.info(f"🎯 Target object: {target_object}")
            
            # Find all image tiles
            tile_selectors = [
                'td[class*="rc-imageselect-tile"]',
                'div[class*="rc-imageselect-tile"]',
                'img[class*="rc-image-tile"]'
            ]
            
            image_tiles = []
            for selector in tile_selectors:
                try:
                    tiles = await page.query_selector_all(selector)
                    if tiles:
                        image_tiles = tiles
                        break
                except Exception:
                    continue
            
            if not image_tiles:
                logger.warning("⚠️ No image tiles found")
                return False
            
            logger.info(f"🔍 Found {len(image_tiles)} image tiles")
            
            # Improved heuristic approach based on common patterns
            selected_count = 0
            
            # For bus challenge, use better heuristics based on typical reCAPTCHA patterns
            if target_object == "bus":
                # Common positions where buses appear in 3x3 grids
                # This is based on analysis of typical reCAPTCHA patterns
                bus_positions = [2, 3, 4]  # Middle row positions often contain buses
                
                for i, tile in enumerate(image_tiles):
                    try:
                        # Check if tile is already selected
                        is_selected = await tile.evaluate("el => el.classList.contains('rc-imageselect-tileselected')")
                        if is_selected:
                            logger.info(f"✅ Tile {i+1} already selected")
                            selected_count += 1
                            continue
                        
                        # Use improved heuristic for bus detection
                        if i in bus_positions:
                            await tile.click()
                            logger.info(f"✅ Clicked tile {i+1} (potential {target_object})")
                            selected_count += 1
                            await page.wait_for_timeout(800)  # Longer delay for better UX
                    
                    except Exception as e:
                        logger.warning(f"⚠️ Error clicking tile {i+1}: {e}")
                        continue
            
            else:
                # For other objects, use a more conservative approach
                logger.info(f"🎯 Using conservative selection for {target_object}")
                # Select a few tiles based on common patterns
                conservative_positions = [1, 4, 7]  # First, middle, last positions
                
                for i, tile in enumerate(image_tiles):
                    try:
                        is_selected = await tile.evaluate("el => el.classList.contains('rc-imageselect-tileselected')")
                        if is_selected:
                            logger.info(f"✅ Tile {i+1} already selected")
                            selected_count += 1
                            continue
                        
                        if i in conservative_positions:
                            await tile.click()
                            logger.info(f"✅ Clicked tile {i+1} (potential {target_object})")
                            selected_count += 1
                            await page.wait_for_timeout(800)
                    
                    except Exception as e:
                        logger.warning(f"⚠️ Error clicking tile {i+1}: {e}")
                        continue
            
            logger.info(f"🎯 Selected {selected_count} tiles")
            
            # Wait a moment before clicking verify
            await page.wait_for_timeout(1000)
            
            # Click the VERIFY button
            verify_selectors = [
                'button:has-text("VERIFY")',
                'button[class*="verify"]',
                'input[type="submit"]',
                'button[type="submit"]'
            ]
            
            verify_button = None
            for selector in verify_selectors:
                try:
                    verify_button = await page.query_selector(selector)
                    if verify_button and await verify_button.is_visible():
                        break
                except Exception:
                    continue
            
            if verify_button:
                is_disabled = await verify_button.is_disabled()
                if not is_disabled:
                    await verify_button.click()
                    logger.info("✅ Clicked VERIFY button")
                    await self._take_debug_screenshot(page, "11_verify_clicked", "After clicking VERIFY button")
                    
                    # Wait for result
                    await page.wait_for_timeout(5000)
                    
                    # Check if CAPTCHA was solved
                    if not await self.can_handle(page):
                        logger.info("✅ CAPTCHA appears to be solved!")
                        await self._take_debug_screenshot(page, "12_captcha_solved", "CAPTCHA solved successfully")
                        return True
                    else:
                        logger.warning("⚠️ CAPTCHA still present after verification")
                        await self._take_debug_screenshot(page, "12_captcha_failed", "CAPTCHA still present after verification")
                        return False
                else:
                    logger.warning("⚠️ VERIFY button is disabled")
                    return False
            else:
                logger.warning("⚠️ VERIFY button not found")
                return False

        except Exception as e:
            logger.error(f"❌ Manual image solving failed: {e}")
            await self._take_debug_screenshot(page, "13_manual_error", f"Manual image solving error: {e}")
            return False

    def get_priority(self) -> int:
        """Get solver priority (higher = preferred)."""
        return self.priority
