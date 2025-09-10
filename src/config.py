"""Simple configuration for the Playwright POC."""

import os
from typing import Literal

class Settings:
    """Application settings using os.environ."""

    # Browser settings
    headless: bool = os.environ.get("HEADLESS", "true").lower() == "true"
    browser_type: Literal["chromium", "firefox", "webkit"] = os.environ.get("BROWSER_TYPE", "chromium")

    # API settings
    api_host: str = os.environ.get("API_HOST", "0.0.0.0")
    api_port: int = int(os.environ.get("API_PORT", "8000"))
    debug: bool = os.environ.get("DEBUG", "true").lower() == "true"

    # Test credentials (POC only)
    slack_test_email: str = os.environ.get("SLACK_TEST_EMAIL", "")
    slack_test_password: str = os.environ.get("SLACK_TEST_PASSWORD", "")

    # Browser configuration
    browser_ws_endpoint: str = os.environ.get("BROWSER_WS_ENDPOINT", "")

    # Browser provider settings
    browser_provider: Literal["local", "browserbase"] = os.environ.get("BROWSER_PROVIDER", "local")

    # Browserbase settings
    browserbase_api_key: str = os.environ.get("BROWSERBASE_API_KEY", "")
    browserbase_project_id: str = os.environ.get("BROWSERBASE_PROJECT_ID", "")
    browserbase_use_residential_proxy: bool = os.environ.get("BROWSERBASE_USE_RESIDENTIAL_PROXY", "true").lower() == "true"
    browserbase_captcha_solving: bool = os.environ.get("BROWSERBASE_CAPTCHA_SOLVING", "true").lower() == "true"

    # CAPTCHA solver preferences
    captcha_solver_preferences: list[str] = os.environ.get("CAPTCHA_SOLVER_PREFERENCES", "browserbase,manual").split(",")

    # Session management
    session_reuse_enabled: bool = os.environ.get("SESSION_REUSE_ENABLED", "true").lower() == "true"
    session_timeout_minutes: int = int(os.environ.get("SESSION_TIMEOUT_MINUTES", "60"))

    # Provider-specific configurations
    slack_workspace_url: str = os.environ.get("SLACK_WORKSPACE_URL", "")
    google_api_key: str = os.environ.get("GOOGLE_API_KEY", "")

    # Storage configuration
    storage_type: str = os.environ.get("STORAGE_TYPE", "mock")
    dynamodb_table_name: str = os.environ.get("DYNAMODB_TABLE_NAME", "auth-sessions")
    dynamodb_region: str = os.environ.get("DYNAMODB_REGION", "us-east-1")
    aws_access_key_id: str = os.environ.get("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key: str = os.environ.get("AWS_SECRET_ACCESS_KEY", "")

# Global settings instance
settings = Settings()
