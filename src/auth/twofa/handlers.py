"""Enhanced 2FA handlers with better integration."""

import logging
import asyncio
from typing import Optional
from playwright.async_api import Page

from .base import TwoFAHandler
from .pyotp_handler import PyOTPHandler
from .manual_handler import ManualTwoFAHandler
from src.models import LoginRequest

logger = logging.getLogger(__name__)

# Export handlers for factory
__all__ = ['PyOTPHandler', 'ManualTwoFAHandler']
