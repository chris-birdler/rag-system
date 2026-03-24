# backend/app/api/routes/health.py
from fastapi import APIRouter, Depends
from backend.app.services.library import PaperLibrary
from backend.app.core.config import settings
from backend.app.services.cost_tracker import CostTracker
from backend.app.core.auth import get_current_user

router = APIRouter()

@router.get("/health")
def health():
    return {
        "status": "ok",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "embedding_provider": settings.embedding_provider,
        "reranker": settings.reranker,
    }

@router.get("/stats")
def stats():
    library = PaperLibrary()
    return library.get_stats()

@router.get("/costs")
def get_costs(user: dict = Depends(get_current_user)):
    """API Kosten Übersicht."""
    tracker = CostTracker()
    return tracker.get_summary()