"""Main FastAPI application for the Playwright Auth POC."""

import uuid
from datetime import datetime, timedelta
import logging
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .auth import AuthStrategyFactory, BrowserManager
from .config import settings
from .models import AuthProvider, LoginRequest, LoginResponse, AuthSession  # noqa: F401
from .storage import MockStorage

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

        # Perform authentication
        async with browser_manager.get_page(headless=request.headless) as page:
            success, cookies, message = await auth_strategy.authenticate(page, request)

        # Calculate execution time
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds() * 1000

        if success:
            access_token = None
            refresh_token = None
            token_type = None
            expires_in = None

            # Create and save session
            session_id = str(uuid.uuid4())
            session = AuthSession(
                session_id=session_id,
                provider=request.provider,
                user_email=request.email,
                cookies=cookies,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )

            await storage.save_session(session)

            if message.startswith("oauth_token:"):
                access_token = message.split("oauth_token:", 1)[1]
                message = "Login successful (OAuth token acquired)"

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
