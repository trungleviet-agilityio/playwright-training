"""Mock storage implementation for testing and development."""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from .base import SessionStorage
from src.models import SessionCookie
from src.config import settings

logger = logging.getLogger(__name__)


class MockSessionStorage(SessionStorage):
    """Mock implementation of session storage for testing."""

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    async def store_session(
        self, 
        session_id: str, 
        provider: str, 
        cookies: List[SessionCookie],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store session data in memory."""
        try:
            # Convert cookies to serializable format
            cookies_data = []
            for cookie in cookies:
                cookies_data.append({
                    'name': cookie.name,
                    'value': cookie.value,
                    'domain': cookie.domain,
                    'path': cookie.path,
                    'secure': cookie.secure,
                    'http_only': cookie.http_only
                })

            self.sessions[session_id] = {
                'session_id': session_id,
                'provider': provider,
                'cookies': cookies_data,
                'metadata': metadata or {},
                'created_at': datetime.utcnow().isoformat(),
                'last_accessed': datetime.utcnow().isoformat()
            }

            logger.info(f"Session {session_id} stored successfully in mock storage")
            return True

        except Exception as e:
            logger.error(f"Failed to store session {session_id} in mock storage: {e}")
            return False

    async def get_session(
        self, 
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve session data from memory."""
        try:
            if session_id not in self.sessions:
                logger.info(f"Session {session_id} not found in mock storage")
                return None

            session = self.sessions[session_id]
            
            # Update last accessed time
            session['last_accessed'] = datetime.utcnow().isoformat()
            
            logger.info(f"Session {session_id} retrieved successfully from mock storage")
            return session

        except Exception as e:
            logger.error(f"Failed to retrieve session {session_id} from mock storage: {e}")
            return None

    async def list_active_sessions(
        self, 
        provider: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List active sessions from memory."""
        try:
            current_time = datetime.utcnow()
            active_sessions = []
            
            for session in self.sessions.values():
                try:
                    last_accessed = datetime.fromisoformat(session['last_accessed'])
                    if current_time - last_accessed < timedelta(minutes=settings.session_timeout_minutes):
                        if provider is None or session['provider'] == provider:
                            active_sessions.append(session)
                except (KeyError, ValueError):
                    # Skip sessions with invalid timestamps
                    continue

            logger.info(f"Found {len(active_sessions)} active sessions in mock storage")
            return active_sessions

        except Exception as e:
            logger.error(f"Failed to list sessions from mock storage: {e}")
            return []

    async def delete_session(
        self, 
        session_id: str
    ) -> bool:
        """Delete session data from memory."""
        try:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Session {session_id} deleted successfully from mock storage")
                return True
            else:
                logger.info(f"Session {session_id} not found in mock storage")
                return False

        except Exception as e:
            logger.error(f"Failed to delete session {session_id} from mock storage: {e}")
            return False

    async def is_session_valid(
        self, 
        session_id: str
    ) -> bool:
        """Check if session is still valid."""
        session_data = await self.get_session(session_id)
        if not session_data:
            return False

        try:
            last_accessed = datetime.fromisoformat(session_data['last_accessed'])
            current_time = datetime.utcnow()
            return current_time - last_accessed < timedelta(minutes=settings.session_timeout_minutes)
        except (KeyError, ValueError):
            return False