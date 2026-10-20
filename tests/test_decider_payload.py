import io
import json
import os
import unittest
from unittest.mock import patch

from functions import main


class DeciderPayloadTests(unittest.TestCase):
    def test_builds_choice_questions_in_system_one_schema(self):
        facts = {
            "question_type": "single_choice",
            "sub_questions": [
                {
                    "text": "Quelle option est correcte ?",
                    "candidates": [
                        {"id": "A", "label": "Tourner à gauche"},
                        {"id": "B", "label": "Continuer tout droit"},
                    ],
                }
            ],
        }

        questions, metadata = main._build_decider_questions(facts)

        self.assertEqual(
            questions,
            {
                "1": {
                    "type": "choice",
                    "instructions": "Quelle option est correcte ?",
                    "criteria": {
                        "Tourner à gauche": "Candidat A",
                        "Continuer tout droit": "Candidat B",
                    },
                }
            },
        )
        self.assertEqual(metadata["1"]["mode"], "single_choice")

    def test_selects_multiple_choice_options_at_uniform_probability_threshold(self):
        facts = {
            "question_type": "multiple_choice",
            "sub_questions": [
                {
                    "text": "Quelles options sont correctes ?",
                    "candidates": [
                        {"id": "A", "label": "Option A"},
                        {"id": "B", "label": "Option B"},
                        {"id": "C", "label": "Option C"},
                    ],
                }
            ],
        }
        _, metadata = main._build_decider_questions(facts)
        decision = {
            "answers": {
                "1": {
                    "type": "choice",
                    "choice": "Option B",
                    "probabilities": {
                        "Option A": 0.2,
                        "Option B": 0.45,
                        "Option C": 0.35,
                    },
                    "confidence": 0.25,
                }
            }
        }

        result = main._select_decider_options(decision, metadata)

        self.assertAlmostEqual(result["answers"]["1"]["threshold"], 1 / 3)
        self.assertEqual(
            result["answers"]["1"]["selected_options"],
            ["Option B", "Option C"],
        )

    def test_normalizes_binary_yes_no_question(self):
        facts = {
            "question_type": "single_choice",
            "sub_questions": [
                {
                    "text": "Est-il permis de continuer ?",
                    "candidates": [
                        {"id": "A", "label": "OUI"},
                        {"id": "B", "label": "NON"},
                    ],
                }
            ],
        }
        questions, metadata = main._build_decider_questions(facts)

        self.assertEqual(questions["1"]["type"], "noul")
        decision = {
            "answers": {
                "1": {
                    "type": "noul",
                    "noul": 0.8,
                }
            }
        }
        result = main._select_decider_options(decision, metadata)
        self.assertEqual(result["answers"]["1"]["selected_options"], ["OUI"])

    def test_invokes_endpoint_with_wire_payload_and_processes_response(self):
        facts = {
            "question_type": "multiple_choice",
            "sub_questions": [
                {
                    "text": "Quelles options sont correctes ?",
                    "candidates": [
                        {"id": "A", "label": "Option A"},
                        {"id": "B", "label": "Option B"},
                    ],
                }
            ],
        }
        endpoint_response = {
            "answers": {
                "1": {
                    "type": "choice",
                    "choice": "Option A",
                    "probabilities": {"Option A": 0.7, "Option B": 0.3},
                    "confidence": 0.4,
                }
            }
        }

        with (
            patch.dict(os.environ, {"DECIDER_ENDPOINT": "test-endpoint"}),
            patch.object(
                main._SAGEMAKER_RUNTIME,
                "invoke_endpoint",
                return_value={
                    "Body": io.BytesIO(json.dumps(endpoint_response).encode())
                },
            ) as invoke_endpoint,
        ):
            result = main._invoke_decider(facts, [])

        sent_payload = json.loads(invoke_endpoint.call_args.kwargs["Body"])
        invoke_kwargs = invoke_endpoint.call_args.kwargs
        self.assertEqual(
            set(sent_payload),
            {"state", "questions"},
        )
        self.assertIn('"question_type": "multiple_choice"', sent_payload["state"])
        self.assertEqual(
            sent_payload["questions"],
            {
                "1": {
                    "type": "choice",
                    "instructions": "Quelles options sont correctes ?",
                    "criteria": {
                        "Option A": "Candidat A",
                        "Option B": "Candidat B",
                    },
                }
            },
        )
        self.assertEqual(invoke_kwargs["ContentType"], "application/json")
        self.assertEqual(invoke_kwargs["Accept"], "application/json")
        self.assertEqual(invoke_kwargs["EndpointName"], "test-endpoint")
        self.assertIsInstance(invoke_kwargs["Body"], bytes)
        self.assertEqual(result["answers"]["1"]["selected_options"], ["Option A"])


if __name__ == "__main__":
    unittest.main()
