"""
Cost Repository – liest und schreibt Cost Entries in SQLite.
Ersetzt den In-Memory CostTracker.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.db.models import CostEntry
from datetime import datetime

PRICES = {
    "gpt-4o-mini": {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
    "gpt-4o":      {"input": 2.50  / 1_000_000, "output": 10.00 / 1_000_000},
    "deepseek-chat": {"input": 0.27 / 1_000_000, "output": 1.10 / 1_000_000},
    "text-embedding-3-large": {"input": 0.130 / 1_000_000, "output": 0},
    "text-embedding-3-small": {"input": 0.020 / 1_000_000, "output": 0},
}


def log_cost(
    db: Session,
    model: str,
    input_tokens: int,
    output_tokens: int = 0,
    call_type: str = "llm"
) -> float:
    """Kosten in DB speichern."""
    price = PRICES.get(model, {"input": 0, "output": 0})
    cost = input_tokens * price["input"] + output_tokens * price["output"]

    entry = CostEntry(
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        call_type=call_type
    )
    db.add(entry)
    db.commit()
    return cost


def get_summary(db: Session) -> dict:
    """Kosten Zusammenfassung aus DB."""
    entries = db.query(CostEntry).all()

    if not entries:
        return {"total_cost_usd": 0, "total_calls": 0, "breakdown": {}}

    total = sum(e.cost_usd for e in entries)

    breakdown = {}
    for e in entries:
        if e.model not in breakdown:
            breakdown[e.model] = {
                "calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0
            }
        breakdown[e.model]["calls"] += 1
        breakdown[e.model]["input_tokens"] += e.input_tokens
        breakdown[e.model]["output_tokens"] += e.output_tokens
        breakdown[e.model]["cost_usd"] += e.cost_usd

    return {
        "total_cost_usd": round(total, 6),
        "total_cost_eur": round(total * 0.92, 6),
        "total_calls": len(entries),
        "breakdown": {
            model: {**data, "cost_usd": round(data["cost_usd"], 6)}
            for model, data in breakdown.items()
        }
    }
