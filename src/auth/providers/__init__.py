"""Authentication providers."""

from .slack import SlackAuthStrategy
from .google import GoogleAuthStrategy
from .github import GitHubAuthStrategy
from .microsoft_365 import Microsoft365AuthStrategy
from .salesforce import SalesforceAuthStrategy
from .notion import NotionAuthStrategy
from .atlassian import AtlassianAuthStrategy
from .okta import OktaAuthStrategy

__all__ = [
    "SlackAuthStrategy",
    "GoogleAuthStrategy",
    "GitHubAuthStrategy",
    "Microsoft365AuthStrategy",
    "SalesforceAuthStrategy",
    "NotionAuthStrategy",
    "AtlassianAuthStrategy",
    "OktaAuthStrategy",
]
