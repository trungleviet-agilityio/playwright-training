"""Factory pattern for creating authentication strategies."""

from typing import Dict, Type, List

from ..models import AuthProvider
from .base import AuthStrategy
from .providers import (
    SlackAuthStrategy,
    GoogleAuthStrategy,
    GitHubAuthStrategy,
    Microsoft365AuthStrategy,
    SalesforceAuthStrategy,
    NotionAuthStrategy,
    AtlassianAuthStrategy,
    OktaAuthStrategy,
)


class AuthStrategyFactory:
    """Factory for creating authentication strategies."""

    _strategies: Dict[AuthProvider, Type[AuthStrategy]] = {
        AuthProvider.SLACK: SlackAuthStrategy,
        AuthProvider.GOOGLE: GoogleAuthStrategy,
        AuthProvider.GITHUB: GitHubAuthStrategy,
        AuthProvider.MICROSOFT_365: Microsoft365AuthStrategy,
        AuthProvider.SALESFORCE: SalesforceAuthStrategy,
        AuthProvider.NOTION: NotionAuthStrategy,
        AuthProvider.ATLASSIAN: AtlassianAuthStrategy,
        AuthProvider.OKTA: OktaAuthStrategy,
        # TODO: Add more providers here
    }

    @classmethod
    def create_strategy(cls, provider: AuthProvider) -> AuthStrategy:
        """Create an authentication strategy for the given provider."""
        strategy_class = cls._strategies.get(provider)
        if strategy_class is None:
            raise ValueError(f"Unsupported provider: {provider}")
        return strategy_class()

    @classmethod
    def get_supported_providers(cls) -> List[AuthProvider]:
        """Get list of supported providers."""
        return list(cls._strategies.keys())
