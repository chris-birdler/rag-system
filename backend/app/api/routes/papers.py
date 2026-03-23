# backend/app/api/routes/papers.py
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends

from backend.app.services.library import PaperLibrary
from backend.app.core.auth import get_current_user, require_admin

router = APIRouter()
UPLOAD_DIR = Path("data/pdfs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

def get_library():
    return PaperLibrary()

@router.post("/upload")
async def upload_paper(
    file: UploadFile = File(...),
    user: dict = Depends(require_admin)  # ← nur Admin
):
    """
    PDF hochladen und indexieren.
    Multipart Form Upload – Standard für Datei-Uploads.
    """
    
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")

    # Datei speichern
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Indexieren
    library = get_library()
    result = library.add_paper(str(file_path))

    if not result:
        return {"message": f"'{file.filename}' already indexed"}

    return {
        "message": f"'{file.filename}' successfully indexed",
        "metadata": result
    }

@router.get("/")
def list_papers(
    user: dict = Depends(get_current_user)  # ← alle User
):
    """Alle indexierten Paper auflisten."""
    library = get_library()
    return library.list_papers()

@router.delete("/{doi:path}")
def delete_paper(
    doi: str,
    user: dict = Depends(require_admin)
):
    """
    Paper aus Index entfernen.
    Löscht alle Chunks dieses Papers aus ChromaDB und BM25.
    Nur Admins dürfen löschen.
    """
    library = PaperLibrary()
    
    # Prüfe ob Paper existiert
    results = library._collection.get(
        where={"doi": {"$eq": doi}},
        limit=1
    )
    if not results["ids"]:
        raise HTTPException(404, f"Paper with DOI '{doi}' not found")
    
    # Alle Chunks dieses Papers löschen
    library._collection.delete(
        where={"doi": {"$eq": doi}}
    )
    
    # BM25 neu aufbauen
    library._rebuild_bm25()
    
    return {"message": f"Paper '{doi}' deleted successfully"}