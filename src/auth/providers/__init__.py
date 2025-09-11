"""Authentication providers."""

from .slack import SlackAuthStrategy

__all__ = [
    "SlackAuthStrategy",
    #TODO: Add more providers here
]