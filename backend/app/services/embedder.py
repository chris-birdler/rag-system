from backend.app.core.config import settings

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
        embeddings.extend([e.embedding for e in response.data])
    return embeddings