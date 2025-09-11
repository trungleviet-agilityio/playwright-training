"""Data models for the POC."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel


class AuthProvider(str, Enum):
    """Supported authentication providers."""

    SLACK = "slack"
    #TODO: Add more providers here


class LoginRequest(BaseModel):
    """Login request model with OAuth2 support."""
    provider: AuthProvider
    email: str
    password: str
    headless: bool = True
    
    # Authentication mode
    auth_mode: str = "password"  # "password", "oauth2", "hybrid"
    
    # OAuth2 Configuration
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    redirect_uri: Optional[str] = None
    scopes: Optional[List[str]] = None
    state: Optional[str] = None  # OAuth2 state parameter
    
    # 2FA Configuration
    otp_code: Optional[str] = None
    totp_secret: Optional[str] = None  # TOTP secret for pyotp
    
    # Session Configuration
    session_reuse: bool = True
    session_timeout_minutes: Optional[int] = None
    
    # Browser Configuration
    user_agent: Optional[str] = None
    proxy_config: Optional[Dict[str, str]] = None
    
    # Browserbase Stealth Configuration
    stealth_mode: Optional[str] = None  # "basic", "advanced", or None for default
    advanced_stealth: Optional[bool] = None  # Enable Advanced Stealth Mode
    solve_captchas: Optional[bool] = None  # Enable/disable CAPTCHA solving
    captcha_image_selector: Optional[str] = None  # Custom CAPTCHA image selector
    captcha_input_selector: Optional[str] = None  # Custom CAPTCHA input selector
    use_proxies: Optional[bool] = None  # Enable proxy usage for better CAPTCHA success
    
    # Slack-specific Configuration
    workspace_url: Optional[str] = None  # Slack workspace URL (e.g., "company" for company.slack.com)
    team_id: Optional[str] = None  # Slack team ID for pre-selecting workspace


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
    path: str = "/"
    secure: bool = False
    http_only: bool = False


class OAuthTokens(BaseModel):
    """OAuth tokens for API access."""
    
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    expires_in: Optional[int] = None
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None
    
    # Additional OAuth metadata
    team_id: Optional[str] = None  # Slack team ID
    team_name: Optional[str] = None  # Slack team name
    user_id: Optional[str] = None  # User ID
    bot_user_id: Optional[str] = None  # Bot user ID
    app_id: Optional[str] = None  # App ID


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
