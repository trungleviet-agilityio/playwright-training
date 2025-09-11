"""CAPTCHA solver implementations."""

from .browserbase_solver import BrowserbaseCaptchaSolver
from .manual_solver import ManualCaptchaSolver
from .noop_solver import NoopCaptchaSolver

__all__ = [
    "BrowserbaseCaptchaSolver",
    "ManualCaptchaSolver",
    "NoopCaptchaSolver",
]
