"""Configuration for the application."""

import os
from typing import List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Settings:
    """Configuration for the Slack Google OAuth2 authentication POC."""

    # Browser settings
    headless: bool = os.environ.get("HEADLESS", "true").lower() == "true"
    browser_ws_endpoint: str = os.environ.get("BROWSER_WS_ENDPOINT", "")
    browser_provider: str = os.environ.get("BROWSER_PROVIDER", "browserbase")

    # API settings
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", "8000"))
    debug: bool = os.environ.get("DEBUG", "true").lower() == "true"

    # Browserbase settings
    browserbase_api_key: str = os.environ.get("BROWSERBASE_API_KEY", "")
    browserbase_project_id: str = os.environ.get("BROWSERBASE_PROJECT_ID", "")

    # Slack OAuth2 configuration
    slack_client_id: str = os.environ.get("SLACK_CLIENT_ID", "")
    slack_client_secret: str = os.environ.get("SLACK_CLIENT_SECRET", "")
    slack_redirect_uri: str = os.environ.get(
        "SLACK_REDIRECT_URI", "http://localhost:8000/auth/slack/callback"
    )
    slack_scopes: List[str] = os.environ.get(
        "SLACK_SCOPES", "channels:read,chat:write,users:read,team:read"
    ).split(",")

    # 2FA handler preferences
    twofa_handler_preferences: List[str] = os.environ.get(
        "TWOFA_HANDLER_PREFERENCES", "pyotp,manual"
    ).split(",")

    # Session management
    session_reuse_enabled: bool = (
        os.environ.get("SESSION_REUSE_ENABLED", "true").lower() == "true"
    )
    session_timeout_minutes: int = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "60"))

    # Storage configuration
    storage_type: str = os.environ.get("STORAGE_TYPE", "mock")
    dynamodb_table_name: str = os.environ.get("DYNAMODB_TABLE_NAME", "auth-sessions")
    dynamodb_region: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
    aws_access_key_id: str = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

# Global settings instance
settings = Settings()

# Debug logging for environment variables
import logging
logger = logging.getLogger(__name__)
logger.info(f"SLACK_CLIENT_ID loaded: {'***' if settings.slack_client_id else 'NOT SET'}")
logger.info(f"SLACK_CLIENT_SECRET loaded: {'***' if settings.slack_client_secret else 'NOT SET'}")
logger.info(f"BROWSERBASE_API_KEY loaded: {'***' if settings.browserbase_api_key else 'NOT SET'}")
