"""Factory for creating 2FA handlers with fallback chain."""

from enum import Enum
from typing import List, Type, Dict, Optional
from .base import TwoFAHandler
from .handlers import (
    PyOTPHandler,
    ManualTwoFAHandler,
)
from src.config import settings
import logging

logger = logging.getLogger(__name__)


class TwoFAHandlerType(str, Enum):
    """2FA handler types."""

    PYOTP = "pyotp"
    MANUAL = "manual"


class TwoFAHandlerFactory:
    """Factory for creating 2FA handlers with fallback chain."""

    _handlers: Dict[TwoFAHandlerType, Type[TwoFAHandler]] = {
        TwoFAHandlerType.PYOTP: PyOTPHandler,
        TwoFAHandlerType.MANUAL: ManualTwoFAHandler,
    }

    @classmethod
    def create_handler_chain(
        cls, preferred_handlers: Optional[List[TwoFAHandlerType]] = None
    ) -> List[TwoFAHandler]:
        """Create a chain of 2FA handlers with fallback."""
        if preferred_handlers is None:
            # Use configuration-based preferences
            preferred_handlers = []
            for handler_name in settings.twofa_handler_preferences:
                try:
                    handler_type = TwoFAHandlerType(handler_name)
                    preferred_handlers.append(handler_type)
                except ValueError:
                    logger.warning(f"Unknown 2FA handler type: {handler_name}")

        handlers = []
        for handler_type in preferred_handlers:
            handler_class = cls._handlers.get(handler_type)
            if handler_class:
                try:
                    handler = handler_class()
                    handlers.append(handler)
                    logger.info(f"Created 2FA handler: {handler_type.value}")
                except Exception as e:
                    logger.error(
                        f"Failed to create 2FA handler {handler_type.value}: {e}"
                    )

        # Sort by priority (higher = preferred)
        return sorted(handlers, key=lambda h: h.get_priority(), reverse=True)

    @classmethod
    def create_handler(cls, handler_type: TwoFAHandlerType) -> Optional[TwoFAHandler]:
        """Create a specific 2FA handler."""
        handler_class = cls._handlers.get(handler_type)
        if not handler_class:
            logger.error(f"Unknown 2FA handler type: {handler_type}")
            return None

        try:
            handler = handler_class()
            logger.info(f"Created 2FA handler: {handler_type.value}")
            return handler
        except Exception as e:
            logger.error(f"Failed to create 2FA handler {handler_type.value}: {e}")
            return None

    @classmethod
    def get_available_handlers(cls) -> List[TwoFAHandlerType]:
        """Get list of available 2FA handler types."""
        return list(cls._handlers.keys())

    @classmethod
    def get_handler_info(cls, handler_type: TwoFAHandlerType) -> Dict[str, any]:
        """Get information about a 2FA handler."""
        handler_class = cls._handlers.get(handler_type)
        if not handler_class:
            return {"error": f"Unknown handler type: {handler_type}"}

        try:
            handler = handler_class()
            return {
                "type": handler_type.value,
                "class": handler_class.__name__,
                "priority": handler.get_priority(),
                "available": True,
            }
        except Exception as e:
            return {
                "type": handler_type.value,
                "class": handler_class.__name__,
                "priority": 0,
                "available": False,
                "error": str(e),
            }
