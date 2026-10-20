"""Tests du pattern « politique en forme fermée ».

On vérifie que ``ClosedFormPolicyHandler`` classe une scène via ``decide`` (avec
un endpoint SageMaker simulé) et renvoie une classification en forme fermée pour
les DEUX variantes (``choice`` et ``noul``). Les tests sautent proprement si
``strands-agents`` n'est pas installé.
"""

import io
import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "patterns" / "closed-form-policy"))

try:
    import strands  # noqa: F401

    _HAS_STRANDS = True
except ImportError:
    _HAS_STRANDS = False

from functions import main
from functions.core.decider import decide


class _StubBody(io.BytesIO):
    pass


def _stub_runtime(response):
    class _Runtime:
        def invoke_endpoint(self, **_kwargs):
            return {"Body": _StubBody(json.dumps(response).encode("utf-8"))}

    return _Runtime()


@unittest.skipUnless(_HAS_STRANDS, "strands-agents n'est pas installé")
class ClosedFormPolicyHandlerTests(unittest.TestCase):
    def _make_handler(self, variant, response):
        from handler import ClosedFormPolicyHandler

        return ClosedFormPolicyHandler(
            variant=variant,
            decide=decide,
            runtime=_stub_runtime(response),
        )

    def test_noul_variant_classifies_three_intentions(self):
        facts = {
            "scene_summary": "Carrefour urbain au feu vert.",
            "intentions": [
                "S'engager dans le carrefour",
                "Céder le passage au piéton",
                "Accélérer avant le piéton",
            ],
        }
        response = {
            "answers": {
                "1": {"type": "noul", "noul": 0.72},
                "2": {"type": "noul", "noul": 0.95},
                "3": {"type": "noul", "noul": 0.08},
            }
        }
        handler = self._make_handler("noul", response)

        with patch.dict(os.environ, {"DECIDER_ENDPOINT": "stub"}):
            outcome = handler.evaluate(facts)

        self.assertTrue(outcome.allow)
        self.assertEqual(len(outcome.cards), 3)
        self.assertTrue(all(card["kind"] == "allow_deny" for card in outcome.cards))
        first_options = {opt["label"]: opt for opt in outcome.cards[0]["options"]}
        self.assertTrue(first_options["Autorisé"]["selected"])
        self.assertFalse(first_options["Interdit"]["selected"])
        last_options = {opt["label"]: opt for opt in outcome.cards[2]["options"]}
        self.assertTrue(last_options["Interdit"]["selected"])

    def test_choice_variant_classifies_exam_question(self):
        facts = {
            "question_type": "single_choice",
            "sub_questions": [
                {
                    "text": "Quelle manœuvre est correcte ?",
                    "candidates": [
                        {"id": "A", "label": "Tourner à gauche"},
                        {"id": "B", "label": "Continuer tout droit"},
                    ],
                }
            ],
        }
        response = {
            "answers": {
                "1": {
                    "type": "choice",
                    "choice": "Continuer tout droit",
                    "probabilities": {
                        "Tourner à gauche": 0.3,
                        "Continuer tout droit": 0.7,
                    },
                    "confidence": 0.4,
                }
            }
        }
        handler = self._make_handler("choice", response)

        with patch.dict(os.environ, {"DECIDER_ENDPOINT": "stub"}):
            outcome = handler.evaluate(facts)

        self.assertEqual(len(outcome.cards), 1)
        self.assertEqual(outcome.cards[0]["kind"], "choice")
        selected = [
            opt["label"]
            for opt in outcome.cards[0]["options"]
            if opt["selected"]
        ]
        self.assertEqual(selected, ["Continuer tout droit"])

    def test_before_tool_call_returns_strands_action(self):
        from strands.interventions import Deny, Proceed

        facts = {
            "scene_summary": "Carrefour.",
            "intentions": [
                "S'engager dans le carrefour",
                "Céder le passage au piéton",
                "Accélérer avant le piéton",
            ],
        }
        response = {
            "answers": {
                "1": {"type": "noul", "noul": 0.9},
                "2": {"type": "noul", "noul": 0.9},
                "3": {"type": "noul", "noul": 0.9},
            }
        }
        handler = self._make_handler("noul", response)

        class _Event:
            def __init__(self):
                self.tool_use = {"input": {"facts": facts}}

        with patch.dict(os.environ, {"DECIDER_ENDPOINT": "stub"}):
            action = handler.before_tool_call(_Event())

        self.assertIsInstance(action, (Proceed, Deny))
        self.assertIsInstance(action, Proceed)
        self.assertIsNotNone(handler.last_outcome)

    def test_unknown_variant_rejected(self):
        from handler import ClosedFormPolicyHandler

        with self.assertRaises(ValueError):
            ClosedFormPolicyHandler(variant="bogus", decide=decide)

    def test_handler_shares_production_decide(self):
        # Sanity: the pattern uses the SAME decide imported from functions.
        from handler import evaluate_policy

        self.assertIs(decide, main.decide)
        self.assertTrue(callable(evaluate_policy))


if __name__ == "__main__":
    unittest.main()
