from __future__ import annotations

import unittest
from types import SimpleNamespace

from emporio_agent.model_access import ModelAccessError, validate_model_access


class FakeModels:
    def __init__(self, ids: list[str], calls_healthcheck: bool):
        self.ids = ids
        self.calls_healthcheck = calls_healthcheck
        self.requests = []

    def list(self):
        return [SimpleNamespace(name=f"models/{item}") for item in self.ids]

    def generate_content(self, **kwargs):
        self.requests.append(kwargs)
        calls = []
        if self.calls_healthcheck:
            calls.append(SimpleNamespace(name="healthcheck"))
        return SimpleNamespace(function_calls=calls)


class FakeClient:
    def __init__(self, ids: list[str], calls_healthcheck: bool = True):
        self.models = FakeModels(ids, calls_healthcheck)


class ModelAccessTests(unittest.TestCase):
    def test_model_must_be_listed_for_the_account(self) -> None:
        client = FakeClient(["another-model"])
        with self.assertRaises(ModelAccessError):
            validate_model_access(client, "selected-model")
        self.assertEqual(client.models.requests, [])

    def test_model_must_complete_a_forced_function_call(self) -> None:
        client = FakeClient(["selected-model"], calls_healthcheck=False)
        with self.assertRaises(ModelAccessError):
            validate_model_access(client, "selected-model")

    def test_success_confirms_listing_and_function_calling(self) -> None:
        client = FakeClient(["selected-model"])
        result = validate_model_access(client, "models/selected-model")
        self.assertTrue(result["listed_for_account"])
        self.assertTrue(result["function_call_confirmed"])
        request = client.models.requests[0]
        self.assertEqual(request["model"], "selected-model")
        function_config = request["config"].tool_config.function_calling_config
        self.assertEqual(function_config.mode.value, "ANY")
        self.assertEqual(function_config.allowed_function_names, ["healthcheck"])
        self.assertTrue(request["config"].automatic_function_calling.disable)


if __name__ == "__main__":
    unittest.main()
