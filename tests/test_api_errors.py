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
        decision = {"answers": {"1": {"selected_options": ["Option A"]}}}
        completed_stages = []

        def extract_visual_facts(*args):
            completed_stages.append("extract_visual_facts")
            return facts

        def retrieve_knowledge(received_facts):
            self.assertEqual(received_facts, facts)
            completed_stages.append("retrieve_knowledge")
            return references

        def invoke_decider(received_facts, received_references, **kwargs):
            self.assertEqual(received_facts, facts)
            self.assertEqual(received_references, references)
            completed_stages.append("invoke_decider")
            return decision

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
            patch.object(main, "_invoke_decider", side_effect=invoke_decider),
        ):
            response = main.lambda_handler(event, None)

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(
            completed_stages,
            ["extract_visual_facts", "retrieve_knowledge", "invoke_decider"],
        )
        body = json.loads(response["body"])
        self.assertEqual(body["decision"], decision)
        self.assertEqual(body["knowledge_references"], references)

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
