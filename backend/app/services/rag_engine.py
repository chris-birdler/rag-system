# backend/app/services/rag_engine.py

"""
RAGEngine – verbindet Retrieval mit LLM Antwort-Generierung.

Öffentliche API:
    engine = RAGEngine()
    answer = engine.ask("What is the coercive field?")
    answer = engine.ask("...", use_expansion=True)
"""

from backend.app.services.library import PaperLibrary
from backend.app.services.llm import get_llm_response
from backend.app.core.config import settings


# System Prompt – Engineer-Aufgabe:
# Definiert wie das LLM antwortet.
# Präzise, wissenschaftlich, mit Quellenangaben.
SYSTEM_PROMPT = """You are a scientific research assistant specializing in 
condensed matter physics and materials science.

Your task: Answer questions based ONLY on the provided paper excerpts.

Rules:
- Base your answer strictly on the provided context
- Always cite your sources: mention the paper title, authors, year, and page
- If the context does not contain enough information, say so clearly
- Use precise scientific language
- Structure your answer: direct answer first, then details
- If multiple papers address the question, synthesize the information
- For questions about conditions or mechanisms: always explain the 
  PHYSICAL MEANING, not just the mathematical formula
- For questions about "why" or "how": explain the underlying mechanism
  step by step

Format for citations: [Author name et al. (Year), Page X, Section Name]
"""


class RAGEngine:

    def __init__(self, persist_directory: str = ".chroma"):
        self._library = PaperLibrary(persist_directory)

    def ask(
        self,
        question: str,
        history: list[dict] = None,
        use_expansion: bool = False,
        n_chunks: int = 5,
        show_sources: bool = True
    ) -> dict:
        """
        Stellt eine Frage und gibt eine vollständige Antwort zurück.

        Args:
            question:      Die Frage des Users
            use_expansion: Query Expansion verwenden
            n_chunks:      Wie viele Chunks ans LLM schicken
            show_sources:  Quellenangaben in Output

        Returns:
            {
                "answer":   "...",
                "sources":  [...],
                "question": "..."
            }
        """
        # Schritt 1: Retrieval
        if use_expansion:
            chunks = self._library.search_expanded(
                question, n_results=n_chunks
            )
        else:
            chunks = self._library.search_with_rerank(
                question, n_results=n_chunks
            )

        if not chunks:
            return {
                "answer": "No relevant information found in the library.",
                "sources": [],
                "question": question
            }

        # Schritt 2: Kontext aufbauen
        context = self._build_context(chunks)

        # Schritt 3: LLM Prompt
        # Messages aufbauen MIT History
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Vorherige Nachrichten einbauen
        if history:
            messages.extend(history)

        messages.append({
            "role": "user", 
            "content": f"""Paper excerpts:

        {context}

        Question: {question}

        Please answer based on the provided excerpts."""
        })

        # Schritt 4: LLM Antwort
        answer = get_llm_response(
            messages=messages,
            temperature=0.3,  # etwas Kreativität für Formulierung
            max_tokens=1000
        )

        # Schritt 5: Quellen aufbereiten
        sources = self._extract_sources(chunks)

        return {
            "answer": answer,
            "sources": sources,
            "question": question
        }

    def _build_context(self, chunks: list[dict]) -> str:
        """
        Baut den Kontext-String aus Chunks.

        Jeder Chunk bekommt eine Nummer und Quelleninfo –
        das LLM kann dann präzise zitieren.
        """
        context_parts = []

        for i, chunk in enumerate(chunks, 1):
            # Quelleninfo für diesen Chunk
            source_info = f"[{i}] {chunk.get('title', 'Unknown')}"
            if chunk.get('authors'):
                # Nur ersten Autor + et al.
                first_author = chunk['authors'].split(',')[0]
                source_info += f" ({first_author} et al., {chunk.get('year', '?')})"
            source_info += f" | Page {chunk.get('page', '?')} | {chunk.get('section', '')}"

            context_parts.append(f"{source_info}\n{chunk['text']}\n")

        return "\n---\n".join(context_parts)

    def _extract_sources(self, chunks: list[dict]) -> list[dict]:
        """
        Extrahiert eindeutige Quellen aus den verwendeten Chunks.
        Dedupliziert nach Paper (nicht nach Chunk).
        """
        seen = set()
        sources = []

        for chunk in chunks:
            doi = chunk.get('doi', '')
            if doi and doi not in seen:
                seen.add(doi)

                # Fix: Nachname = zweites Wort
                first_author = chunk['authors'].split(',')[0]
                sources.append({
                    "title": chunk.get('title', ''),
                    "authors": chunk.get('authors', ''),
                    "year": chunk.get('year', ''),
                    "doi": doi,
                    "page": chunk.get('page', ''),
                    "section": chunk.get('section', ''),
                    "relevance": chunk.get('similarity', 0)
                })

        return sources