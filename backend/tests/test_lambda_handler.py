from __future__ import annotations

import importlib
import json
import os
import unittest

from backend.tests.test_support import reset_fake_environment


class LambdaHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_fake_environment()
        os.environ["SCHEDULED_AGENT_ENABLED"] = "true"
        os.environ["SCHEDULED_AGENT_OWNER_ID"] = "scheduled-owner"
        os.environ["SCHEDULED_AGENT_ALLOW_DRAFTS"] = "false"
        self.lambda_handler = importlib.import_module("lambda_handler")
        importlib.reload(self.lambda_handler)

    def test_eventbridge_scheduled_event_runs_operations_agent(self) -> None:
        response = self.lambda_handler.handler(
            {"source": "aws.events", "detail-type": "Scheduled Event"},
            None,
        )
        payload = json.loads(response["body"])

        self.assertEqual(response["statusCode"], 200)
        self.assertEqual(payload["scheduled_agent"], "completed")
        self.assertEqual(payload["status"], "completed")
        self.assertTrue(payload["run_id"])


if __name__ == "__main__":
    unittest.main()
