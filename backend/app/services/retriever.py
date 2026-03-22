# backend/app/services/retriever.py

from rank_bm25 import BM25Okapi
from backend.app.services.vector_store import VectorStore
from backend.app.services.chunker import Chunk


class HybridRetriever:

    def __init__(self, vector_store: VectorStore):
        self.vector_store = vector_store
        self.bm25 = None
        self.bm25_chunks = []  # alle Chunks für BM25

    def index_for_bm25(self, chunks: list[Chunk]) -> None:
        """
        BM25 Index aufbauen.

        BM25 arbeitet nicht mit Vektoren sondern mit Tokens –
        wir teilen jeden Chunk in Wörter auf.

        Wichtig: BM25 Index ist nicht persistent wie ChromaDB.
        Er muss bei jedem Start neu aufgebaut werden.
        Das ist okay weil es sehr schnell geht (~Millisekunden).
        """
        self.bm25_chunks.extend(chunks)

        # Tokenisierung: Text → Liste von Wörtern (lowercase)
        tokenized = [
            chunk.text.lower().split()
            for chunk in self.bm25_chunks
        ]
        self.bm25 = BM25Okapi(tokenized)
        print(f"BM25 Index: {len(self.bm25_chunks)} Chunks")

    def search(
        self,
        query: str,
        n_results: int = 5,
        vector_weight: float = 0.7,  # 70% Vektor, 30% BM25
        bm25_weight: float = 0.3
    ) -> list[dict]:
        """
        Hybrid Suche: Vektor + BM25 kombiniert.

        vector_weight + bm25_weight sollten = 1.0 sein.
        0.7/0.3 ist ein guter Ausgangspunkt für wissenschaftliche Texte –
        semantisches Verständnis ist wichtiger als exakte Keywords,
        aber Keywords sind für Formeln und Namen kritisch.
        """
        # Mehr Kandidaten holen als wir brauchen
        # RRF braucht Überlappung zum Kombinieren
        n_candidates = n_results * 3

        # --- Vektor Suche ---
        vector_results = self.vector_store.search(
            query, n_results=n_candidates
        )

        # --- BM25 Suche ---
        bm25_results = self._bm25_search(query, n_candidates)

        # --- Reciprocal Rank Fusion ---
        fused = self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
            vector_weight,
            bm25_weight
        )

        return fused[:n_results]
    
    def search_with_rerank(
        self,
        query: str,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Vollständige Pipeline:
        1. Hybrid Retrieval (Vektor + BM25) → Top 15 Kandidaten
        2. Cohere Re-Ranking → Top 5 finale Ergebnisse

        Warum zwei Schritte?
        Re-Ranking ist teurer als Retrieval –
        wir wollen nicht alle 79 Chunks re-ranken,
        sondern nur die vielversprechendsten 15.
        """
        import cohere
        from backend.app.core.config import settings

        # Schritt 1: Hybrid Retrieval – mehr Kandidaten als nötig
        candidates = self.search(query, n_results=15)

        if not candidates:
            return []

        # Schritt 2: Cohere Re-Ranking
        co = cohere.Client(settings.cohere_api_key)

        # Cohere braucht nur die Texte
        documents = [c["text"] for c in candidates]

        response = co.rerank(
            model="rerank-english-v3.0",
            query=query,
            documents=documents,
            top_n=n_results,
            return_documents=True
        )

        # Ergebnisse mit neuem Score aufbauen
        reranked = []
        for hit in response.results:
            # hit.index = Position im original candidates Liste
            original = candidates[hit.index]
            result = original.copy()
            result["similarity"] = hit.relevance_score  # 0.0 bis 1.0
            result["rerank_score"] = hit.relevance_score
            result["original_rank"] = hit.index
            reranked.append(result)

        return reranked

    def _bm25_search(
        self, query: str, n_results: int
    ) -> list[dict]:
        """
        BM25 Suche.
        Gibt dieselbe Struktur zurück wie vector_store.search()
        damit RRF beide gleich behandeln kann.
        """
        if not self.bm25:
            return []

        # Query tokenisieren
        query_tokens = query.lower().split()

        # BM25 Scores für alle Chunks
        scores = self.bm25.get_scores(query_tokens)

        # Top n_results Indices
        top_indices = sorted(
            range(len(scores)),
            key=lambda i: scores[i],
            reverse=True
        )[:n_results]

        results = []
        for idx in top_indices:
            chunk = self.bm25_chunks[idx]
            results.append({
                "text": chunk.text,
                "similarity": float(scores[idx]),
                "title": chunk.title or "",
                "authors": chunk.authors or "",
                "year": chunk.year or "",
                "doi": chunk.doi or "",
                "page": chunk.page_number,
                "section": chunk.section or "",
                "metadata": {
                    "filename": chunk.filename,
                    "chunk_index": chunk.chunk_index,
                }
            })

        return results

    def _reciprocal_rank_fusion(
        self,
        vector_results: list[dict],
        bm25_results: list[dict],
        vector_weight: float,
        bm25_weight: float,
        k: int = 60  # RRF Dämpfungsfaktor
    ) -> list[dict]:
        """
        Reciprocal Rank Fusion.

        Für jeden Chunk:
        score = vector_weight × 1/(rank_v + k)
              + bm25_weight   × 1/(rank_b + k)

        k=60 ist empirisch bewährt – dämpft den Einfluss
        sehr hoher Rankings damit kein einzelnes Ergebnis dominiert.

        Chunks die in beiden Rankings gut sind gewinnen.
        """
        # Scores pro Chunk-ID sammeln
        # ID = filename + chunk_index (eindeutig)
        scores = {}
        chunk_data = {}

        # Vektor Rankings
        for rank, result in enumerate(vector_results):
            chunk_id = self._get_chunk_id(result)
            rrf_score = vector_weight * (1 / (rank + k))
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
            chunk_data[chunk_id] = result

        # BM25 Rankings
        for rank, result in enumerate(bm25_results):
            chunk_id = self._get_chunk_id(result)
            rrf_score = bm25_weight * (1 / (rank + k))
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
            if chunk_id not in chunk_data:
                chunk_data[chunk_id] = result

        # Nach Score sortieren
        sorted_ids = sorted(
            scores.keys(),
            key=lambda cid: scores[cid],
            reverse=True
        )

        # Ergebnisse mit finalem RRF Score zurückgeben
        results = []
        for chunk_id in sorted_ids:
            result = chunk_data[chunk_id].copy()
            result["rrf_score"] = scores[chunk_id]
            result["similarity"] = scores[chunk_id]
            results.append(result)

        return results

    def _get_chunk_id(self, result: dict) -> str:
        """Eindeutige ID aus Metadaten."""
        meta = result.get("metadata", {})
        filename = meta.get("filename", result.get("title", ""))
        chunk_index = meta.get("chunk_index", 0)
        return f"{filename}_{chunk_index}"