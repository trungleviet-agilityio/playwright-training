"""OAuth helper functions."""

from typing import Optional, Dict
import httpx
from urllib.parse import urlparse, parse_qs


async def exchange_code_for_token(
    token_url: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    extra: Optional[Dict[str, str]] = None,
) -> Dict:
    """Exchange code for token."""
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if extra:
        data.update(extra)
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(token_url, data=data, headers={"Accept": "application/json"})
        resp.raise_for_status()
        return resp.json()

def extract_code_from_url(url: str) -> Optional[str]:
    """Extract code from URL."""
    qs = parse_qs(urlparse(url).query)
    codes = qs.get("code")
    return codes[0] if codes else None
