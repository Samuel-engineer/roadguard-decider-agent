import json
import os
from typing import Any

from .aws import _BEDROCK_AGENT_RUNTIME


def _retrieval_question_context(facts: dict[str, Any]) -> str:
    parts = []
    sub_questions = facts.get("sub_questions", [])
    if not isinstance(sub_questions, list):
        return ""

    for sub_question in sub_questions:
        if not isinstance(sub_question, dict):
            continue

        text = sub_question.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())

        candidates = sub_question.get("candidates", [])
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            label = candidate.get("label")
            if (
                isinstance(label, str)
                and label.strip()
                and label.strip().casefold() not in {"oui", "non"}
            ):
                parts.append(label.strip())

    return "\n".join(parts)


def _retrieve_knowledge(facts: dict[str, Any]) -> list[dict[str, Any]]:
    visual_context = json.dumps(
        {
            key: value
            for key, value in facts.items()
            if key not in {"sub_questions", "question_type"}
        },
        ensure_ascii=False,
    )
    question_context = _retrieval_question_context(facts)
    query = "\n".join(part for part in (question_context, visual_context) if part)
    response = _BEDROCK_AGENT_RUNTIME.retrieve(
        knowledgeBaseId=os.environ["KNOWLEDGE_BASE_ID"],
        retrievalQuery={"text": query[:20000]},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
    )

    references = []
    for result in response.get("retrievalResults", []):
        content = result.get("content", {})
        references.append(
            {
                "text": content.get("text", ""),
                "score": result.get("score"),
                "location": result.get("location"),
            }
        )
    return references
