import unittest

from functions import main

# The frozen 19-name re-export contract from design section 1. Tests patch these
# attributes on the main module, so none may ever be dropped.
FROZEN_ALL = [
    "_SAGEMAKER_RUNTIME",
    "_build_decider_questions",
    "_create_upload_request",
    "_get_media_key",
    "_invoke_decider_with_client",
    "_media_metadata",
    "_parse_request",
    "_response",
    "_retrieve_knowledge",
    "_select_decider_options",
    "extract_facts_from_media",
    "lambda_handler",
    "_invoke_decider",
    "_build_situation_questions",
    "_retrieve_knowledge_exam",
    "_retrieve_knowledge_situation",
    "build_response",
    "decide",
    "logger",
]


class ReexportTests(unittest.TestCase):
    def test_all_contains_every_frozen_name(self):
        self.assertEqual(set(main.__all__), set(FROZEN_ALL))
        self.assertEqual(len(FROZEN_ALL), 19)

    def test_every_frozen_name_is_an_attribute_of_main(self):
        for name in FROZEN_ALL:
            self.assertTrue(hasattr(main, name), f"main is missing {name!r}")


if __name__ == "__main__":
    unittest.main()
