from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from google.genai import types

from emporio_agent.agent import SupportAgent
from emporio_agent.policies import PolicyStore
from emporio_agent.repository import StoreRepository
from emporio_agent.tools import ToolDispatcher


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class FakeModels:
    def __init__(self) -> None:
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) % 2 == 1:
            function_call = SimpleNamespace(
                id="call_1",
                name="search_products",
                args={
                    "query": "Takamine GD20",
                    "category": None,
                    "max_price_brl": None,
                    "only_available": True,
                },
            )
            model_content = types.Content(
                role="model",
                parts=[
                    types.Part(
                        function_call=types.FunctionCall(
                            name=function_call.name, args=function_call.args
                        )
                    )
                ],
            )
            return SimpleNamespace(
                candidates=[SimpleNamespace(content=model_content)],
                function_calls=[function_call],
                text=None,
            )
        text = "O Takamine GD20 custa R$ 2.199,00."
        model_content = types.Content(
            role="model", parts=[types.Part.from_text(text=text)]
        )
        return SimpleNamespace(
            candidates=[SimpleNamespace(content=model_content)],
            function_calls=None,
            text=text,
        )


class FakeClient:
    def __init__(self) -> None:
        self.models = FakeModels()


class AgentTests(unittest.TestCase):
    def build_agent(self) -> tuple[SupportAgent, FakeClient]:
        repository = StoreRepository(DATA_DIR)
        policies = PolicyStore(DATA_DIR / "policy_sections.json")
        client = FakeClient()
        agent = SupportAgent(
            client=client,
            model="test-model",
            dispatcher=ToolDispatcher(repository, policies),
        )
        return agent, client

    def test_gemini_function_response_preserves_role_and_call_id(self) -> None:
        agent, client = self.build_agent()

        answer = agent.chat("Quanto custa o Takamine GD20?")

        self.assertEqual(answer, "O Takamine GD20 custa R$ 2.199,00.")
        self.assertEqual(len(client.models.calls), 2)
        second_contents = client.models.calls[1]["contents"]
        function_response_contents = [
            item
            for item in second_contents
            if item.role == "user" and item.parts[0].function_response is not None
        ]
        self.assertEqual(len(function_response_contents), 1)
        self.assertEqual(function_response_contents[0].role, "user")
        function_response = function_response_contents[0].parts[0].function_response
        tool_result = function_response.response
        self.assertEqual(function_response.id, "call_1")
        self.assertIn("Takamine GD20", str(tool_result))
        self.assertTrue(
            client.models.calls[0]["config"].automatic_function_calling.disable
        )

    def test_conversation_history_is_preserved_between_user_messages(self) -> None:
        agent, client = self.build_agent()
        agent.chat("Quanto custa o Takamine GD20?")
        agent.chat("E ele está disponível?")

        latest_contents = client.models.calls[-1]["contents"]
        user_messages = [
            item.parts[0].text
            for item in latest_contents
            if item.role == "user" and item.parts[0].text is not None
        ]
        self.assertEqual(
            user_messages,
            ["Quanto custa o Takamine GD20?", "E ele está disponível?"],
        )


if __name__ == "__main__":
    unittest.main()
