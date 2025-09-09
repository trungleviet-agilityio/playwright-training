"""Mock storage implementation (simulating DynamoDB)."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from ..models import AuthSession


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
