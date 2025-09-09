"""Mock storage implementation (simulating DynamoDB)."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from ..models import AuthSession, AuthProvider


class MockStorage:
    """Mock storage that simulates DynamoDB using local JSON file."""

    def __init__(self, storage_file: str = "sessions.json"):
        self.storage_file = Path(storage_file)

    async def save_session(self, session: AuthSession) -> bool:
        """Save authentication session."""
        try:
            sessions = await self._load_sessions()
            sessions[session.session_id] = session.dict()
            await self._save_sessions(sessions)
            return True
        except Exception:
            return False

    async def get_session(self, session_id: str) -> Optional[AuthSession]:
        """Get session by ID."""
        try:
            sessions = await self._load_sessions()
            session_data = sessions.get(session_id)
            if session_data:
                return AuthSession(**session_data)
            return None
        except Exception:
            return None

    async def _load_sessions(self) -> Dict:
        """Load sessions from file."""
        if not self.storage_file.exists():
            return {}

        try:
            with open(self.storage_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    async def _save_sessions(self, sessions: Dict) -> None:
        """Save sessions to file."""
        with open(self.storage_file, "w") as f:
            json.dump(sessions, f, default=str, indent=2)

    async def get_sessions_by_provider(self, provider: str) -> List[AuthSession]:
        """Get all sessions for a specific provider."""
        try:
            sessions = await self._load_sessions()
            provider_sessions = []
            for session_data in sessions.values():
                if session_data.get('provider') == provider:
                    provider_sessions.append(AuthSession(**session_data))
            return provider_sessions
        except Exception:
            return []

    async def get_sessions_by_email(self, email: str) -> List[AuthSession]:
        """Get all sessions for a specific email."""
        try:
            sessions = await self._load_sessions()
            email_sessions = []
            for session_data in sessions.values():
                if session_data.get('user_email') == email:
                    email_sessions.append(AuthSession(**session_data))
            return email_sessions
        except Exception:
            return []

    async def update_session(self, session_id: str, updates: Dict) -> bool:
        """Update session in storage."""
        try:
            sessions = await self._load_sessions()
            if session_id in sessions:
                session_data = sessions[session_id]
                # Update the session data
                for key, value in updates.items():
                    if key == 'last_used' and hasattr(value, 'isoformat'):
                        session_data[key] = value.isoformat()
                    elif key == 'oauth_tokens' and value is not None:
                        session_data[key] = value.dict() if hasattr(value, 'dict') else value
                    else:
                        session_data[key] = value
                
                sessions[session_id] = session_data
                await self._save_sessions(sessions)
                return True
            return False
        except Exception:
            return False

    async def delete_session(self, session_id: str) -> bool:
        """Delete session from storage."""
        try:
            sessions = await self._load_sessions()
            if session_id in sessions:
                del sessions[session_id]
                await self._save_sessions(sessions)
                return True
            return False
        except Exception:
            return False
