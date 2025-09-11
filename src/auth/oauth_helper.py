"""Helper functions for OAuth2 authentication."""

import logging
import httpx
from typing import Dict, Any, Optional
from src.config import settings

logger = logging.getLogger(__name__)

class OAuthError(Exception):
    """Custom OAuth error for better error handling."""
    pass

class TokenExchangeError(OAuthError):
    """Error during token exchange."""
    pass

async def exchange_slack_code_for_token(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Exchange Slack authorization code for tokens."""
    if not all([client_id, client_secret, redirect_uri, code]):
        raise TokenExchangeError("Missing required parameters for token exchange")

    token_url = "https://slack.com/api/oauth.v2.access"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }

    logger.info("Exchanging Slack code for tokens")

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                token_url,
                data=data,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "Cybernetika-Auth/1.0",
                },
            )
            resp.raise_for_status()
            result = resp.json()

            if not result.get("ok"):
                error = result.get("error", "Unknown error")
                raise TokenExchangeError(f"Slack token exchange failed: {error}")

            if not result.get("access_token"):
                raise TokenExchangeError("No access token in Slack response")

            logger.info("Slack token exchange successful")
            return result

    except httpx.TimeoutException:
        raise TokenExchangeError(f"Slack token exchange timed out after {timeout}s")
    except httpx.HTTPStatusError as e:
        raise TokenExchangeError(f"HTTP error {e.response.status_code}: {e.response.text}")
    except Exception as e:
        raise TokenExchangeError(f"Slack token exchange failed: {str(e)}")

def build_slack_authorize_url(
    client_id: str,
    redirect_uri: str,
    scopes: str = "channels:read,chat:write,users:read,team:read",
    team_id: Optional[str] = None,
    state: Optional[str] = None,
) -> str:
    """Build Slack authorization URL."""
    if not client_id:
        raise ValueError("SLACK_CLIENT_ID is required but not provided")
    
    base_url = "https://slack.com/oauth/v2/authorize"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
        "response_type": "code",
    }
    if team_id:
        params["team"] = team_id
    if state:
        params["state"] = state

    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    return f"{base_url}?{query_string}"
