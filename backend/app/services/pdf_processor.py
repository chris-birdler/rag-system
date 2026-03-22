# backend/app/services/pdf_processor.py

import fitz  # PyMuPDF
import re
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from backend.app.services.llm import get_llm_response
from backend.app.core.config import settings

@dataclass
class DocumentMetadata:
    filename: str
    title: Optional[str] = None
    authors: Optional[str] = None
    year: Optional[str] = None
    doi: Optional[str] = None
    abstract: Optional[str] = None
    total_pages: int = 0


@dataclass
class ProcessedDocument:
    metadata: DocumentMetadata
    pages: list[dict] = field(default_factory=list)


class PDFProcessor:

    def process(
        self,
        pdf_path: str,
        use_llm: bool = True  # True = LLM Extraktion, False = Regex
    ) -> ProcessedDocument:
        """
        Main entry point.
        use_llm=True  → schnell, robust, kostet ~$0.001 pro Paper
        use_llm=False → kostenlos, fragil, nur für bekannte Journals
        """
        path = Path(pdf_path)
        doc = fitz.open(pdf_path)
        pages = []
        full_text = ""
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text("text")
            pages.append({"page": page_num, "text": text})
            full_text += text + "\n"

        if use_llm:
            metadata = self._extract_metadata_with_llm(
                doc[0].get_text(), full_text, path.name
            )
        else:
            metadata = self._extract_metadata_with_regex(
                doc, full_text, path.name
            )

        metadata.total_pages = len(doc)
        doc.close()
        return ProcessedDocument(metadata=metadata, pages=pages)

    # =========================================================
    # LLM-BASED EXTRACTION (empfohlen)
    # =========================================================

    def _extract_metadata_with_llm(
        self,
        first_page: str,
        full_text: str,
        filename: str
    ) -> DocumentMetadata:
        """
        Nutzt GPT-4o-mini um Metadaten zu extrahieren.
        Funktioniert für alle Journals ohne Anpassung.
        Kosten: ~$0.001 pro Paper.
        """

        # DOI per Regex vorher holen - sehr zuverlässig und spart LLM-Kosten
        doi = None
        doi_match = re.search(r'10\.\d{4,}/[^\s]+', full_text)
        if doi_match:
            doi = doi_match.group(0).rstrip('.,)')

        
        response = get_llm_response(messages=[{
                "role": "user",
                "content": f"""Extract metadata from this scientific paper.
Respond ONLY with valid JSON, nothing else. No markdown, no explanation.

For authors field: use "Lastname, Firstname; Lastname2, Firstname2" format.

{{
  "title": "full title or null",
  "authors": "Vogler, Christoph; Heigl, Michael; ...",
  "year": "4 digit year or null",
  "abstract": "full abstract text or null"
}}

Paper text:
{first_page[:3000]}"""
            }],
            temperature=0
        )

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            # Fallback wenn LLM trotzdem kein valides JSON liefert
            data = {}

        return DocumentMetadata(
            filename=filename,
            title=data.get("title"),
            authors=data.get("authors"),
            year=data.get("year"),
            doi=doi,  # aus Regex, zuverlässiger als LLM
            abstract=data.get("abstract")
        )

    # =========================================================
    # REGEX-BASED EXTRACTION (optional, kostenlos)
    # =========================================================

    def _extract_metadata_with_regex(
        self,
        doc: fitz.Document,
        full_text: str,
        filename: str
    ) -> DocumentMetadata:
        """
        Regex-basierte Extraktion.
        Kostenlos aber fragil - funktioniert nur für bekannte Journal-Layouts.
        Aktuell unterstützt: Physical Review, ACS
        """
        metadata = DocumentMetadata(filename=filename)
        first_page = doc[0].get_text()

        # --- DOI ---
        doi_match = re.search(r'10\.\d{4,}/[^\s]+', full_text)
        if doi_match:
            metadata.doi = doi_match.group(0).rstrip('.,)')

        # --- Year ---
        year_match = re.search(r'\b(19[9][0-9]|20[0-2][0-9])\b', full_text[:500])
        if year_match:
            metadata.year = year_match.group(0)

        # --- Title ---
        pdf_meta = doc.metadata
        if pdf_meta.get("title") and len(pdf_meta["title"]) > 10:
            metadata.title = pdf_meta["title"].strip()
        else:
            lines = [l.strip() for l in first_page.split('\n')
                     if l.strip() and len(l.strip()) > 20]
            for line in lines:
                if not re.search(r'\d{3},\s*\d+', line):
                    metadata.title = line
                    break

        # --- Authors ---
        authors = self._regex_extract_authors(first_page)
        if authors:
            metadata.authors = authors

        # --- Abstract ---
        abstract = self._regex_extract_abstract_explicit(full_text)
        if not abstract:
            abstract = self._regex_extract_abstract_implicit(first_page)
        metadata.abstract = abstract

        return metadata

    def _regex_extract_authors(self, first_page: str) -> Optional[str]:
        lines = first_page.split('\n')

        # === ACS Strategie ===
        cite_idx = None
        for i, line in enumerate(lines):
            if 'Cite This:' in line:
                cite_idx = i
                break

        if cite_idx is not None:
            candidate_lines = []
            for i in range(cite_idx):
                stripped = lines[i].strip()
                if stripped:
                    candidate_lines.append((i, stripped))
            if not candidate_lines:
                return None
            author_start_idx = None
            for i, (line_idx, line) in enumerate(candidate_lines):
                if (re.search(r',\*?\s+[A-Z]', line) and
                        ':' not in line.split(',')[0]):
                    author_start_idx = i
                    break
            if author_start_idx is not None:
                author_lines = [line for _, line in candidate_lines[author_start_idx:]]
                combined = ' '.join(author_lines)
                combined = re.sub(r'\*', '', combined)
                combined = re.sub(r'\s+', ' ', combined).strip()
                return combined

        # === Physical Review Strategie ===
        author_lines = []
        collecting = False
        prev_line = ""

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'^[A-Z\s]+\d+,\s*\d+', stripped):
                continue
            if not collecting:
                if stripped.startswith(',') and prev_line:
                    collecting = True
                    first_author = re.sub(r'[*†‡§,]', ' ', prev_line)
                    first_author = re.sub(r'\s+', ' ', first_author).strip()
                    if first_author and len(first_author) > 2:
                        author_lines.append(first_author)
                elif ',' in stripped and len(stripped) < 80:
                    collecting = True
            if collecting:
                if re.match(r'^\d+[A-Z]', stripped):
                    break
                if any(kw in stripped for kw in
                       ['Received', 'DOI:', 'Published', 'Cite This']):
                    break
                clean = re.sub(r',?\s*\d+\s*', ' ', stripped)
                clean = re.sub(r'[*†‡§,]', ' ', clean)
                clean = re.sub(r'\s+', ' ', clean).strip()
                if clean and len(clean) > 2:
                    author_lines.append(clean)
            if collecting and len(author_lines) > 5:
                break
            if stripped and not re.match(r'^[A-Z\s]+\d+,\s*\d+', stripped):
                prev_line = stripped

        if author_lines:
            combined = ' '.join(author_lines)
            return re.sub(r'\s+', ' ', combined).strip()
        return None

    def _regex_extract_abstract_explicit(self, full_text: str) -> Optional[str]:
        patterns = [
            r'ABSTRACT[:\s]+(.*?)(?=KEYWORDS:|■\s*INTRODUCTION|INTRODUCTION)',
            r'[Aa]bstract[.\s\-—:]+(.*?)(?=\n[A-Z\s]{3,}\n|\nI\.\s|\n1\s|\nINTRODUCTION)',
            r'[Aa]bstract\s*\n+(.*?)(?=\n\n|\nI\.|\n1\.)',
        ]
        for pattern in patterns:
            match = re.search(pattern, full_text, re.DOTALL)
            if match:
                abstract = match.group(1).strip()
                abstract = re.sub(r'\s+', ' ', abstract)
                if len(abstract) > 100:
                    return abstract[:1500]
        return None

    def _regex_extract_abstract_implicit(self, first_page: str) -> Optional[str]:
        pattern = r'\(Received[^)]+\)\s*(.*?)(?=DOI:|I\.\s+INTRODUCTION)'
        match = re.search(pattern, first_page, re.DOTALL)
        if match:
            abstract = match.group(1).strip()
            abstract = re.sub(r'\s+', ' ', abstract)
            if len(abstract) > 100:
                return abstract[:1500]
        return None
