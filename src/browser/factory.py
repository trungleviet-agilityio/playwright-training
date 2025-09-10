"""Factory for creating browser providers."""

from enum import Enum
from typing import Type, Dict
from .base import BrowserProvider
from .providers import LocalBrowserProvider, BrowserbaseProvider


class BrowserProviderType(str, Enum):
    """Browser provider types."""

    LOCAL = "local"
    BROWSERBASE = "browserbase"
    CUSTOM_CDP = "custom_cdp"


class BrowserProviderFactory:
    """Factory for creating browser providers."""

    _providers: Dict[BrowserProviderType, Type[BrowserProvider]] = {
        BrowserProviderType.LOCAL: LocalBrowserProvider,
        BrowserProviderType.BROWSERBASE: BrowserbaseProvider,
    }

    @classmethod
    def create_provider(cls, provider_type: BrowserProviderType) -> BrowserProvider:
        """Create a browser provider instance."""
        provider_class = cls._providers.get(provider_type)
        if not provider_class:
            raise ValueError(f"Unsupported browser provider: {provider_type}")
        return provider_class()
