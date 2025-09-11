"""Base storage interface for session management."""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime
from src.models import SessionCookie


class SessionStorage(ABC):
    """Abstract base class for session storage implementations."""

    @abstractmethod
    async def store_session(
        self, 
        session_id: str, 
        provider: str, 
        cookies: List[SessionCookie],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store session data."""
        pass

    @abstractmethod
    async def get_session(
        self, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve session data."""
        pass

    @abstractmethod
    async def list_active_sessions(
        self, 
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List active sessions."""
        pass

    @abstractmethod
    async def delete_session(
        self, 
        session_id: str
    ) -> bool:
        """Delete session data."""
        pass

    @abstractmethod
    async def is_session_valid(
        self, 
        session_id: str
    ) -> bool:
        """Check if session is still valid."""
        pass
