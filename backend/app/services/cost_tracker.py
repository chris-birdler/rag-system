"""
Cost Tracker – verfolgt OpenAI API Kosten.

Preise (Stand März 2026):
    gpt-4o-mini:  Input $0.150/1M tokens, Output $0.600/1M tokens
    gpt-4o:       Input $2.50/1M tokens,  Output $10.00/1M tokens
    deepseek:     Input $0.27/1M tokens,  Output $1.10/1M tokens

Verwendung:
    tracker = CostTracker()
    tracker.log(model="gpt-4o-mini", input_tokens=500, output_tokens=200)
    print(tracker.get_summary())
"""

from dataclasses import dataclass, field
from datetime import datetime


# Preise pro Token in USD
PRICES = {
    "gpt-4o-mini": {
        "input":  0.150 / 1_000_000,
        "output": 0.600 / 1_000_000,
    },
    "gpt-4o": {
        "input":  2.50 / 1_000_000,
        "output": 10.00 / 1_000_000,
    },
    "gpt-4o-mini-2024-07-18": {
        "input":  0.150 / 1_000_000,
        "output": 0.600 / 1_000_000,
    },
    "deepseek-chat": {
        "input":  0.27 / 1_000_000,
        "output": 1.10 / 1_000_000,
    },
    "text-embedding-3-large": {
        "input":  0.130 / 1_000_000,
        "output": 0,
    },
    "text-embedding-3-small": {
        "input":  0.020 / 1_000_000,
        "output": 0,
    },
}


@dataclass
class CostEntry:
    """Ein einzelner API Call."""
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    call_type: str  # "llm", "embedding", "reranker"


class CostTracker:
    """
    Singleton – eine Instanz für die gesamte App.
    Verfolgt alle API Kosten in Memory.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._entries: list[CostEntry] = []
        return cls._instance

    def log(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
        call_type: str = "llm"
    ) -> float:
        """
        API Call loggen und Kosten berechnen.
        Gibt Kosten in USD zurück.
        """
        price = PRICES.get(model, {"input": 0, "output": 0})
        cost = (
            input_tokens * price["input"] +
            output_tokens * price["output"]
        )

        self._entries.append(CostEntry(
            timestamp=datetime.utcnow(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            call_type=call_type
        ))

        return cost

    def get_summary(self) -> dict:
        """Zusammenfassung aller Kosten."""
        if not self._entries:
            return {
                "total_cost_usd": 0,
                "total_calls": 0,
                "breakdown": {}
            }

        total = sum(e.cost_usd for e in self._entries)

        # Aufschlüsselung nach Modell
        breakdown = {}
        for entry in self._entries:
            if entry.model not in breakdown:
                breakdown[entry.model] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0
                }
            breakdown[entry.model]["calls"] += 1
            breakdown[entry.model]["input_tokens"] += entry.input_tokens
            breakdown[entry.model]["output_tokens"] += entry.output_tokens
            breakdown[entry.model]["cost_usd"] += entry.cost_usd

        return {
            "total_cost_usd": round(total, 6),
            "total_cost_eur": round(total * 0.92, 6),
            "total_calls": len(self._entries),
            "breakdown": {
                model: {
                    **data,
                    "cost_usd": round(data["cost_usd"], 6)
                }
                for model, data in breakdown.items()
            }
        }

    def reset(self):
        """Kosten zurücksetzen."""
        self._entries = []