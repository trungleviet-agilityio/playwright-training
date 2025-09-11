"""Factory for creating OAuth2 authentication strategies."""

import logging
from typing import Dict, Type, List

from ..models import AuthProvider
from .base import AuthStrategy, AuthMethod
from .providers import SlackAuthStrategy

logger = logging.getLogger(__name__)


class AuthStrategyFactory:
    """Factory for creating OAuth2 authentication strategies."""

    _strategies: Dict[AuthProvider, Type[AuthStrategy]] = {
        AuthProvider.SLACK: SlackAuthStrategy,
    }

    @classmethod
    def create_strategy(cls, provider: AuthProvider) -> AuthStrategy:
        """Create an authentication strategy for the given provider."""
        strategy_class = cls._strategies.get(provider)
        if not strategy_class:
            raise ValueError(f"Unsupported provider: {provider}")

        strategy = strategy_class()
        logger.info(f"Created {strategy.__class__.__name__} for {provider}")
        return strategy

    @classmethod
    def get_supported_providers(cls) -> List[AuthProvider]:
        """Get list of supported providers."""
        return list(cls._strategies.keys())

    @classmethod
    def get_supported_methods(cls, provider: AuthProvider) -> List[AuthMethod]:
        """Get supported authentication methods for a provider."""
        try:
            strategy = cls.create_strategy(provider)
            return strategy.supported_methods
        except ValueError:
            return []

    @classmethod
    def register_strategy(
        cls, provider: AuthProvider, strategy_class: Type[AuthStrategy]
    ) -> None:
        """Register a strategy for a provider."""
        cls._strategies[provider] = strategy_class
        logger.info(f"Registered strategy for {provider}: {strategy_class.__name__}")

    @classmethod
    def get_strategy_info(cls, provider: AuthProvider) -> Dict[str, any]:
        """Get information about a provider's strategy."""
        try:
            strategy = cls.create_strategy(provider)
            return {
                "provider": provider,
                "strategy_class": strategy.__class__.__name__,
                "supported_methods": [
                    method.value for method in strategy.supported_methods
                ],
                "default_method": strategy.default_method.value,
                "required_fields": {
                    method.value: strategy.get_required_fields(method)
                    for method in strategy.supported_methods
                },
                "features": {
                    "oauth2": True,
                    "2fa_support": "PyOTP library for TOTP generation",
                },
            }
        except ValueError as e:
            return {"error": str(e)}
