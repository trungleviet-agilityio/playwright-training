"""Compatibility layer for storage interface."""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from .factory import StorageFactory
from ..models import AuthSession, AuthProvider
from ..config import settings

logger = logging.getLogger(__name__)


class StorageAdapter:
    """Compatibility wrapper for storage implementations to match old interface."""
    
    def __init__(self, storage_type: str = None):
        """
        Initialize storage adapter.
        
        Args:
            storage_type: Type of storage to use. If None, uses settings.storage_type
        """
        self.storage_type = storage_type or settings.storage_type
        self._storage = StorageFactory.create_storage(self.storage_type)
        self._sessions: Dict[str, AuthSession] = {}
        
        logger.info(f"StorageAdapter initialized with type: {self.storage_type}")
        
        # Validate configuration
        if not StorageFactory.validate_storage_config(self.storage_type):
            logger.warning(f"Storage configuration validation failed for type: {self.storage_type}")
    
    def get_storage_info(self) -> Dict[str, Any]:
        """Get information about the current storage configuration."""
        return {
            "type": self.storage_type,
            "class": self._storage.__class__.__name__,
            "validated": StorageFactory.validate_storage_config(self.storage_type)
        }
    
    async def save_session(self, session: AuthSession) -> None:
        """Save an AuthSession object."""
        try:
            # Store in the new format
            await self._storage.store_session(
                session_id=session.session_id,
                provider=session.provider.value,
                cookies=session.cookies,
                metadata={
                    'user_email': session.user_email,
                    'oauth_tokens': session.oauth_tokens.dict() if session.oauth_tokens else None,
                    'created_at': session.created_at.isoformat(),
                    'expires_at': session.expires_at.isoformat(),
                    'last_used': session.last_used.isoformat() if session.last_used else None,
                    'is_active': session.is_active
                }
            )
            
            # Also store in memory for compatibility
            self._sessions[session.session_id] = session
            logger.info(f"Session {session.session_id} saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save session {session.session_id}: {e}")
            raise
    
    async def get_session(self, session_id: str) -> Optional[AuthSession]:
        """Get an AuthSession object."""
        try:
            # First check memory
            if session_id in self._sessions:
                return self._sessions[session_id]
            
            # Then check storage
            session_data = await self._storage.get_session(session_id)
            if session_data:
                # Convert back to AuthSession
                from ..models import SessionCookie, OAuthTokens
                
                cookies = []
                for cookie_data in session_data.get('cookies', []):
                    cookies.append(SessionCookie(
                        name=cookie_data['name'],
                        value=cookie_data['value'],
                        domain=cookie_data['domain'],
                        path=cookie_data.get('path', '/'),
                        secure=cookie_data.get('secure', False),
                        http_only=cookie_data.get('http_only', False)
                    ))
                
                oauth_tokens = None
                if session_data.get('metadata', {}).get('oauth_tokens'):
                    oauth_data = session_data['metadata']['oauth_tokens']
                    oauth_tokens = OAuthTokens(**oauth_data)
                
                session = AuthSession(
                    session_id=session_data['session_id'],
                    provider=AuthProvider(session_data['provider']),
                    user_email=session_data['metadata']['user_email'],
                    cookies=cookies,
                    oauth_tokens=oauth_tokens,
                    created_at=datetime.fromisoformat(session_data['metadata']['created_at']),
                    expires_at=datetime.fromisoformat(session_data['metadata']['expires_at']),
                    last_used=datetime.fromisoformat(session_data['metadata']['last_used']) if session_data['metadata'].get('last_used') else None,
                    is_active=session_data['metadata'].get('is_active', True)
                )
                
                # Cache in memory
                self._sessions[session_id] = session
                return session
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}")
            return None
    
    async def get_sessions_by_provider(self, provider: str) -> List[AuthSession]:
        """Get all sessions for a specific provider."""
        try:
            sessions = []
            active_sessions = await self._storage.list_active_sessions(provider)
            
            for session_data in active_sessions:
                session = await self.get_session(session_data['session_id'])
                if session:
                    sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get sessions by provider {provider}: {e}")
            return []
    
    async def get_sessions_by_email(self, email: str) -> List[AuthSession]:
        """Get all sessions for a specific email."""
        try:
            sessions = []
            active_sessions = await self._storage.list_active_sessions()
            
            for session_data in active_sessions:
                if session_data.get('metadata', {}).get('user_email') == email:
                    session = await self.get_session(session_data['session_id'])
                    if session:
                        sessions.append(session)
            
            return sessions
            
        except Exception as e:
            logger.error(f"Failed to get sessions by email {email}: {e}")
            return []
    
    async def update_session(self, session_id: str, updates: Dict[str, Any]) -> bool:
        """Update session data."""
        try:
            session = await self.get_session(session_id)
            if not session:
                return False
            
            # Update the session object
            for key, value in updates.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            
            # Save the updated session
            await self.save_session(session)
            return True
            
        except Exception as e:
            logger.error(f"Failed to update session {session_id}: {e}")
            return False
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        try:
            # Remove from memory
            if session_id in self._sessions:
                del self._sessions[session_id]
            
            # Remove from storage
            return await self._storage.delete_session(session_id)
            
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}")
            return False


# Backward compatibility alias
MockStorage = StorageAdapter