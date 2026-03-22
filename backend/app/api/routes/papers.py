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
def delete_paper(doi: str):
    """
    Paper aus Index entfernen.
    DOI als Path Parameter – enthält Slashes daher doi:path
    """
    # TODO in Schritt 11 implementieren
    raise HTTPException(501, "Not implemented yet")