"""Unified response projection shared by both circuits.

``build_response`` turns the internal ``(facts, references, decision)`` triple
into the public ``{mode, cards, scene_summary, debug}`` shape. Selection is set
purely by membership in ``answer["selected_options"]`` (written by
``_select_decider_options``); this module performs no probability comparison.
"""

from typing import Any


def _exam_card(
    question_key: str,
    answer: dict[str, Any],
    title: str,
    candidate_labels: list[str],
) -> dict[str, Any]:
    selected_options = answer.get("selected_options") or []
    options: list[dict[str, Any]] = []
    if answer.get("type") == "noul":
        noul = answer.get("noul", 0.0)
        yes_label = next(
            (label for label in candidate_labels if label.casefold() == "oui"),
            "Oui",
        )
        no_label = next(
            (label for label in candidate_labels if label.casefold() == "non"),
            "Non",
        )
        options = [
            {
                "label": yes_label,
                "score": noul,
                "selected": yes_label in selected_options,
            },
            {
                "label": no_label,
                "score": 1 - noul,
                "selected": no_label in selected_options,
            },
        ]
    else:
        probabilities = answer.get("probabilities", {})
        for label, score in probabilities.items():
            options.append(
                {
                    "label": label,
                    "score": score,
                    "selected": label in selected_options,
                }
            )
    return {
        "id": question_key,
        "title": title,
        "kind": "choice",
        "options": options,
    }


def _situation_card(
    question_key: str,
    answer: dict[str, Any],
    intention_label: str,
) -> dict[str, Any]:
    selected_options = answer.get("selected_options") or []
    noul = answer.get("noul", 0.0)
    options = [
        {
            "label": "Autorisé",
            "score": noul,
            "selected": "Autorisé" in selected_options,
        },
        {
            "label": "Interdit",
            "score": 1 - noul,
            "selected": "Interdit" in selected_options,
        },
    ]
    return {
        "id": question_key,
        "title": intention_label,
        "kind": "allow_deny",
        "options": options,
    }


def build_response(
    mode: str,
    facts: dict[str, Any],
    references: list[dict[str, Any]],
    decision: dict[str, Any],
    media_key: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    answers = decision.get("answers", {}) if isinstance(decision, dict) else {}
    cards: list[dict[str, Any]] = []

    if mode == "situation":
        intentions = facts.get("intentions", []) or []
        for index, intention in enumerate(intentions, start=1):
            question_key = str(index)
            answer = answers.get(question_key, {})
            label = intention.strip() if isinstance(intention, str) else str(intention)
            cards.append(_situation_card(question_key, answer, label))
    else:
        sub_questions = facts.get("sub_questions", []) or []
        titles: dict[str, str] = {}
        labels_by_key: dict[str, list[str]] = {}
        for index, sub_question in enumerate(sub_questions, start=1):
            question_key = str(index)
            if not isinstance(sub_question, dict):
                continue
            text = sub_question.get("text")
            titles[question_key] = text.strip() if isinstance(text, str) else ""
            candidate_labels: list[str] = []
            for candidate in sub_question.get("candidates", []) or []:
                if isinstance(candidate, dict):
                    label = candidate.get("label")
                    if isinstance(label, str) and label.strip():
                        candidate_labels.append(label.strip())
            labels_by_key[question_key] = candidate_labels
        for question_key, answer in answers.items():
            cards.append(
                _exam_card(
                    question_key,
                    answer,
                    titles.get(question_key, ""),
                    labels_by_key.get(question_key, []),
                )
            )

    return {
        "mode": mode,
        "cards": cards,
        "scene_summary": facts.get("scene_summary", ""),
        "debug": {
            "visual_facts": facts,
            "knowledge_references": references,
            "media_key": media_key,
            "elapsed_ms": elapsed_ms,
        },
    }
