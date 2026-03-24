# evaluation/eval.py

"""
Evaluation Pipeline für das RAG System.

Misst:
1. Retrieval Recall@k  → findet das System die richtige Seite?
2. Antwort Korrektheit → ist die Antwort inhaltlich richtig?

Verwendung:
    cd rag-system
    python evaluation/eval.py
"""

import json
import sys
from pathlib import Path

# Projekt-Root zum Python Path hinzufügen
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.services.library import PaperLibrary
from backend.app.services.rag_engine import RAGEngine
from backend.app.services.llm import get_llm_response


def recall_at_k(
    library: PaperLibrary,
    question: str,
    expected_page: int,
    paper_doi: str,
    k: int = 5,
    page_tolerance: int = 1
) -> bool:
    """
    Recall@k: Ist der relevante Chunk unter den Top-k?

    Prüft:
    1. Richtiges Paper (DOI)
    2. Richtige Seite (± page_tolerance)

    page_tolerance=1 weil Chunks Seitengrenzen überspannen können.
    Funktioniert für alle Journals unabhängig von Section-Struktur.

    True  → System findet die richtige Quelle
    False → System findet sie nicht
    """
    results = library.search_with_rerank(question, n_results=k)

    for result in results:
        # 1. Richtiges Paper?
        if result.get('doi') != paper_doi:
            continue

        # 2. Richtige Seite (mit Toleranz)?
        page = result.get('page', 0)
        if abs(page - expected_page) <= page_tolerance:
            return True

    return False


def evaluate_answer(
    question: str,
    expected: str,
    actual: str
) -> dict:
    """
    LLM-as-Judge: Lässt das LLM die Antwort bewerten.

    Score 0-3:
    0 = komplett falsch
    1 = teilweise richtig
    2 = größtenteils richtig
    3 = vollständig richtig
    """
    prompt = f"""You are evaluating a RAG system answer.

Question: {question}
Expected answer (key information): {expected}
Actual answer: {actual}

Rate the actual answer from 0 to 3:
0 = completely wrong or missing key information
1 = partially correct, missing important details
2 = mostly correct, minor inaccuracies
3 = correct and complete

Be lenient with terminology – if the answer conveys the 
correct physical concept even with different wording, 
give full credit.

Respond ONLY with valid JSON:
{{"score": 0, "reason": "brief explanation"}}"""

    response = get_llm_response(
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )

    try:
        clean = response.replace('```json', '').replace('```', '').strip()
        # LaTeX Backslashes escapen
        clean = clean.replace('\\(', '(').replace('\\)', ')').replace('\\,', ',')
        return json.loads(clean)
    except json.JSONDecodeError:
        # Fallback: Score direkt aus Text extrahieren
        import re
        match = re.search(r'"score"\s*:\s*(\d)', response)
        if match:
            return {"score": int(match.group(1)), "reason": "extracted from response"}
        return {"score": 0, "reason": "Could not parse response"}


def run_evaluation(
    dataset_path: str = "evaluation/dataset.json",
    k: int = 5,
    page_tolerance: int = 1
):
    """Hauptfunktion – führt komplette Evaluation durch."""

    print("=" * 60)
    print("RAG System Evaluation")
    print("=" * 60)

    # Dataset laden
    with open(dataset_path) as f:
        dataset = json.load(f)

    questions = dataset["questions"]
    print(f"Questions:      {len(questions)}")
    print(f"Recall@k:       k={k}")
    print(f"Page tolerance: ±{page_tolerance}")
    print()

    library = PaperLibrary()
    engine = RAGEngine()

    recall_results = []
    answer_scores = []
    details = []

    for q in questions:
        print(f"Q{q['id']}: {q['question'][:]}")

        # 1. Retrieval Recall@k mit Page
        recall = recall_at_k(
            library,
            q["question"],
            q["expected_page"],
            q["paper_doi"],
            k=k,
            page_tolerance=page_tolerance
        )
        recall_results.append(recall)
        print(f"  Retrieval: {'✅' if recall else '❌'} "
              f"(expected page {q['expected_page']})")

        # 2. Antwort Qualität via LLM-as-Judge
        result = engine.ask(q["question"])
        eval_result = evaluate_answer(
            q["question"],
            q["expected_answer"],
            result["answer"]
        )
        answer_scores.append(eval_result["score"])
        print(f"  Answer:    {eval_result['score']}/3 "
              f"– {eval_result['reason'][:]}")
        print()

        details.append({
            "id": q["id"],
            "question": q["question"],
            "expected_answer": q["expected_answer"],
            "actual_answer": result["answer"][:200],
            "expected_page": q["expected_page"],
            "recall": recall,
            "answer_score": eval_result["score"],
            "answer_reason": eval_result["reason"]
        })

        import time
        time.sleep(6)

    # Zusammenfassung
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)

    recall_score = sum(recall_results) / len(recall_results)
    avg_answer = sum(answer_scores) / len(answer_scores)
    correctness = sum(1 for s in answer_scores if s >= 2) / len(answer_scores)

    print(f"Recall@{k}:             {recall_score:.2%}  "
          f"({sum(recall_results)}/{len(questions)})")
    print(f"Avg Answer Score:    {avg_answer:.2f}/3")
    print(f"Answer Correctness:  {correctness:.2%}  "
          f"({sum(1 for s in answer_scores if s >= 2)}/{len(questions)})")

    # Schwache Stellen identifizieren
    failed_recall = [d for d in details if not d["recall"]]
    failed_answers = [d for d in details if d["answer_score"] < 2]

    if failed_recall:
        print(f"\n❌ Retrieval failed for:")
        for d in failed_recall:
            print(f"  Q{d['id']}: {d['question'][:55]}")

    if failed_answers:
        print(f"\n❌ Wrong answers for:")
        for d in failed_answers:
            print(f"  Q{d['id']}: {d['question'][:55]}")
            print(f"     Expected: {d['expected_answer']}")
            print(f"     Reason:   {d['answer_reason']}")

    # Ergebnis speichern
    output = {
        "config": {
            "k": k,
            "page_tolerance": page_tolerance,
            "total_questions": len(questions)
        },
        "metrics": {
            "recall_at_k": recall_score,
            "avg_answer_score": avg_answer,
            "answer_correctness": correctness
        },
        "details": details
    }

    output_path = "evaluation/results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nResults saved to {output_path}")
    return output


if __name__ == "__main__":
    run_evaluation()
