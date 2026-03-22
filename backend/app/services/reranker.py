# backend/app/services/reranker.py

"""
Reranker – sortiert Kandidaten nach Relevanz zur Query.

Zwei Strategien:
    cohere: Cohere API (beste Qualität, Cloud)
    local:  CrossEncoder (gut, vollständig lokal)

Konfiguration via .env:
    RERANKER=cohere   # Cloud
    RERANKER=local    # Kein Internet nötig
"""

from backend.app.core.config import settings


def rerank(
    query: str,
    candidates: list[dict],
    n_results: int = None
) -> list[dict]:
    """
    Einheitliches Interface für alle Reranker.

    Args:
        query:      Suchanfrage
        candidates: Liste von Chunks aus Hybrid Retrieval
        n_results:  Anzahl finale Ergebnisse

    Returns:
        Neu sortierte Liste mit similarity Score 0.0-1.0
    """
    n = n_results or settings.top_k_rerank
    provider = settings.reranker.lower()

    if provider == "cohere":
        return _rerank_cohere(query, candidates, n)
    elif provider == "local":
        return _rerank_local(query, candidates, n)
    else:
        raise ValueError(f"Unknown reranker: {provider}")


def _rerank_cohere(
    query: str,
    candidates: list[dict],
    n_results: int
) -> list[dict]:
    """
    Cohere Re-Ranking.
    Beste Qualität, benötigt Internet und API Key.
    """
    import cohere
    co = cohere.Client(settings.cohere_api_key)

    documents = [c["text"] for c in candidates]

    response = co.rerank(
        model="rerank-english-v3.0",
        query=query,
        documents=documents,
        top_n=n_results,
        return_documents=True
    )

    reranked = []
    for hit in response.results:
        result = candidates[hit.index].copy()
        result["similarity"] = hit.relevance_score
        reranked.append(result)

    return reranked


def _rerank_local(
    query: str,
    candidates: list[dict],
    n_results: int
) -> list[dict]:
    """
    Lokales Re-Ranking mit CrossEncoder.
    Kein Internet, kein API Key, läuft vollständig lokal.

    Modell: cross-encoder/ms-marco-MiniLM-L-6-v2
    - Klein und schnell (~80MB)
    - Gut für englische wissenschaftliche Texte
    - Beim ersten Aufruf automatisch heruntergeladen

    Warum CrossEncoder statt Bi-Encoder?

    Bi-Encoder (was wir für Embeddings nutzen):
    Query → Vektor
    Chunk → Vektor
    Similarity = Cosine(Query-Vektor, Chunk-Vektor)
    → schnell aber ungenau

    CrossEncoder:
    [Query + Chunk] → Score
    → liest beide zusammen → versteht Beziehung
    → langsamer aber deutlich genauer
    → dasselbe Prinzip wie Cohere
    """
    from sentence_transformers import CrossEncoder

    # Modell laden (wird gecacht nach erstem Download)
    model = CrossEncoder(
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        max_length=512
    )

    # Query-Chunk Paare für CrossEncoder
    pairs = [[query, c["text"]] for c in candidates]

    # Scores berechnen
    scores = model.predict(pairs)

    # Scores normalisieren auf 0-1 via Sigmoid
    import numpy as np
    scores_normalized = 1 / (1 + np.exp(-scores))

    # Kandidaten mit Scores zusammenführen
    scored = list(zip(scores_normalized, candidates))

    # Nach Score sortieren
    scored.sort(key=lambda x: x[0], reverse=True)

    # Top n_results zurückgeben
    reranked = []
    for score, candidate in scored[:n_results]:
        result = candidate.copy()
        result["similarity"] = float(score)
        reranked.append(result)

    return reranked