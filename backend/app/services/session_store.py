# backend/app/services/session_store.py

"""
Session Store – verwaltet Konversations-History pro User.

Aktuell: In-Memory (geht verloren bei Neustart)
Später:  Redis als Drop-in Replacement

Interface bleibt gleich – nur _store Implementierung tauschen.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Message:
    """Eine einzelne Nachricht im Gespräch."""
    role: str       # "user" oder "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Session:
    """
    Eine Konversations-Session pro User.
    Enthält die History der letzten N Nachrichten.
    """
    username: str
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)


class SessionStore:
    """
    Verwaltet Sessions für alle User.

    Interface:
        store.add_message(username, role, content)
        store.get_history(username) → list[dict]
        store.clear(username)
        store.get_session(username) → Session
    """

    def __init__(self, max_messages: int = 20):
        """
        max_messages: wie viele Nachrichten pro Session behalten.
        20 = 10 Frage-Antwort Paare.
        Ältere werden automatisch gelöscht.
        """
        self._sessions: dict[str, Session] = {}
        self._max_messages = max_messages

    def get_or_create_session(self, username: str) -> Session:
        """Session holen oder neu erstellen."""
        if username not in self._sessions:
            self._sessions[username] = Session(username=username)
        return self._sessions[username]

    def add_message(
        self,
        username: str,
        role: str,
        content: str
    ) -> None:
        """
        Nachricht zur Session hinzufügen.
        Älteste Nachricht wird gelöscht wenn max_messages erreicht.
        """
        session = self.get_or_create_session(username)
        session.messages.append(Message(role=role, content=content))
        session.last_active = datetime.utcnow()

        # Älteste Nachrichten löschen wenn zu viele
        # Immer paarweise löschen (User + Assistant)
        while len(session.messages) > self._max_messages:
            session.messages.pop(0)

    def get_history(self, username: str) -> list[dict]:
        """
        History als Liste von Dicts zurückgeben.
        Format passt direkt zum OpenAI messages Format.

        Returns:
            [
                {"role": "user", "content": "What is..."},
                {"role": "assistant", "content": "..."},
                ...
            ]
        """
        session = self._sessions.get(username)
        if not session:
            return []

        return [
            {"role": msg.role, "content": msg.content}
            for msg in session.messages
        ]

    def clear(self, username: str) -> None:
        """Session für einen User löschen."""
        if username in self._sessions:
            del self._sessions[username]

    def get_stats(self, username: str) -> dict:
        """Statistiken über eine Session."""
        session = self._sessions.get(username)
        if not session:
            return {"messages": 0, "session_exists": False}

        return {
            "messages": len(session.messages),
            "session_exists": True,
            "created_at": session.created_at.isoformat(),
            "last_active": session.last_active.isoformat(),
        }

    def get_all_stats(self) -> dict:
        """Statistiken über alle Sessions."""
        return {
            "total_sessions": len(self._sessions),
            "users": [
                {
                    "username": username,
                    **self.get_stats(username)
                }
                for username in self._sessions
            ]
        }