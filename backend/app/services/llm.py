# backend/app/services/llm.py

"""
LLM Factory – gibt den richtigen LLM Client zurück.

Unterstützte Provider:
- openai:    GPT-4o, GPT-4o-mini
- deepseek:  deepseek-chat (OpenAI-kompatibel)
- ollama:    Llama3, Mistral etc. (lokal)
- anthropic: Claude

Der Rest der Applikation weiß nicht welcher Provider
verwendet wird – alle haben dasselbe Interface.
"""

from backend.app.core.config import settings


def get_llm_response(
    messages: list[dict],
    temperature: float = None,
    max_tokens: int = 1000
) -> str:
    """
    Einheitliches Interface für alle LLM Provider.

    Args:
        messages:    Conversation history im OpenAI Format
                     [{"role": "user", "content": "..."}]
        temperature: Überschreibt config default
        max_tokens:  Maximale Antwortlänge

    Returns:
        Antwort als String
    """
    temp = temperature if temperature is not None else settings.llm_temperature
    provider = settings.llm_provider.lower()

    if provider == "openai":
        return _openai_response(messages, temp, max_tokens)
    elif provider == "deepseek":
        return _deepseek_response(messages, temp, max_tokens)
    elif provider == "ollama":
        return _ollama_response(messages, temp, max_tokens)
    elif provider == "anthropic":
        return _anthropic_response(messages, temp, max_tokens)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def _openai_response(
    messages: list[dict],
    temperature: float,
    max_tokens: int
) -> str:
    """OpenAI GPT-4o, GPT-4o-mini etc."""
    from openai import OpenAI
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.llm_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content


def _deepseek_response(
    messages: list[dict],
    temperature: float,
    max_tokens: int
) -> str:
    """
    DeepSeek – OpenAI-kompatibel.
    Nur base_url und api_key ändern sich.
    Deshalb können wir den OpenAI Client direkt verwenden.
    """
    from openai import OpenAI
    client = OpenAI(
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com"
    )

    response = client.chat.completions.create(
        model=settings.llm_model,  # "deepseek-chat"
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content


def _ollama_response(
    messages: list[dict],
    temperature: float,
    max_tokens: int
) -> str:
    """
    Ollama – lokale Modelle.
    Läuft auf localhost:11434.
    Kein API Key nötig.
    Modelle: llama3, mistral, phi3 etc.
    """
    from openai import OpenAI
    client = OpenAI(
        api_key="ollama",  # Dummy Key – Ollama braucht keinen
        base_url="http://localhost:11434/v1"
    )

    response = client.chat.completions.create(
        model=settings.llm_model,  # "llama3"
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens
    )
    return response.choices[0].message.content


def _anthropic_response(
    messages: list[dict],
    temperature: float,
    max_tokens: int
) -> str:
    """
    Anthropic Claude.
    Anderes API Format – system message separat.
    """
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    # Anthropic trennt system message vom Rest
    system_msg = ""
    user_messages = []

    for msg in messages:
        if msg["role"] == "system":
            system_msg = msg["content"]
        else:
            user_messages.append(msg)

    response = client.messages.create(
        model=settings.llm_model,  # "claude-opus-4-6"
        max_tokens=max_tokens,
        temperature=temperature,
        system=system_msg,
        messages=user_messages
    )
    return response.content[0].text