from pydantic_settings import BaseSettings
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"

class Settings(BaseSettings):
    # Optional wenn lokal – leerer String als Default
    openai_api_key: str = ""
    cohere_api_key: str = ""
    deepseek_api_key: str = ""
    anthropic_api_key: str = ""
    
    chunk_size: int = 1500
    chunk_overlap: int = 200
    top_k_retrieval: int = 10
    top_k_rerank: int = 5
    chunking_strategy: str = "recursive"

    # NEU – LLM Konfiguration
    llm_provider: str = "openai"        # openai, deepseek, ollama, anthropic
    llm_model: str = "gpt-4o-mini"      # Modell pro Provider
    llm_temperature: float = 0.3        # für Antwort-Generierung
    deepseek_api_key: str = ""          # optional
    anthropic_api_key: str = ""         # optional
    embedding_provider: str = "openai"      # openai, cohere, ollama
    embedding_model: str = "text-embedding-3-large"
    embedding_batch_size: int = 100
    reranker: str = "cohere"  # cohere oder local

    secret_key: str = "Chris2088"
    token_expire_hours: int = 24

    # Admin-Account – aus .env laden, NICHT hardcoden
    admin_username: str = ""
    admin_password: str = ""

    class Config:
        env_file = ENV_PATH

settings = Settings()
