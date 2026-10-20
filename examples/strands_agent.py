"""Exemple exécutable : un agent Strands branché sur la politique en forme fermée.

Objectif : montrer, de bout en bout et SANS AWS, comment un builder câble
``ClosedFormPolicyHandler`` dans son propre agent Strands.

Ce script :
  1. importe ``strands-agents`` (dépendance du groupe dev uniquement) ;
  2. définit un outil ``analyser_situation`` qui appelle le ``decide`` PARTAGÉ
     (le même qu'en production) via un client SageMaker *factice* ;
  3. instancie un ``Agent`` avec ``ClosedFormPolicyHandler(variant="noul",
     decide=decide)`` ;
  4. exécute UN tour sur une scène d'exemple avec un modèle *factice*
     (aucun appel réseau) ;
  5. affiche les cartes et la décision en forme fermée.

Lancer :  ``uv run python examples/strands_agent.py``
"""

from __future__ import annotations

import io
import json
import os
import sys
from collections.abc import AsyncIterable
from pathlib import Path
from typing import Any

from strands import Agent, tool
from strands.models.model import Model

# ``patterns/closed-form-policy`` contient un tiret : on l'ajoute au sys.path
# pour importer le handler comme un module simple.
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))
sys.path.insert(0, str(_REPO_ROOT / "patterns" / "closed-form-policy"))

from handler import ClosedFormPolicyHandler

from functions.core.decider import decide

# --- Scène d'exemple (telle que la produirait le VLM en mode situation) -------
SAMPLE_FACTS: dict[str, Any] = {
    "scene_summary": (
        "Intersection urbaine avec un feu tricolore au vert et un piéton "
        "engagé sur le passage protégé à droite."
    ),
    "keywords": ["intersection", "feu vert", "passage piéton"],
    "signals": ["feu tricolore vert"],
    "road_users": ["piéton", "voiture"],
    "intentions": [
        "S'engager dans le carrefour",
        "Céder le passage au piéton",
        "Accélérer pour passer avant le piéton",
    ],
}

# Réponse que renverrait l'endpoint Decider pour ces 3 intentions.
_DECIDER_RESPONSE = {
    "answers": {
        "1": {"type": "noul", "noul": 0.72},
        "2": {"type": "noul", "noul": 0.95},
        "3": {"type": "noul", "noul": 0.08},
    }
}


class _StubSageMakerRuntime:
    """Client SageMaker factice : renvoie une réponse Decider figée."""

    def invoke_endpoint(self, **_kwargs: Any) -> dict[str, Any]:
        body = json.dumps(_DECIDER_RESPONSE).encode("utf-8")
        return {"Body": io.BytesIO(body)}


class _StubModel(Model):
    """Modèle factice : émet un appel d'outil puis clôt le tour, hors-ligne.

    Au premier appel il demande l'outil ``analyser_situation`` ; une fois le
    résultat de l'outil injecté dans l'historique, il clôt le tour par un texte
    final. Aucun appel réseau n'est effectué.
    """

    def __init__(self) -> None:
        self._config: dict[str, Any] = {}

    def get_config(self) -> dict[str, Any]:
        return self._config

    def update_config(self, **model_config: Any) -> None:
        self._config.update(model_config)

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs):
        yield {"output": output_model()}

    async def stream(
        self,
        messages,
        tool_specs=None,
        system_prompt=None,
        **kwargs: Any,
    ) -> AsyncIterable[dict[str, Any]]:
        already_called = any(
            isinstance(block, dict) and "toolResult" in block
            for message in messages
            for block in message.get("content", [])
        )
        if already_called:
            yield {"messageStart": {"role": "assistant"}}
            yield {"contentBlockStart": {"start": {}}}
            yield {
                "contentBlockDelta": {
                    "delta": {"text": "Analyse de la situation terminée."}
                }
            }
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
            return

        yield {"messageStart": {"role": "assistant"}}
        yield {
            "contentBlockStart": {
                "start": {
                    "toolUse": {
                        "toolUseId": "tool-1",
                        "name": "analyser_situation",
                    }
                }
            }
        }
        yield {
            "contentBlockDelta": {
                "delta": {"toolUse": {"input": json.dumps({"facts": SAMPLE_FACTS})}}
            }
        }
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "tool_use"}}


_RUNTIME = _StubSageMakerRuntime()


@tool
def analyser_situation(facts: dict) -> str:
    """Classe une situation de conduite via le Decider partagé en forme fermée.

    Args:
        facts: Faits visuels perçus (résumé de scène + 3 intentions).
    """
    decision, elapsed_ms = decide(
        facts, [], _RUNTIME, request_id="example", mode="situation"
    )
    return json.dumps(
        {"decision": decision, "elapsed_ms": elapsed_ms}, ensure_ascii=False
    )


def main() -> None:
    # L'endpoint n'est jamais réellement contacté (client factice), mais
    # ``decide`` lit cette variable d'environnement pour nommer l'endpoint.
    os.environ.setdefault("DECIDER_ENDPOINT", "stub-decider-endpoint")

    handler = ClosedFormPolicyHandler(
        variant="noul",
        decide=decide,
        runtime=_RUNTIME,
    )

    agent = Agent(
        model=_StubModel(),
        tools=[analyser_situation],
        interventions=[handler],
        system_prompt="Tu analyses des situations de conduite.",
    )

    agent("Analyse la scène de conduite et classe les intentions possibles.")

    outcome = handler.last_outcome
    if outcome is None:
        # Repli : si l'intervention n'a pas vu l'appel d'outil, on classe
        # directement la scène d'exemple pour produire un résultat affichable.
        outcome = handler.evaluate(SAMPLE_FACTS)

    print("=== Politique en forme fermée (variante noul) ===")
    print(f"Autorisé globalement : {outcome.allow}")
    print(f"Motif : {outcome.reason}")
    print("Cartes :")
    print(json.dumps(outcome.cards, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
