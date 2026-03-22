import re
from dataclasses import dataclass
from typing import Optional
from backend.app.services.pdf_processor import ProcessedDocument
from backend.app.core.config import settings
from backend.app.services.embedder import get_embeddings

@dataclass
class Chunk:
    """
    Ein einzelner Chunk – Textabschnitt der in die Vektordatenbank kommt.
    Metadaten sind wichtig für spätere Quellenangaben.
    """
    text: str
    chunk_index: int        # Position im Dokument
    page_number: int        # Für Quellenangabe: "Seite 4"
    filename: str           # Welches Paper
    title: Optional[str]    # Für Anzeige in der UI
    authors: Optional[str]  # Für Anzeige in der UI
    year: Optional[str]     # Für Filter
    doi: Optional[str]      # Für Link zum Original
    strategy: str           # Welche Strategie wurde verwendet
    section: Optional[str] = None  # Welche Sektion: "Introduction" etc.


class Chunker:

    def chunk(
        self,
        doc: ProcessedDocument,
        strategy: str = "recursive"
    ) -> list[Chunk]:
        """
        Haupteinstiegspunkt.
        strategy: "fixed", "recursive", "semantic"
        """
        if strategy == "fixed":
            return self._fixed_size_chunking(doc)
        elif strategy == "recursive":
            return self._recursive_chunking(doc)
        elif strategy == "semantic":
            return self._semantic_chunking(doc)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    # =========================================================
    # SEKTION-ERKENNUNG
    # =========================================================

    def _split_into_sections(self, full_text: str) -> list[dict]:
        """
        Teilt wissenschaftlichen Text in Sektionen.

        Drei präzise Patterns – kein normaler Fließtext kann matchen:

        Pattern 1 – Physical Review:
            "I. INTRODUCTION", "II. EXPERIMENTS", "III. RESULTS"
            → Römische Zahl + Punkt + Großbuchstaben

        Pattern 2 – Whitelist bekannter Sektionsnamen:
            "Introduction", "Methods", "Results" etc.
            → Nur explizit gelistete Wörter

        Pattern 3 – ACS mit Symbol:
            "■ INTRODUCTION", "■ METHODS"
            → Sonderzeichen + Großbuchstaben
        """
        # Pattern 1: Physical Review Stil
        # Matcht: "I. INTRODUCTION", "II. EXPERIMENTS"
        # Matcht NICHT: normalen Text
        phys_rev = r'\n([IVX]+\.\s+[A-Z][A-Z\s]+)\n'

        # Pattern 2: Whitelist – nur bekannte Sektionsnamen
        # Matcht: "Introduction", "Methods", "Results"
        # Matcht NICHT: "We show", "The size", beliebigen Text
        known_sections = (
            'Abstract|Introduction|Background|'
            'Method|Methods|Materials|Experimental|Experiments|'
            'Results|Discussion|Conclusion|Conclusions|'
            'Acknowledgements|Acknowledgments|References|'
            'Appendix|Supplementary|Theory|Simulation|'
            'Computational|Summary'
        )
        whitelist = rf'\n({known_sections})\n'

        # Pattern 3: ACS Stil mit ■ Symbol
        acs = r'(■\s+[A-Z][A-Z\s]+)'

        # Alle drei kombinieren
        combined = f'(?:{phys_rev})|(?:{whitelist})|(?:{acs})'

        splits = re.split(combined, full_text)

        sections = []
        current_title = "Abstract"
        current_text = ""

        for part in splits:
            if part is None:
                continue
            part_stripped = part.strip()
            if not part_stripped:
                continue

            # Ist dieser Teil eine Überschrift?
            # Prüfe gegen alle drei Patterns
            is_heading = (
                # Physical Review: römische Zahl am Anfang
                bool(re.match(r'^[IVX]+\.\s+[A-Z]', part_stripped)) or
                # Whitelist: exakter Match mit bekanntem Sektionsnamen
                bool(re.match(
                    rf'^(?:{known_sections})$',
                    part_stripped,
                    re.IGNORECASE
                )) or
                # ACS: beginnt mit ■
                part_stripped.startswith('■')
            )

            if is_heading:
                # Aktuelle Sektion speichern
                if current_text.strip():
                    sections.append({
                        "title": current_title,
                        "text": current_text.strip()
                    })
                # Neue Sektion beginnen
                current_title = part_stripped
                current_text = ""
            else:
                current_text += part + "\n"

        # Letzte Sektion nicht vergessen
        if current_text.strip():
            sections.append({
                "title": current_title,
                "text": current_text.strip()
            })

        # Fallback: wenn keine Sektionen erkannt → ganzer Text als eine Sektion
        if not sections:
            sections = [{"title": "Full Text", "text": full_text}]

        return sections

    # =========================================================
    # STRATEGIE 1: FIXED SIZE
    # =========================================================

    def _fixed_size_chunking(self, doc: ProcessedDocument) -> list[Chunk]:
        """
        Einfachste Methode: schneide nach fixer Zeichenzahl.

        chunk_size und chunk_overlap kommen aus config.py.

        Beispiel mit size=1000, overlap=200:
        Chunk 1: Zeichen 0–1000
        Chunk 2: Zeichen 800–1800  ← 200 Zeichen Overlap
        Chunk 3: Zeichen 1600–2600
        """
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap

        full_text = ""
        page_boundaries = []

        for page in doc.pages:
            page_boundaries.append((len(full_text), page["page"]))
            full_text += page["text"] + "\n"

        chunks = []
        start = 0
        chunk_index = 0

        while start < len(full_text):
            end = start + chunk_size
            text = full_text[start:end].strip()

            if text:
                page_num = self._get_page_for_position(
                    start, page_boundaries
                )
                chunks.append(self._make_chunk(
                    text, chunk_index, page_num, doc, "fixed"
                ))
                chunk_index += 1

            start += chunk_size - overlap

        return chunks

    # =========================================================
    # STRATEGIE 2: RECURSIVE (Standard, empfohlen)
    # =========================================================

    def _recursive_chunking(self, doc: ProcessedDocument) -> list[Chunk]:
        """
        Intelligent + Sektion-bewusst.

        Schritt 1: Text in Sektionen aufteilen
                   (Introduction, Methods, Results...)
        Schritt 2: Jede Sektion separat chunken
                   → Abstract und Introduction können nie
                     im selben Chunk landen

        Jeder Chunk bekommt seine Sektion als Prefix:
        "[I. INTRODUCTION]
         Ferrimagnets are becoming..."

        Das verbessert Retrieval: bei "wie wurde experimentiert?"
        suchen wir in [EXPERIMENTS] Chunks.
        """
        chunk_size = settings.chunk_size
        overlap = settings.chunk_overlap
        separators = ["\n\n", "\n", ". ", " ", ""]

        full_text = ""
        page_boundaries = []

        for page in doc.pages:
            page_boundaries.append((len(full_text), page["page"]))
            full_text += page["text"] + "\n"

        # Erst in Sektionen teilen
        sections = self._split_into_sections(full_text)

        chunks = []
        chunk_index = 0
        position = 0

        for section in sections:
            # Jede Sektion separat chunken
            raw_chunks = self._recursive_split(
                section["text"], separators, chunk_size, overlap
            )

            for text in raw_chunks:
                text = text.strip()
                if not text or len(text) < 50:
                    continue

                pos = full_text.find(text, max(0, position - 100))
                if pos != -1:
                    position = pos

                page_num = self._get_page_for_position(
                    position, page_boundaries
                )

                # Sektion als Kontext prefix
                enriched_text = f"[{section['title']}]\n{text}"

                chunk = self._make_chunk(
                    enriched_text, chunk_index, page_num, doc, "recursive"
                )
                chunk.section = section["title"]
                chunks.append(chunk)
                chunk_index += 1

        return chunks

    def _recursive_split(
        self,
        text: str,
        separators: list[str],
        chunk_size: int,
        overlap: int
    ) -> list[str]:
        """
        Kernlogik: versucht bei natürlichen Grenzen zu trennen.

        Priorität:
        1. Doppelter Zeilenumbruch (Absatz)
        2. Einfacher Zeilenumbruch
        3. Satzende (". ")
        4. Leerzeichen (Wort)
        5. Notfalls: harter Schnitt
        """
        if not separators:
            return [text[i:i+chunk_size]
                    for i in range(0, len(text), chunk_size - overlap)]

        separator = separators[0]
        splits = text.split(separator) if separator else list(text)

        chunks = []
        current = ""

        for split in splits:
            candidate = current + separator + split if current else split

            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    if len(current) > chunk_size:
                        # Noch zu groß → rekursiv mit nächstem Separator
                        chunks.extend(self._recursive_split(
                            current, separators[1:], chunk_size, overlap
                        ))
                    else:
                        chunks.append(current)

                # Overlap: letzte Wörter mitnehmen
                if current and overlap > 0:
                    words = current.split()
                    overlap_text = " ".join(words[-10:])
                    current = overlap_text + separator + split
                else:
                    current = split

        if current:
            chunks.append(current)

        return chunks

    # =========================================================
    # STRATEGIE 3: SEMANTIC
    # =========================================================

    def _semantic_chunking(self, doc: ProcessedDocument) -> list[Chunk]:
        """
        Beste Qualität: trennt wo der semantische Inhalt wechselt.

        1. Text in Sätze teilen
        2. Embedding für jeden Satz berechnen
        3. Cosine Similarity zwischen aufeinanderfolgenden Sätzen
        4. Wo Similarity stark abfällt → Chunk-Grenze

        Langsamer weil Embeddings berechnet werden müssen.
        Kosten: ~$0.001 pro Paper.
        """
        from openai import OpenAI
        import numpy as np
        from backend.app.core.config import settings as cfg

        client = OpenAI(api_key=cfg.openai_api_key)

        full_text = ""
        page_boundaries = []
        for page in doc.pages:
            page_boundaries.append((len(full_text), page["page"]))
            full_text += page["text"] + "\n"

        sentences = self._split_into_sentences(full_text)
        if len(sentences) < 3:
            return self._recursive_chunking(doc)

        embeddings = self._get_embeddings(sentences, client)

        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i+1])
            similarities.append(sim)

        mean_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        threshold = mean_sim - 0.5 * std_sim

        chunks = []
        chunk_index = 0
        current_sentences = [sentences[0]]
        current_start = 0

        for i, sim in enumerate(similarities):
            if sim < threshold:
                text = " ".join(current_sentences).strip()
                if len(text) > 50:
                    position = full_text.find(sentences[current_start])
                    page_num = self._get_page_for_position(
                        position, page_boundaries
                    )
                    chunks.append(self._make_chunk(
                        text, chunk_index, page_num, doc, "semantic"
                    ))
                    chunk_index += 1
                current_sentences = [sentences[i+1]]
                current_start = i + 1
            else:
                current_sentences.append(sentences[i+1])

        if current_sentences:
            text = " ".join(current_sentences).strip()
            if len(text) > 50:
                position = full_text.find(sentences[current_start])
                page_num = self._get_page_for_position(
                    position, page_boundaries
                )
                chunks.append(self._make_chunk(
                    text, chunk_index, page_num, doc, "semantic"
                ))

        return chunks

    def _split_into_sentences(self, text: str) -> list[str]:
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences
                if s.strip() and len(s.strip()) > 20]

    # def _get_embeddings(
    #     self, texts: list[str], client
    # ) -> list[list[float]]:
    #     embeddings = []
    #     batch_size = 100
    #     for i in range(0, len(texts), batch_size):
    #         batch = texts[i:i+batch_size]
    #         response = client.embeddings.create(
    #             model="text-embedding-3-small",
    #             input=batch
    #         )
    #         embeddings.extend([e.embedding for e in response.data])
    #     return embeddings

    def _get_embeddings(self, texts):
        return get_embeddings(texts)

    def _cosine_similarity(
        self, a: list[float], b: list[float]
    ) -> float:
        import numpy as np
        a, b = np.array(a), np.array(b)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    # =========================================================
    # HILFSFUNKTIONEN
    # =========================================================

    def _get_page_for_position(
        self,
        char_position: int,
        page_boundaries: list[tuple]
    ) -> int:
        """
        Gibt Seitennummer für eine Zeichenposition zurück.

        page_boundaries: [(0, 1), (1250, 2), (2800, 3)]
        char_position:   1500
        → liegt nach 1250 aber vor 2800 → Seite 2
        """
        page_num = 1
        for start_char, page in page_boundaries:
            if char_position >= start_char:
                page_num = page
            else:
                break
        return page_num

    def _make_chunk(
        self,
        text: str,
        index: int,
        page_num: int,
        doc: ProcessedDocument,
        strategy: str
    ) -> Chunk:
        """Erstellt Chunk-Objekt mit allen Metadaten."""
        return Chunk(
            text=text,
            chunk_index=index,
            page_number=page_num,
            filename=doc.metadata.filename,
            title=doc.metadata.title,
            authors=doc.metadata.authors,
            year=doc.metadata.year,
            doi=doc.metadata.doi,
            strategy=strategy
        )