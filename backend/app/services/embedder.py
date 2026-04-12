from backend.app.core.config import settings
from backend.app.db.database import SessionLocal
from backend.app.db.repositories import cost_repo


def _log_embedding_cost(input_tokens: int) -> None:
    """Embedding-Kosten in DB schreiben, damit das Tageslimit greift."""
    if input_tokens <= 0:
        return
    with SessionLocal() as db:
        cost_repo.log_cost(
            db,
            model=settings.embedding_model,
            input_tokens=input_tokens,
            output_tokens=0,
            call_type="embedding",
        )


def _estimate_tokens(texts: list[str]) -> int:
    """Grobe Token-Schätzung, wenn Provider keine Usage-Info liefert (~4 chars/token)."""
    return sum(len(t) for t in texts) // 4


def get_embeddings(texts: list[str]) -> list[list[float]]:
    """
    Einheitliches Interface für alle Embedding Provider.
    Analog zu get_llm_response() in llm.py.
    """
    provider = settings.embedding_provider.lower()

    if provider == "openai":
        return _openai_embeddings(texts)
    elif provider == "cohere":
        return _cohere_embeddings(texts)
    elif provider == "ollama":
        return _ollama_embeddings(texts)
    else:
        raise ValueError(f"Unknown embedding provider: {provider}")


def _openai_embeddings(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)
    embeddings = []
    for i in range(0, len(texts), settings.embedding_batch_size):
        batch = texts[i:i+settings.embedding_batch_size]
        response = client.embeddings.create(
            model=settings.embedding_model,
            input=batch
        )
        _log_embedding_cost(response.usage.total_tokens)
        embeddings.extend([e.embedding for e in response.data])
    return embeddings


def _cohere_embeddings(texts: list[str]) -> list[list[float]]:
    import cohere
    client = cohere.Client(settings.cohere_api_key)
    embeddings = []
    for i in range(0, len(texts), 96):  # Cohere batch limit
        batch = texts[i:i+96]
        response = client.embed(
            texts=batch,
            model=settings.embedding_model,  # "embed-english-v3.0"
            input_type="search_document"
        )
        # Cohere liefert keine zuverlässige Usage-Info in allen SDK-Versionen
        _log_embedding_cost(_estimate_tokens(batch))
        embeddings.extend(response.embeddings)
    return embeddings


def _ollama_embeddings(texts: list[str]) -> list[list[float]]:
    from openai import OpenAI
    client = OpenAI(
        api_key="ollama",
        base_url="http://localhost:11434/v1"
    )
    embeddings = []
    for i in range(0, len(texts), settings.embedding_batch_size):
        batch = texts[i:i+settings.embedding_batch_size]
        response = client.embeddings.create(
            model=settings.embedding_model,  # "nomic-embed-text"
            input=batch
        )
        # Ollama läuft lokal – keine Kosten, kein Logging
        embeddings.extend([e.embedding for e in response.data])
    return embeddings
