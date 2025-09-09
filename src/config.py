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

    browser_ws_endpoint: str = "" # If provided, use this endpoint to connect to the browser

    class Config:
        env_file = ".env"


# Global settings instance
settings = Settings()
