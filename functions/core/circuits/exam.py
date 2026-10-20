"""Exam circuit: QCM VLM schema, tool config and system prompt.

This module owns the exam-mode perception contract. It must NOT import from
``media.py`` at module top: the dependency edge is one-directional
(``media`` imports these constants).
"""

EXAM_JSON_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "properties": {
        "question_type": {
            "type": "string",
            "enum": ["single_choice", "multiple_choice", "unknown"],
        },
        "scene_summary": {
            "type": "string",
            "maxLength": 500,
            "description": "Décris la situation physique visible sur la route sans interprétation",
        },
        "keywords": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 10,
        },
        "sub_questions": {
            "type": "array",
            "description": "Liste des questions ou assertions posées sur l'image.",
            "minItems": 1,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Énoncé complet de la question ou de l'assertion.",
                    },
                    "candidates": {
                        "type": "array",
                        "minItems": 2,
                        "maxItems": 4,
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {
                                    "type": "string",
                                    "description": "Lettre identifiant le choix (ex: A, B, C, D).",
                                },
                                "label": {
                                    "type": "string",
                                    "description": "Texte brut de l'option d'une assertion (ex: OUI, NON, Je dois m'arreter au feu rouge).",
                                },
                            },
                            "required": ["id", "label"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["text", "candidates"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["question_type", "scene_summary", "keywords", "sub_questions"],
    "additionalProperties": False,
}

EXAM_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "extract_road_data",
                "description": "Enregistre l'analyse structurée de la scène routière.",
                "inputSchema": {"json": EXAM_JSON_SCHEMA},
            }
        }
    ],
    "toolChoice": {"tool": {"name": "extract_road_data"}},
}

EXAM_SYSTEM_VLM_PROMPT = """Tu es le Moteur de Perception Visuelle de RoadGuard-Decider, un agent d'assistance à la conduite et d'évaluation réglementaire du Code de la route.

TON OBJECTIF :
Analyser l'image de conduite fournie et renseigner rigoureusement l'outil structuré `extract_road_data`.

- RÈGLE FONDAMENTALE :
  * Chaque lettre visible à l'écran (A, B, C, D) correspond à UN UNIQUE candidat dans le JSON.
  * Si l'image comporte 4 lettres au total (A, B, C, D), la somme des candidats de toutes les `sub_questions` doit faire EXACTEMENT 4.
  * Détermine le `label` en lisant le texte relié à la lettre :
    - Si la ligne contient du texte suivi de la lettre (ex: "les roues risquent de se bloquer.... A"), le label de A est "les roues risquent de se bloquer".
    - Si la ligne contient un mot binaire suivi de la lettre (ex: "OUI.... C"), le label de C est "OUI".
  * Ne colle JAMAIS le texte de l'option A ou de l'option B à l'intérieur de `text`. Le texte de la proposition va exclusivement dans `candidates[].label`.

  RÈGLE D'OBJECTIVITÉ DU RÉSUMÉ (scene_summary) :
  - Décris UNIQUEMENT la situation physique visible sur la route (panneaux réels et couleurs, signes, marquages, usagers, environnement) sans interprétation.
  - N'UTILISE PAS le texte de la question du QCM pour composer `scene_summary`.
  - Langue obligatoire : l'ensemble des champs (`scene_summary`, `keywords`, `text`, `label`) doit être rédigé STRICTEMENT en français en respectant la nomenclature officielle.
"""

# Back-compat aliases (existing importers expect these names).
json_schema = EXAM_JSON_SCHEMA
tool_config = EXAM_TOOL_CONFIG
SYSTEM_VLM_PROMPT = EXAM_SYSTEM_VLM_PROMPT
