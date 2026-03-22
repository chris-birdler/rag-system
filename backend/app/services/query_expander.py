# backend/app/services/query_expander.py

#from openai import OpenAI
from backend.app.core.config import settings
from backend.app.services.llm import get_llm_response


class QueryExpander:
    """
    Erweitert eine Query um bessere Retrieval-Ergebnisse zu erzielen.

    Zwei Strategien:
    - multi_query: generiert N reformulierte Queries
    - hyde:        generiert eine hypothetische Antwort als Query
    """

    def __init__(self):
        pass

    def expand(
        self,
        query: str,
        strategy: str = "multi_query",
        n_queries: int = 3
    ) -> list[str]:
        """
        Gibt Liste von Queries zurück – Original + Erweiterungen.
        Immer inkl. Original damit nichts verloren geht.
        """
        if strategy == "multi_query":
            expanded = self._multi_query(query, n_queries)
        elif strategy == "hyde":
            expanded = self._hyde(query)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        # Original immer zuerst
        return [query] + expanded
    
    def _multi_query(self, query: str, n: int) -> list[str]:
        """
        Generiert N alternative Formulierungen der Query.
        Nützlich wenn die originale Query zu spezifisch oder
        zu vage ist.
        """
        response = get_llm_response(messages=[{
                "role": "user",
                "content": f"""You are helping search scientific physics papers.
    Generate exactly {n} alternative search queries using DIFFERENT vocabulary and terminology.
    Do NOT just rephrase - use synonyms, related technical terms, and specific units.

    Example:
    Original: "What temperature was used?"
    Good alternatives:
    - "kelvin cooling experimental conditions"  
    - "low temperature measurement physics experiment"
    - "thermal conditions sample characterization"
Respond ONLY with a JSON array of strings, nothing else.

Query: {query}

Example output format:
["query1", ..., "query{n}"]"""
            }],
            temperature=0,
        )

        import json
        try:
            data = json.loads(response)
            
            # Beide Fälle abfangen:
            if isinstance(data, list):
                queries = data
            elif isinstance(data, dict):
                queries = data.get("queries", [])
            else:
                queries = []
            
            return queries[:n]
        except json.JSONDecodeError:
            return []

    def _hyde(self, query: str) -> list[str]:
        """
        HyDE: Hypothetical Document Embedding.

        Generiert eine hypothetische Antwort im Stil eines
        wissenschaftlichen Papers. Diese Antwort enthält
        wahrscheinlich ähnliche Terme wie die echte Antwort.

        Beispiel:
        Query: "What temperature was used?"
        HyDE:  "The measurements were performed at 40 K using
                a SQUID-VSM magnetometer under applied fields
                up to 7 T."
        → dieser Text findet den echten Chunk besser als die Query
        """
        response = get_llm_response(messages=[{
                "role": "user",
                "content": f"""Write a short hypothetical passage from a 
scientific paper that would answer this question.
Write 2-3 sentences in the style of a scientific paper.
Do NOT say "the answer is" - just write the passage directly.

Question: {query}"""
            }],
            temperature=0.3
        )

        hyde_text = response.choices[0].message.content.strip()
        return [hyde_text]