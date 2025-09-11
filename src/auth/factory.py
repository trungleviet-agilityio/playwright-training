"""Factory pattern for creating authentication strategies."""

import logging
from typing import Dict, Type, List, Optional

from ..models import AuthProvider
from .base import AuthStrategy, AuthMethod
from .providers import (
    SlackAuthStrategy,
    #TODO: Add more providers here

)


logger = logging.getLogger(__name__)


class AuthStrategyFactory:
    """Factory for creating authentication strategies with method support."""

    _strategies: Dict[AuthProvider, Type[AuthStrategy]] = {
        AuthProvider.SLACK: SlackAuthStrategy,
        # Focus on Slack only for now
    }

    @classmethod
    def create_strategy(cls, provider: AuthProvider, method: Optional[AuthMethod] = None) -> AuthStrategy:
        """Create an authentication strategy for the given provider and method."""
        strategy_class = cls._strategies.get(provider)
        
        if strategy_class is None:
            raise ValueError(f"Unsupported provider: {provider}")
        
        strategy = strategy_class()
        
        # Validate method support
        if method and not strategy.supports_method(method):
            raise ValueError(f"Provider {provider} does not support authentication method: {method}")
        
        logger.info(f"Created {strategy.__class__.__name__} for {provider}")
        return strategy

    @classmethod
    def create_strategy_by_method(cls, provider: AuthProvider, method: AuthMethod) -> AuthStrategy:
        """Create a strategy specifically for the given method."""
        return cls.create_strategy(provider, method)

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
    def get_providers_by_method(cls, method: AuthMethod) -> List[AuthProvider]:
        """Get providers that support the given authentication method."""
        supported_providers = []
        for provider in cls.get_supported_providers():
            if method in cls.get_supported_methods(provider):
                supported_providers.append(provider)
        return supported_providers

    @classmethod
    def register_strategy(cls, provider: AuthProvider, strategy_class: Type[AuthStrategy]) -> None:
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
                "supported_methods": [method.value for method in strategy.supported_methods],
                "default_method": strategy.default_method.value,
                "required_fields": {
                    method.value: strategy.get_required_fields(method) 
                    for method in strategy.supported_methods
                },
                "features": {
                    "oauth2": AuthMethod.OAUTH2 in strategy.supported_methods,
                    "google_auth": AuthMethod.GOOGLE in strategy.supported_methods,
                    "password_auth": AuthMethod.PASSWORD in strategy.supported_methods,
                    "hybrid_auth": AuthMethod.HYBRID in strategy.supported_methods,
                    "captcha_solving": "Browserbase automatic CAPTCHA solving",
                    "2fa_support": "PyOTP library for TOTP generation"
                }
            }
        except ValueError as e:
            return {"error": str(e)}
