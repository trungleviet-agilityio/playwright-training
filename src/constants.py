"""Constants for the application."""


# Slack URLs
SLACK_SIGNIN_URL = "https://slack.com/signin"
SLACK_OAUTH2_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"

# Slack Element Selectors
SLACK_EMAIL_SELECTORS = [
    'input[id="identifierId"]',  # Google OAuth email field
    'input[type="email"]',
    'input[name="identifier"]',
    'input[aria-label="Email or phone"]',  # Fallback for Google login
    'input[aria-label="Email"]',  # Another Google login variant
    'input[placeholder*="Email"]',
    'input[placeholder*="email"]',
    'input[name="email"]',
    'input[data-testid="identifier"]',  # Google OAuth test ID
    'input[autocomplete="username"]',  # Username autocomplete
]

SLACK_CONTINUE_BUTTON_SELECTORS = [
    'button[id="identifierNext"]',  # Google OAuth "Next" button
    'button:has-text("Next")',
    'button[type="submit"]',
    'button:has-text("Continue")',
    'button[id="passwordNext"]',
    'div[id="identifierNext"] button',  # Fallback for nested button
]

SLACK_PASSWORD_SELECTORS = [
    'input[type="password"]',
    'input[name="password"]',
    'input[id="password"]',
    'input[aria-label*="password"]',
    'input[aria-label*="Password"]',
]

SLACK_2FA_SELECTORS = [
    'input[id="totpPin"]',  # Google 2FA input
    'input[name="totp"]',
    'input[type="tel"]',
    'input[aria-label*="Verification code"]',
    'input[placeholder*="code"]',
]

# Timeouts (in milliseconds)
DEFAULT_TIMEOUT = 30000
