from __future__ import annotations

import types
import unittest

from backend.tests.test_support import reset_fake_environment


class OpenAIResponseParsingTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_fake_environment()
        from replenishment_ai import OpenAIReplenishmentNarrator

        self.narrator = OpenAIReplenishmentNarrator()

    def test_response_text_reads_nested_response_content(self) -> None:
        response = types.SimpleNamespace(
            output=[
                types.SimpleNamespace(
                    content=[
                        types.SimpleNamespace(text='{"summary":"Critical stock risk","confidence":"high"}')
                    ]
                )
            ]
        )

        self.assertIn("Critical stock risk", self.narrator._response_text(response))

    def test_parse_json_payload_accepts_wrapped_json_object(self) -> None:
        parsed = self.narrator._parse_json_payload(
            'Here is the structured response: {"answer":"Focus on late orders.","confidence":"medium"}'
        )

        self.assertEqual(parsed["answer"], "Focus on late orders.")
        self.assertEqual(parsed["confidence"], "medium")


if __name__ == "__main__":
    unittest.main()
