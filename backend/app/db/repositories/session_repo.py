"""
Session Repository – persistiert Konversations-History in SQLite.
Ersetzt den In-Memory SessionStore.
"""

from sqlalchemy.orm import Session
from backend.app.db.models import SessionMessage


def add_message(
    db: Session,
    username: str,
    role: str,
    content: str
) -> None:
    """Nachricht in DB speichern."""
    msg = SessionMessage(
        username=username,
        role=role,
        content=content
    )
    db.add(msg)
    db.commit()


def get_history(
    db: Session,
    username: str,
    max_messages: int = 20
) -> list[dict]:
    """
    History für User holen.
    Neueste max_messages Nachrichten.
    """
    messages = (
        db.query(SessionMessage)
        .filter(SessionMessage.username == username)
        .order_by(SessionMessage.timestamp.asc())
        .all()
    )

    # Nur die letzten max_messages behalten
    if len(messages) > max_messages:
        messages = messages[-max_messages:]

    return [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]


def clear_history(db: Session, username: str) -> None:
    """History für User löschen."""
    db.query(SessionMessage)\
      .filter(SessionMessage.username == username)\
      .delete()
    db.commit()


def get_stats(db: Session, username: str) -> dict:
    """Statistiken für eine Session."""
    count = (
        db.query(SessionMessage)
        .filter(SessionMessage.username == username)
        .count()
    )
    return {
        "messages": count,
        "session_exists": count > 0
    }
