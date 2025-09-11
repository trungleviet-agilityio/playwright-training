"""Main FastAPI application for the Playwright Auth POC."""

import uuid
from datetime import datetime, timedelta
import logging
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .auth import AuthStrategyFactory
from .browser.manager import BrowserManager
from .config import settings
from .models import AuthProvider, LoginRequest, LoginResponse, AuthSession, OAuthTokens  # noqa: F401
from .storage.compatibility import MockStorage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create FastAPI app
app = FastAPI(
    title="Playwright Auth POC",
    description="Simple POC demonstrating authentication with Strategy and Factory patterns",
    version="0.1.0",
)

# Initialize components
browser_manager = BrowserManager()
auth_factory = AuthStrategyFactory()
storage = MockStorage()


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Playwright Authentication POC",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/providers")
async def get_providers():
    """Get supported authentication providers."""
    providers = auth_factory.get_supported_providers()
    return {"providers": [p.value for p in providers]}


@app.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate user with specified provider."""
    start_time = datetime.utcnow()

    try:
        # Create authentication strategy
        auth_strategy = auth_factory.create_strategy(request.provider)

        # Perform authentication with enhanced browser management
        async with browser_manager.get_page(
            headless=request.headless,
            captcha_solving=request.solve_captchas if request.solve_captchas is not None else True,
            browser_type=settings.browser_type,
            # Pass Browserbase-specific configuration
            captcha_image_selector=request.captcha_image_selector,
            captcha_input_selector=request.captcha_input_selector,
        ) as page:
            success, cookies, message, oauth_tokens = await auth_strategy.authenticate(page, request)

        # Calculate execution time
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds() * 1000

        if success:
            # Extract OAuth tokens if available
            access_token = oauth_tokens.access_token if oauth_tokens else None
            refresh_token = oauth_tokens.refresh_token if oauth_tokens else None
            token_type = oauth_tokens.token_type if oauth_tokens else None
            expires_in = oauth_tokens.expires_in if oauth_tokens else None

            # Update message for OAuth2 success
            if oauth_tokens:
                message = "Login successful (OAuth2 tokens acquired)"

            # Create and save session
            session_id = str(uuid.uuid4())
            session = AuthSession(
                session_id=session_id,
                provider=request.provider,
                user_email=request.email,
                cookies=cookies,
                oauth_tokens=oauth_tokens,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=1),
                last_used=datetime.utcnow(),
                is_active=True,
            )

            await storage.save_session(session)

            return LoginResponse(
                success=True,
                message=message,
                session_id=session_id,
                execution_time_ms=execution_time,
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                expires_in=expires_in,
            )
        else:
            return LoginResponse(
                success=False, message=message, execution_time_ms=execution_time
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds() * 1000

        return LoginResponse(
            success=False,
            message=f"Authentication error: {str(e)}",
            execution_time_ms=execution_time,
        )


@app.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get session information."""
    session = await storage.get_session(session_id)
    if session:
        return session.dict()
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/sessions/provider/{provider}")
async def get_sessions_by_provider(provider: str):
    """Get all sessions for a specific provider."""
    try:
        provider_enum = AuthProvider(provider)
        sessions = await storage.get_sessions_by_provider(provider_enum.value)
        return {"sessions": [session.dict() for session in sessions]}
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid provider: {provider}")


@app.get("/sessions/email/{email}")
async def get_sessions_by_email(email: str):
    """Get all sessions for a specific email."""
    sessions = await storage.get_sessions_by_email(email)
    return {"sessions": [session.dict() for session in sessions]}


@app.put("/session/{session_id}/refresh")
async def refresh_session(session_id: str):
    """Update session last_used timestamp."""
    success = await storage.update_session(session_id, {"last_used": datetime.utcnow()})
    if success:
        return {"message": "Session refreshed successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found or update failed")


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    success = await storage.delete_session(session_id)
    if success:
        return {"message": "Session deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Session not found or deletion failed")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
