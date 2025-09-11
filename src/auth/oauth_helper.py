"""OAuth helper functions."""

import logging
from typing import Optional, Dict
import httpx
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


async def exchange_code_for_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    extra: Optional[Dict[str, str]] = None,
) -> Dict:
    """Exchange authorization code for access token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if extra:
        data.update(extra)
    
    logger.info(f"Exchanging code for token at {token_url}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(token_url, data=data, headers={"Accept": "application/json"})
        resp.raise_for_status()
        result = resp.json()
        logger.info("Token exchange successful")
        return result


async def exchange_slack_code_for_token(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
) -> Dict:
    """Exchange Slack authorization code for tokens."""
    token_url = "https://slack.com/api/oauth.v2.access"
    
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    
    logger.info("Exchanging Slack code for tokens")
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(token_url, data=data, headers={"Accept": "application/json"})
        resp.raise_for_status()
        result = resp.json()
        
        if not result.get("ok"):
            error = result.get("error", "Unknown error")
            logger.error(f"Slack token exchange failed: {error}")
            raise Exception(f"Slack token exchange failed: {error}")
        
        logger.info("Slack token exchange successful")
        return result


def extract_code_from_url(url: str) -> Optional[str]:
    """Extract authorization code from callback URL."""
    qs = parse_qs(urlparse(url).query)
    codes = qs.get("code")
    return codes[0] if codes else None


def extract_error_from_url(url: str) -> Optional[str]:
    """Extract error from callback URL."""
    qs = parse_qs(urlparse(url).query)
    errors = qs.get("error")
    return errors[0] if errors else None
