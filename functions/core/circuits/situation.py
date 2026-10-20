"""Situation circuit: free-form driving-scene VLM schema, prompt and the
3-intention Decider question builder.

The VLM only perceives the scene and proposes exactly 3 plausible driver
intentions as free-form French labels. It must NOT judge legality: the Decider
alone decides whether each intention is conforme au Code de la route.
"""

from typing import Any

from ..errors import UpstreamError

SITUATION_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "scene_summary": {
            "type": "string",
            "maxLength": 600,
            "description": "Description physique objective de la scène, sans jugement légal.",
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 12,
        },
        "signals": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 12,
            "description": "Panneaux, feux, marquages visibles (description factuelle).",
        },
        "road_users": {
            "type": "array",
            "items": {"type": "string"},
            "maxItems": 12,
            "description": "Usagers visibles: véhicules, piétons, cyclistes, etc.",
        },
        "intentions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string", "maxLength": 200},
            "description": "Exactement 3 intentions plausibles du conducteur, en français, libres.",
        },
    },
    "required": ["scene_summary", "keywords", "signals", "road_users", "intentions"],
    "additionalProperties": False,
}

SITUATION_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "analyze_driving_situation",
                "description": "Enregistre l'analyse factuelle de la situation de conduite et 3 intentions possibles.",
                "inputSchema": {"json": SITUATION_JSON_SCHEMA},
            }
        }
    ],
    "toolChoice": {"tool": {"name": "analyze_driving_situation"}},
}

SITUATION_SYSTEM_VLM_PROMPT = """Tu es le Moteur de Perception Visuelle de RoadGuard-Decider en mode Conduite.

TON OBJECTIF :
Analyser la scène de conduite fournie et renseigner rigoureusement l'outil structuré `analyze_driving_situation`.

RÈGLES D'OBSERVATION :
- Décris UNIQUEMENT ce qui est physiquement visible dans la scène : panneaux, feux, marquages, usagers (véhicules, piétons, cyclistes), environnement.
- Renseigne `scene_summary`, `keywords`, `signals` et `road_users` de manière strictement factuelle.

RÈGLE SUR LES INTENTIONS :
- Propose EXACTEMENT 3 intentions plausibles du conducteur, formulées comme des actions libres en français (ex: « S'engager dans le carrefour », « Céder le passage au piéton », « Se rabattre sur la voie de droite »).
- Ce sont des propositions ouvertes, PAS une liste fermée.

INTERDICTION ABSOLUE :
- N'émets AUCUN jugement de légalité. N'utilise JAMAIS les mots « autorisé », « interdit », « permis », « défendu », « légal », « illégal », « obligatoire », « a le droit » ou équivalents.
- Seul le Decider juge la conformité au Code de la route. Toi, tu perçois et tu proposes des intentions.

Langue obligatoire : tous les champs doivent être rédigés STRICTEMENT en français.
"""


def _build_situation_questions(
    facts: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    intentions = facts.get("intentions")
    if (
        not isinstance(intentions, list)
        or len(intentions) != 3
        or not all(
            isinstance(intention, str) and intention.strip()
            for intention in intentions
        )
    ):
        raise UpstreamError(
            "Le modèle visuel doit proposer exactement 3 intentions."
        )

    questions: dict[str, dict[str, Any]] = {}
    question_metadata: dict[str, dict[str, Any]] = {}
    for index, intention in enumerate(intentions, start=1):
        label = intention.strip()
        question_key = str(index)
        questions[question_key] = {
            "type": "noul",
            "instructions": (
                "Au vu de la situation routière décrite, l'intention suivante "
                f"du conducteur est-elle conforme au Code de la route : « {label} » ?"
            ),
            "criteria": {
                "true": "L'intention est conforme au Code de la route (autorisée).",
                "false": "L'intention n'est pas conforme au Code de la route (interdite).",
            },
        }
        question_metadata[question_key] = {
            "mode": "binary",
            "true_label": "Autorisé",
            "false_label": "Interdit",
            "candidates": {
                "Autorisé": {"id": None, "label": "Autorisé"},
                "Interdit": {"id": None, "label": "Interdit"},
            },
        }
    return questions, question_metadata
