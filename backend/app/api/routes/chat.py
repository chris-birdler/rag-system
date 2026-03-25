# backend/app/api/routes/chat.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.app.services.rag_engine import RAGEngine
from backend.app.services.session_store import SessionStore
from backend.app.core.auth import get_current_user
from sqlalchemy.orm import Session
from backend.app.db.database import get_db
from backend.app.db.repositories import session_repo
from backend.app.db.repositories import cost_repo

router = APIRouter()

# Request/Response Modelle
class QuestionRequest(BaseModel):
    question: str
    use_expansion: bool = False
    n_chunks: int = 5

class AnswerResponse(BaseModel):
    question: str
    answer: str
    sources: list[dict]

# RAGEngine einmal erstellen – nicht bei jedem Request
engine = RAGEngine()
store = SessionStore(max_messages=20)

@router.post("/ask", response_model=AnswerResponse)
def ask(
    request: QuestionRequest,
    user: dict = Depends(get_current_user), # ← NEU
    db: Session = Depends(get_db)
):
    
    username = user["username"]

    # History für diesen User holen
    history = session_repo.get_history(db, username)

    result = engine.ask(
        question=request.question,
        history=history,
        use_expansion=request.use_expansion,
        n_chunks=request.n_chunks
    )

    # History in DB speichern
    session_repo.add_message(db, username, "user", request.question)
    session_repo.add_message(db, username, "assistant", result["answer"])

    return AnswerResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result["sources"]
    )


@router.delete("/history")
def clear_history(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session_repo.clear_history(db, user["username"])
    return {"message": "History cleared"}


@router.get("/history")
def get_history(
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    history = session_repo.get_history(db, user["username"])
    stats = session_repo.get_stats(db, user["username"])
    return {"history": history, "stats": stats}