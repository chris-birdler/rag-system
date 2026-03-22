# backend/app/api/routes/chat.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.app.services.rag_engine import RAGEngine
from backend.app.services.session_store import SessionStore
from backend.app.core.auth import get_current_user

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
    user: dict = Depends(get_current_user)  # ← NEU
):
    
    username = user["username"]

    # History für diesen User holen
    history = store.get_history(username)

    result = engine.ask(
        question=request.question,
        history=history,
        use_expansion=request.use_expansion,
        n_chunks=request.n_chunks
    )

    # History updaten
    store.add_message(username, "user", request.question)
    store.add_message(username, "assistant", result["answer"])

    return AnswerResponse(
        question=result["question"],
        answer=result["answer"],
        sources=result["sources"]
    )

@router.delete("/history")
def clear_history(user: dict = Depends(get_current_user)):
    """Konversations-History löschen."""
    store.clear(user["username"])
    return {"message": "History cleared"}


@router.get("/history")
def get_history(user: dict = Depends(get_current_user)):
    """Aktuelle History abrufen."""
    return {
        "history": store.get_history(user["username"]),
        "stats": store.get_stats(user["username"])
    }