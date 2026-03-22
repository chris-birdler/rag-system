# backend/app/api/routes/health.py
from fastapi import APIRouter
from backend.app.services.library import PaperLibrary
from backend.app.core.config import settings

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