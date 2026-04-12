from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends
from backend.app.services.library import PaperLibrary
from backend.app.core.config import settings
from backend.app.core.auth import get_current_user
from backend.app.db.database import get_db
from backend.app.db.repositories import cost_repo

router = APIRouter()


@router.get("/health")
def health():
    # Absichtlich minimal – kein Leak von Provider-/Modell-Infos
    # an unauthentifizierte Clients.
    return {"status": "ok"}


@router.get("/stats")
def stats(user: dict = Depends(get_current_user)):
    """Interne Stats – nur für eingeloggte User."""
    library = PaperLibrary()
    base = library.get_stats()
    return {
        **base,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "reranker": settings.reranker,
    }


@router.get("/costs")
def get_costs(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return cost_repo.get_summary(db)
