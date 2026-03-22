# backend/app/services/library.py

"""
PaperLibrary – einziges öffentliches Interface für alle RAG-Operationen.

User-facing API:
    library = PaperLibrary()
    library.add_paper("paper.pdf")
    results = library.search("coercive field")
    results = library.search_with_rerank("coercive field")

Intern verwaltet PaperLibrary:
    - ChromaDB für Vektor-Suche
    - BM25 für Keyword-Suche
    - Cohere für Re-Ranking
    - PDF Processing und Chunking

Der User weiß nichts davon und muss nichts davon wissen.
"""

import chromadb
from rank_bm25 import BM25Okapi
from pathlib import Path

from backend.app.core.config import settings
from backend.app.services.pdf_processor import PDFProcessor
from backend.app.services.chunker import Chunker, Chunk
from backend.app.services.query_expander import QueryExpander
from backend.app.services.llm import get_llm_response
from backend.app.services.reranker import rerank
from backend.app.services.embedder import get_embeddings


class PaperLibrary:
    """
    Zentrale Bibliothek für wissenschaftliche Paper.
    Kapselt alle Retrieval-Operationen hinter einem einfachen Interface.
    """

    def __init__(self, persist_directory: str = ".chroma"):
        # Interne Komponenten – privat, nicht für User gedacht
        self._processor = PDFProcessor()
        self._chunker = Chunker()
        self._expander = QueryExpander()

        # ChromaDB – persistent
        self._chroma = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._chroma.get_or_create_collection(
            name="papers",
            metadata={"hnsw:space": "cosine"}
        )

        # BM25 – aus ChromaDB beim Start laden
        self._bm25 = None
        self._bm25_docs = []  # [(text, metadata), ...]
        self._rebuild_bm25()

    # =========================================================
    # ÖFFENTLICHE API
    # =========================================================

    def add_paper(self, pdf_path: str) -> dict:
        """
        Fügt ein Paper zur Bibliothek hinzu.
        Verarbeitet, chunked, indexiert – alles automatisch.

        Returns: Metadaten des hinzugefügten Papers
        """
        # Bereits indexiert?
        filename = Path(pdf_path).name
        if self._is_indexed(filename):
            print(f"'{filename}' bereits in der Bibliothek.")
            return {}

        print(f"Verarbeite '{filename}'...")

        # 1. PDF verarbeiten
        doc = self._processor.process(pdf_path, use_llm=True)

        # 2. Chunking
        chunks = self._chunker.chunk(
            doc, strategy=settings.chunking_strategy
        )

        # 3. Embeddings + ChromaDB
        self._add_to_chroma(chunks)

        # 4. BM25 automatisch aktualisieren
        self._rebuild_bm25()

        print(f"✅ '{filename}' hinzugefügt "
              f"({len(chunks)} Chunks, "
              f"Total: {self._collection.count()})")

        return {
            "filename": filename,
            "title": doc.metadata.title,
            "authors": doc.metadata.authors,
            "year": doc.metadata.year,
            "doi": doc.metadata.doi,
            "chunks": len(chunks)
        }

    def search(
        self,
        query: str,
        n_results: int = None,
        year: str = None,
        author: str = None
    ) -> list[dict]:
        """
        Hybrid Suche: Vektor + BM25 kombiniert.
        Schnell, keine externen API-Kosten.

        Args:
            query:     Suchanfrage
            n_results: Anzahl Ergebnisse (default aus config)
            year:      Filter nach Jahr z.B. "2020"
            author:    Filter nach Autor z.B. "Vogler"
        """
        n = n_results or settings.top_k_retrieval
        candidates = n * 3

        vector_results = self._vector_search(query, candidates, year, author)
        bm25_results = self._bm25_search(query, candidates)

        return self._rrf_fusion(vector_results, bm25_results, n)

    # def search_with_rerank(
    #     self,
    #     query: str,
    #     n_results: int = None,
    #     year: str = None,
    #     author: str = None
    # ) -> list[dict]:
    #     """
    #     Vollständige Pipeline: Hybrid + Cohere Re-Ranking.
    #     Beste Qualität, empfohlen für finale Antworten.

    #     Args:
    #         query:     Suchanfrage
    #         n_results: Anzahl finale Ergebnisse (default aus config)
    #         year:      Filter nach Jahr
    #         author:    Filter nach Autor
    #     """
    #     n = n_results or settings.top_k_rerank

    #     # Mehr Kandidaten für Re-Ranking
    #     candidates = self.search(query, n_results=15, year=year, author=author)

    #     if not candidates:
    #         return []

    #     # Cohere Re-Ranking
    #     documents = [c["text"] for c in candidates]
    #     response = self._cohere.rerank(
    #         model="rerank-english-v3.0",
    #         query=query,
    #         documents=documents,
    #         top_n=n,
    #         return_documents=True
    #     )

    #     reranked = []
    #     for hit in response.results:
    #         result = candidates[hit.index].copy()
    #         result["similarity"] = hit.relevance_score
    #         reranked.append(result)

    #     return reranked

    def search_with_rerank(
        self,
        query,
        n_results=None,
        year=None,
        author=None):

        n = n_results or settings.top_k_rerank
        candidates = self.search(query, n_results=15, year=year, author=author)

        if not candidates:
            return []

        # Vorher: self._cohere.rerank(...)
        # Nachher: reranker.py übernimmt
        return rerank(query, candidates, n_results=n)

    def get_stats(self) -> dict:
        """Statistiken über die Bibliothek."""
        return {
            "total_chunks": self._collection.count(),
            "bm25_indexed": len(self._bm25_docs),
        }

    def list_papers(self) -> list[dict]:
        """Alle indizierten Paper auflisten."""
        results = self._collection.get(include=["metadatas"])
        seen = {}
        for meta in results["metadatas"]:
            filename = meta.get("filename", "")
            if filename not in seen:
                seen[filename] = {
                    "filename": filename,
                    "title": meta.get("title", ""),
                    "authors": meta.get("authors", ""),
                    "year": meta.get("year", ""),
                    "doi": meta.get("doi", ""),
                }
        return list(seen.values())
    
    def search_expanded(
        self,
        query: str,
        n_results: int = None,
        strategy: str = "multi_query",
        year: str = None,
        author: str = None
    ) -> list[dict]:
        """
        Suche mit Query Expansion.
        Findet mehr relevante Chunks durch multiple Queries.

        strategy: "multi_query" oder "hyde"
        """
        n = n_results or settings.top_k_retrieval

        # Query expandieren
        queries = self._expander.expand(query, strategy=strategy)
        print(f"Expanded queries: {queries}")

        # Alle Queries suchen
        all_results = []
        for q in queries:
            results = self.search(q, n_results=10, year=year, author=author)
            all_results.append(results)

        # RRF über alle Query-Ergebnisse
        return self._multi_query_rrf(all_results, n)

    # =========================================================
    # INTERNE METHODEN – nicht für User gedacht
    # =========================================================

    def _multi_query_rrf(
        self,
        all_results: list[list[dict]],
        n_results: int,
        k: int = 60
    ) -> list[dict]:
        """
        RRF über mehrere Query-Ergebnislisten.
        Chunks die in mehreren Queries gut ranken gewinnen.
        """
        scores = {}
        chunk_data = {}

        for results in all_results:
            for rank, result in enumerate(results):
                cid = self._chunk_id(result)
                scores[cid] = scores.get(cid, 0) + (1 / (rank + k))
                chunk_data[cid] = result

        sorted_ids = sorted(
            scores.keys(),
            key=lambda cid: scores[cid],
            reverse=True
        )

        results = []
        for cid in sorted_ids[:n_results]:
            result = chunk_data[cid].copy()
            result["similarity"] = scores[cid]
            results.append(result)

        return results

    def _add_to_chroma(self, chunks: list[Chunk]) -> None:
        """Chunks in ChromaDB speichern."""
        if not chunks:
            return

        texts = [chunk.text for chunk in chunks]
        embeddings = self._get_embeddings(texts)

        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=[self._chunk_to_metadata(c) for c in chunks],
            ids=[self._make_id(c) for c in chunks]
        )

    def _rebuild_bm25(self) -> None:
        """
        BM25 Index neu aufbauen aus ChromaDB.
        Wird automatisch aufgerufen:
        - beim Start (__init__)
        - nach add_paper()
        Garantiert Synchronität zwischen ChromaDB und BM25.
        """
        results = self._collection.get(
            include=["documents", "metadatas"]
        )

        if not results["documents"]:
            self._bm25 = None
            self._bm25_docs = []
            return

        self._bm25_docs = list(zip(
            results["documents"],
            results["metadatas"]
        ))

        tokenized = [text.lower().split() for text, _ in self._bm25_docs]
        self._bm25 = BM25Okapi(tokenized)

    def _vector_search(
        self,
        query: str,
        n_results: int,
        year: str = None,
        author: str = None
    ) -> list[dict]:
        """ChromaDB Vektor-Suche."""
        query_embedding = self._get_embeddings([query])[0]
        where = self._build_filter(year, author)

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, self._collection.count()),
            where=where if where else None,
            include=["documents", "metadatas", "distances"]
        )

        formatted = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ):
            formatted.append({
                "text": doc,
                "metadata": meta,
                "similarity": 1 - dist,
                "title": meta.get("title", ""),
                "authors": meta.get("authors", ""),
                "year": meta.get("year", ""),
                "doi": meta.get("doi", ""),
                "page": meta.get("page_number", 0),
                "section": meta.get("section", ""),
            })
        return formatted

    def _bm25_search(self, query: str, n_results: int) -> list[dict]:
        """BM25 Keyword-Suche."""
        if not self._bm25 or not self._bm25_docs:
            return []

        scores = self._bm25.get_scores(query.lower().split())
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:n_results]

        results = []
        for idx in top_indices:
            text, meta = self._bm25_docs[idx]
            results.append({
                "text": text,
                "metadata": meta,
                "similarity": float(scores[idx]),
                "title": meta.get("title", ""),
                "authors": meta.get("authors", ""),
                "year": meta.get("year", ""),
                "doi": meta.get("doi", ""),
                "page": meta.get("page_number", 0),
                "section": meta.get("section", ""),
            })
        return results

    def _rrf_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        n_results: int,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        k: int = 60
    ) -> list[dict]:
        """Reciprocal Rank Fusion."""
        scores = {}
        chunk_data = {}

        for rank, result in enumerate(vector_results):
            cid = self._chunk_id(result)
            scores[cid] = scores.get(cid, 0) + \
                vector_weight * (1 / (rank + k))
            chunk_data[cid] = result

        for rank, result in enumerate(bm25_results):
            cid = self._chunk_id(result)
            scores[cid] = scores.get(cid, 0) + \
                bm25_weight * (1 / (rank + k))
            if cid not in chunk_data:
                chunk_data[cid] = result

        sorted_ids = sorted(
            scores.keys(),
            key=lambda cid: scores[cid],
            reverse=True
        )

        results = []
        for cid in sorted_ids[:n_results]:
            result = chunk_data[cid].copy()
            result["similarity"] = scores[cid]
            results.append(result)

        return results

    # def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
    #     """OpenAI Embeddings in Batches."""
    #     embeddings = []
    #     for i in range(0, len(texts), 100):
    #         batch = texts[i:i+100]
    #         response = self._openai.embeddings.create(
    #             model="text-embedding-3-large",
    #             input=batch
    #         )
    #         embeddings.extend([e.embedding for e in response.data])
    #     return embeddings

    def _get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return get_embeddings(texts)

    def _is_indexed(self, filename: str) -> bool:
        """Prüft ob ein Paper bereits indexiert ist."""
        results = self._collection.get(
            where={"filename": {"$eq": filename}},
            limit=1
        )
        return len(results["ids"]) > 0

    def _chunk_to_metadata(self, chunk: Chunk) -> dict:
        """Chunk → ChromaDB Metadaten."""
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
        """Eindeutige ID pro Chunk."""
        filename = chunk.filename.replace(".pdf", "").replace(" ", "_")
        return f"{filename}_chunk_{chunk.chunk_index}"

    def _chunk_id(self, result: dict) -> str:
        """Eindeutige ID aus Result-Dict."""
        meta = result.get("metadata", {})
        return f"{meta.get('filename', '')}_{meta.get('chunk_index', 0)}"

    def _build_filter(self, year: str = None, author: str = None) -> dict:
        """ChromaDB Filter."""
        conditions = []
        if year:
            conditions.append({"year": {"$eq": year}})
        if author:
            conditions.append({"authors": {"$contains": author}})

        if not conditions:
            return {}
        elif len(conditions) == 1:
            return conditions[0]
        else:
            return {"$and": conditions}