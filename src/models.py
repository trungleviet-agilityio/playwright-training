"""Models for the application."""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class AuthProvider(str, Enum):
    """Supported authentication providers."""

    SLACK = "slack"


class LoginRequest(BaseModel):
    """Login request model for Slack Google OAuth2."""

    provider: AuthProvider = AuthProvider.SLACK
    email: str
    password: Optional[str] = None  # Google account password
    headless: bool = True
    totp_secret: Optional[str] = None  # TOTP secret for PyOTP (Google 2FA)
    workspace_url: Optional[str] = (
        None  # Slack workspace URL (e.g., "company.slack.com")
    )
    team_id: Optional[str] = None  # Slack team ID
    state: Optional[str] = None  # OAuth state parameter


class LoginResponse(BaseModel):
    """Login response model."""

    success: bool
    message: str
    session_id: Optional[str] = None
    execution_time_ms: float
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: Optional[str] = None


class SessionCookie(BaseModel):
    """Browser session cookie."""

    name: str
    value: str
    domain: str
    path: str = "/"
    secure: bool = False
    http_only: bool = False


class OAuthTokens(BaseModel):
    """OAuth tokens for API access."""

    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    scope: Optional[str] = None
    team_id: Optional[str] = None  # Slack team ID
    team_name: Optional[str] = None  # Slack team name
    user_id: Optional[str] = None  # Slack user ID
    bot_user_id: Optional[str] = None  # Slack bot user ID
    app_id: Optional[str] = None  # Slack app ID


class AuthSession(BaseModel):
    """Authentication session."""

    session_id: str
    provider: AuthProvider
    user_email: str
    cookies: List[SessionCookie]
    oauth_tokens: Optional[OAuthTokens] = None
    created_at: datetime
    expires_at: datetime
    last_used: Optional[datetime] = None
    is_active: bool = True
