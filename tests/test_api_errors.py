import json
import os
import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError

from functions import main
from functions.core.errors import RequestError
from functions.core.media import _read_image


class ApiErrorTests(unittest.TestCase):
    def test_handler_waits_for_visual_facts_and_knowledge_before_decider(self):
        event = {
            "rawPath": "/query",
            "body": json.dumps(
                {
                    "content_type": "image/png",
                    "s3_key": "requests/image.png",
                }
            ),
        }
        facts = {
            "question_type": "single_choice",
            "scene_summary": "Un feu rouge.",
            "sub_questions": [
                {
                    "text": "Quelle option est correcte ?",
                    "candidates": [
                        {"id": "A", "label": "Option A"},
                        {"id": "B", "label": "Option B"},
                    ],
                }
            ],
        }
        references = [{"text": "Documentation pertinente", "score": 0.9}]
        decision = {
            "answers": {
                "1": {
                    "type": "choice",
                    "probabilities": {"Option A": 0.7, "Option B": 0.3},
                    "selected_options": ["Option A"],
                }
            }
        }
        completed_stages = []

        def extract_visual_facts(*args, **kwargs):
            completed_stages.append("extract_visual_facts")
            return facts

        def retrieve_knowledge(received_facts, *, mode="exam"):
            self.assertEqual(received_facts, facts)
            self.assertEqual(mode, "exam")
            completed_stages.append("retrieve_knowledge")
            return references

        def decide(received_facts, received_references, runtime_client, **kwargs):
            self.assertEqual(received_facts, facts)
            self.assertEqual(received_references, references)
            completed_stages.append("invoke_decider")
            return decision, 1234

        with (
            patch.dict(os.environ, {"MEDIA_BUCKET": "media-bucket"}),
            patch.object(
                main, "_media_metadata", return_value=("image", "png", "image/png")
            ),
            patch.object(main, "_get_media_key", return_value="requests/image.png"),
            patch.object(
                main, "extract_facts_from_media", side_effect=extract_visual_facts
            ),
            patch.object(main, "_retrieve_knowledge", side_effect=retrieve_knowledge),
            patch.object(main, "decide", side_effect=decide),
        ):
            response = main.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            completed_stages,
            ["extract_visual_facts", "retrieve_knowledge", "invoke_decider"],
        )
        body = json.loads(response["body"])
        self.assertEqual(body["mode"], "exam")
        self.assertTrue(body["cards"])
        self.assertEqual(body["cards"][0]["kind"], "choice")
        self.assertEqual(body["debug"]["knowledge_references"], references)
        self.assertEqual(body["debug"]["media_key"], "requests/image.png")
        self.assertEqual(body["debug"]["elapsed_ms"], 1234)
        self.assertNotIn("decision", body)
        self.assertNotIn("visual_facts", body)
        self.assertNotIn("knowledge_references", body)
        self.assertNotIn("media_key", body)

    def test_handler_dispatches_situation_mode_through_the_backbone(self):
        event = {
            "rawPath": "/query",
            "body": json.dumps(
                {
                    "mode": "situation",
                    "content_type": "image/png",
                    "s3_key": "requests/image.png",
                }
            ),
        }
        facts = {
            "scene_summary": "Un carrefour avec un piéton.",
            "keywords": ["carrefour"],
            "signals": ["stop"],
            "road_users": ["piéton"],
            "intentions": [
                "S'engager dans le carrefour",
                "Céder le passage au piéton",
                "Se rabattre sur la voie de droite",
            ],
        }
        references = [{"text": "Article pertinent", "score": 0.8}]
        decision = {
            "answers": {
                "1": {"type": "noul", "noul": 0.9, "selected_options": ["Autorisé"]},
                "2": {"type": "noul", "noul": 0.8, "selected_options": ["Autorisé"]},
                "3": {"type": "noul", "noul": 0.2, "selected_options": ["Interdit"]},
            }
        }
        completed_stages = []

        def extract_visual_facts(*args, **kwargs):
            completed_stages.append("extract_visual_facts")
            return facts

        def retrieve_knowledge(received_facts, *, mode="exam"):
            self.assertEqual(mode, "situation")
            completed_stages.append("retrieve_knowledge")
            return references

        def decide(received_facts, received_references, runtime_client, **kwargs):
            self.assertEqual(kwargs.get("mode"), "situation")
            completed_stages.append("invoke_decider")
            return decision, 42

        with (
            patch.dict(os.environ, {"MEDIA_BUCKET": "media-bucket"}),
            patch.object(
                main, "_media_metadata", return_value=("image", "png", "image/png")
            ),
            patch.object(main, "_get_media_key", return_value="requests/image.png"),
            patch.object(
                main, "extract_facts_from_media", side_effect=extract_visual_facts
            ),
            patch.object(main, "_retrieve_knowledge", side_effect=retrieve_knowledge),
            patch.object(main, "decide", side_effect=decide),
        ):
            response = main.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            completed_stages,
            ["extract_visual_facts", "retrieve_knowledge", "invoke_decider"],
        )
        body = json.loads(response["body"])
        self.assertEqual(body["mode"], "situation")
        self.assertEqual(len(body["cards"]), 3)
        self.assertTrue(all(card["kind"] == "allow_deny" for card in body["cards"]))
        self.assertEqual(body["debug"]["knowledge_references"], references)
        self.assertEqual(body["debug"]["media_key"], "requests/image.png")

    def test_missing_mode_behaves_as_exam(self):
        event = {
            "rawPath": "/query",
            "body": json.dumps(
                {
                    "content_type": "image/png",
                    "s3_key": "requests/image.png",
                }
            ),
        }
        facts = {
            "question_type": "single_choice",
            "sub_questions": [
                {
                    "text": "Quelle option est correcte ?",
                    "candidates": [
                        {"id": "A", "label": "Option A"},
                        {"id": "B", "label": "Option B"},
                    ],
                }
            ],
        }
        decision = {
            "answers": {
                "1": {
                    "type": "choice",
                    "probabilities": {"Option A": 0.7, "Option B": 0.3},
                    "selected_options": ["Option A"],
                }
            }
        }
        seen_modes = {}

        def retrieve_knowledge(received_facts, *, mode="exam"):
            seen_modes["retrieve"] = mode
            return []

        def decide(received_facts, received_references, runtime_client, **kwargs):
            seen_modes["decide"] = kwargs.get("mode")
            return decision, 1

        with (
            patch.dict(os.environ, {"MEDIA_BUCKET": "media-bucket"}),
            patch.object(
                main, "_media_metadata", return_value=("image", "png", "image/png")
            ),
            patch.object(main, "_get_media_key", return_value="requests/image.png"),
            patch.object(main, "extract_facts_from_media", return_value=facts),
            patch.object(main, "_retrieve_knowledge", side_effect=retrieve_knowledge),
            patch.object(main, "decide", side_effect=decide),
        ):
            response = main.lambda_handler(event, None)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(body["mode"], "exam")
        self.assertEqual(seen_modes["retrieve"], "exam")
        self.assertEqual(seen_modes["decide"], "exam")

    def test_invalid_mode_returns_request_error(self):
        event = {
            "rawPath": "/query",
            "body": json.dumps(
                {
                    "mode": "autopilot",
                    "content_type": "image/png",
                    "s3_key": "requests/image.png",
                }
            ),
        }

        with patch.dict(os.environ, {"MEDIA_BUCKET": "media-bucket"}):
            response = main.lambda_handler(event, None)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 400)
        self.assertEqual(body["code"], "request_error")

    def test_missing_s3_object_becomes_actionable_not_found_error(self):
        error = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not found"}},
            "GetObject",
        )

        with (
            patch("functions.core.media._S3.get_object", side_effect=error),
            self.assertRaises(RequestError) as raised,
        ):
            _read_image("media-bucket", "requests/missing.png")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertIn("Vérifiez la clé S3", str(raised.exception))

    def test_handler_returns_request_id_for_client_and_cloudwatch_correlation(self):
        event = {
            "rawPath": "/query",
            "requestContext": {"requestId": "test-request-123"},
            "body": json.dumps(
                {
                    "content_type": "image/png",
                    "s3_key": "requests/missing.png",
                }
            ),
        }

        with (
            patch.dict(os.environ, {"MEDIA_BUCKET": "media-bucket"}),
            patch.object(
                main, "_media_metadata", return_value=("image", "png", "image/png")
            ),
            patch.object(
                main,
                "_get_media_key",
                return_value="requests/missing.png",
            ),
            patch.object(
                main,
                "extract_facts_from_media",
                side_effect=RequestError("Fichier introuvable.", status_code=404),
            ),
            self.assertLogs(main.logger, level="INFO") as logs,
        ):
            response = main.lambda_handler(event, None)

        body = json.loads(response["body"])
        self.assertEqual(response["statusCode"], 404)
        self.assertEqual(body["request_id"], "test-request-123")
        self.assertEqual(body["code"], "request_error")
        self.assertTrue(
            any(
                "request_id=test-request-123" in message
                and "stage=extract_visual_facts" in message
                for message in logs.output
            )
        )


if __name__ == "__main__":
    unittest.main()
