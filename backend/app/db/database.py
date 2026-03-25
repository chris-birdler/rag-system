"""
SQLite Datenbankverbindung via SQLAlchemy.

Die DB Datei liegt in data/rag_system.db
→ überlebt Neustarts
→ wird durch Docker Volume persistiert
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os

if os.getenv("RENDER"):
    # Render: In-Memory SQLite
    DATABASE_URL = "sqlite://"
else:
    # Lokal: Persistente Datei
    DATABASE_URL = "sqlite:///data/rag_system.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite spezifisch
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

class Base(DeclarativeBase):
    pass

def get_db():
    """FastAPI Dependency – gibt DB Session zurück."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """Tabellen erstellen beim Start."""
    from backend.app.db import models  # noqa
    Base.metadata.create_all(bind=engine)
