# backend/app/api/routes/papers.py
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks

from backend.app.services.library import PaperLibrary
from backend.app.core.auth import get_current_user, require_admin

router = APIRouter()
UPLOAD_DIR = Path("data/pdfs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Maximale Upload-Größe pro PDF (gegen Disk-DoS)
MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

def get_library():
    return PaperLibrary()

# In-Memory Status Store
# Key: filename, Value: status dict
indexing_status: dict[str, dict] = {}

def _index_paper_task(file_path: str, filename: str) -> None:
    """
    Background Task – läuft nach dem Response.
    Updated den Status während der Indexierung.
    """
    try:
        indexing_status[filename] = {
            "status": "indexing",
            "filename": filename
        }
        library = PaperLibrary()
        result = library.add_paper(file_path)

        if not result:
            indexing_status[filename] = {
                "status": "already_indexed",
                "filename": filename
            }
        else:
            indexing_status[filename] = {
                "status": "done",
                "filename": filename,
                "chunks": result.get("chunks", 0),
                "title": result.get("title", ""),
            }
    except Exception as e:
        indexing_status[filename] = {
            "status": "failed",
            "filename": filename,
            "error": str(e)
        }

@router.post("/upload")
async def upload_paper(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user: dict = Depends(require_admin)  # ← nur Admin
):
    """
    PDF hochladen und indexieren.
    Multipart Form Upload – Standard für Datei-Uploads.
    """

    # Filename härten: Pfadanteile ("../", "/", "\") entfernen, damit
    # ein bösartiger Name nicht außerhalb von UPLOAD_DIR schreiben kann.
    raw_name = file.filename or ""
    safe_name = Path(raw_name).name
    if not safe_name or not safe_name.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files allowed")
    if ".." in safe_name or "/" in safe_name or "\\" in safe_name:
        raise HTTPException(400, "Invalid filename")

    file_path = UPLOAD_DIR / safe_name

    # In Chunks streamen und Größe begrenzen.
    size = 0
    try:
        with open(file_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):  # 1 MB
                size += len(chunk)
                if size > MAX_UPLOAD_SIZE:
                    raise HTTPException(
                        413,
                        f"File too large (max {MAX_UPLOAD_SIZE // (1024 * 1024)} MB)"
                    )
                f.write(chunk)
    except HTTPException:
        # Teilweise geschriebene Datei wegräumen
        file_path.unlink(missing_ok=True)
        raise

    # Indexierung im Hintergrund starten
    background_tasks.add_task(
        _index_paper_task,
        str(file_path),
        safe_name
    )

    # Sofort antworten – nicht warten
    return {
        "status": "indexing",
        "message": f"'{safe_name}' upload received, indexing started",
        "filename": safe_name
    }

@router.get("/status/{filename}")
def get_indexing_status(
    filename: str,
    user: dict = Depends(get_current_user)
):
    """
    Status der Indexierung abfragen.
    Frontend kann diesen Endpoint pollen bis status='done'
    """
    status = indexing_status.get(filename)
    if not status:
        return {"status": "unknown", "filename": filename}
    return status

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