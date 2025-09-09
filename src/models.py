"""Data models for the POC."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class AuthProvider(str, Enum):
    """Supported authentication providers."""

    ATLASSIAN = "atlassian"
    SLACK = "slack"
    GOOGLE = "google"
    MICROSOFT_365 = "microsoft_365"
    SALESFORCE = "salesforce"
    NOTION = "notion"
    GITHUB = "github"
    OKTA = "okta"


class LoginRequest(BaseModel):
    """Login request model."""
    provider: AuthProvider
    email: str
    password: str
    headless: bool = True
    # Optional OAuth mode (only if you have an app for the provider)
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: Optional[List[str]] = None
    # Optional direct OTP inputs (future 2FA extension)
    otp_code: Optional[str] = None
    otp_secret: Optional[str] = None  # use pyotp if provided


class LoginResponse(BaseModel):
    """Login response model."""
    success: bool
    message: str
    session_id: Optional[str] = None
    execution_time_ms: float
    # Optional tokens when OAuth flow is used
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None
    token_type: Optional[str] = None


class SessionCookie(BaseModel):
    """Browser session cookie."""

    name: str
    value: str
    domain: str


class OAuthTokens(BaseModel):
    """OAuth tokens for API access."""
    
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None


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
