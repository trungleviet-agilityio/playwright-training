"""Simple configuration for the Playwright POC."""

import os
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Browser settings
    headless: bool = True
    browser_type: Literal["chromium", "firefox", "webkit"] = "chromium"

    # API settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = True

    # Test credentials (POC only)
    slack_test_email: str = ""
    slack_test_password: str = ""

    # Browser configuration
    browser_ws_endpoint: str = "" # If provided, use this endpoint to connect to the browser
    
    # Provider-specific configurations
    slack_workspace_url: str = ""
    google_api_key: str = ""
    browserbase_api_key: str = ""
    captcha_2captcha: str = ""
    
    # Storage configuration
    storage_type: str = "mock"  # "mock" or "dynamodb"
    dynamodb_table_name: str = "auth-sessions"
    dynamodb_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    
    model_config = {
        "env_file": ".env",
        "extra": "ignore",  # Ignore extra fields from .env file
        "env_prefix": "",
        "case_sensitive": False
    }


# Global settings instance
settings = Settings()
