# backend/app/services/vector_store.py

import chromadb
from openai import OpenAI
from backend.app.core.config import settings
from backend.app.services.chunker import Chunk


class VectorStore:

    def __init__(self, persist_directory: str = ".chroma"):
        """
        ChromaDB lokal auf Disk.
        persist_directory = wo die Vektoren gespeichert werden.
        Beim nächsten Start automatisch geladen – kein erneutes Berechnen.
        """
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.openai = OpenAI(api_key=settings.openai_api_key)

        # Collection = Tabelle in ChromaDB
        # get_or_create → beim ersten Mal anlegen, danach laden
        self.collection = self.client.get_or_create_collection(
            name="papers",
            metadata={"hnsw:space": "cosine"}  # Cosine Similarity als Distanzmetrik
        )

    def add_chunks(self, chunks: list[Chunk]) -> None:
        """
        Berechnet Embeddings für alle Chunks und speichert sie.

        ChromaDB braucht:
        - documents: die Texte
        - embeddings: die Vektoren
        - metadatas: beliebige Metadaten (für Filter später)
        - ids: eindeutige IDs
        """
        if not chunks:
            return

        print(f"Berechne Embeddings für {len(chunks)} Chunks...")

        # Embeddings in Batches – API hat Limit pro Request
        texts = [chunk.text for chunk in chunks]
        embeddings = self._get_embeddings(texts)

        # In ChromaDB speichern
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=[self._chunk_to_metadata(chunk) for chunk in chunks],
            ids=[self._make_id(chunk) for chunk in chunks]
        )
        print(f"✅ {len(chunks)} Chunks gespeichert")

    def search(
        self,
        query: str,
        n_results: int = 5,
        filter_year: str = None,    # Optional: nur Paper von 2020
        filter_author: str = None   # Optional: nur Paper von Vogler
    ) -> list[dict]:
        """
        Semantische Suche.

        1. Query → Embedding
        2. Cosine Similarity gegen alle gespeicherten Vektoren
        3. Top n_results zurückgeben
        """
        # Query in Vektor umwandeln
        query_embedding = self._get_embeddings([query])[0]

        # Filter aufbauen (optional)
        where = self._build_filter(filter_year, filter_author)

        # Suche in ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )

        # Ergebnisse aufbereiten
        return self._format_results(results)

    def get_stats(self) -> dict:
        """Wie viele Chunks sind gespeichert?"""
        return {
            "total_chunks": self.collection.count(),
        }

    # =========================================================
    # HILFSFUNKTIONEN
    # =========================================================

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        OpenAI Embeddings API.
        text-embedding-3-large: 3072 Dimensionen, beste Qualität.
        In Batches von 100 wegen API-Limits.
        """
        embeddings = []
        batch_size = 100

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            response = self.openai.embeddings.create(
                model="text-embedding-3-large",
                input=batch
            )
            embeddings.extend([e.embedding for e in response.data])

        return embeddings

    def _chunk_to_metadata(self, chunk: Chunk) -> dict:
        """
        Metadaten für ChromaDB.
        Wichtig: ChromaDB erlaubt nur str, int, float, bool.
        None muss zu "" konvertiert werden.
        """
        return {
            "filename": chunk.filename or "",
            "title": chunk.title or "",
            "authors": chunk.authors or "",
            "year": chunk.year or "",
            "doi": chunk.doi or "",
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "section": chunk.section or "",
            "strategy": chunk.strategy or "",
        }

    def _make_id(self, chunk: Chunk) -> str:
        """
        Eindeutige ID pro Chunk.
        filename + index verhindert Duplikate beim erneuten Hinzufügen.
        """
        filename = chunk.filename.replace(".pdf", "").replace(" ", "_")
        return f"{filename}_chunk_{chunk.chunk_index}"

    def _build_filter(
        self,
        filter_year: str = None,
        filter_author: str = None
    ) -> dict:
        """
        ChromaDB Filter-Syntax.
        Ermöglicht: "suche nur in Paper von 2020"
        oder: "suche nur Paper von Vogler"
        """
        conditions = []

        if filter_year:
            conditions.append({"year": {"$eq": filter_year}})

        if filter_author:
            conditions.append({"authors": {"$contains": filter_author}})

        if len(conditions) == 0:
            return {}
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}

    def _format_results(self, results: dict) -> list[dict]:
        """
        ChromaDB gibt verschachtelte Listen zurück.
        Wir flatten das zu einer Liste von Dicts.
        """
        formatted = []
        documents = results["documents"][0]
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for doc, meta, dist in zip(documents, metadatas, distances):
            formatted.append({
                "text": doc,
                "metadata": meta,
                "similarity": 1 - dist,  # Distanz → Similarity
                "title": meta.get("title", ""),
                "authors": meta.get("authors", ""),
                "year": meta.get("year", ""),
                "doi": meta.get("doi", ""),
                "page": meta.get("page_number", 0),
                "section": meta.get("section", ""),
            })

        return formatted