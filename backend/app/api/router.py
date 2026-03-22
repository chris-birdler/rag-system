# backend/app/api/router.py
from fastapi import APIRouter
from backend.app.api.routes import papers, chat, health, auth

router = APIRouter()
router.include_router(health.router, tags=["Health"])
router.include_router(papers.router, prefix="/papers", tags=["Papers"])
router.include_router(chat.router, prefix="/chat", tags=["Chat"])
router.include_router(auth.router, prefix="/auth", tags=["Auth"])