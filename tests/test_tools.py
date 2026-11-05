from __future__ import annotations

import json
import unittest
from pathlib import Path

from emporio_agent.policies import PolicyStore
from emporio_agent.repository import StoreRepository
from emporio_agent.tools import TOOL_DEFINITIONS, ToolDispatcher


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class ToolDispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = ToolDispatcher(
            StoreRepository(DATA_DIR),
            PolicyStore(DATA_DIR / "policy_sections.json"),
        )

    def test_unknown_tool_returns_sanitized_technical_error(self) -> None:
        result = json.loads(self.dispatcher.call("delete_order", {}))
        self.assertEqual(result["status"], "technical_error")
        self.assertNotIn("traceback", str(result).casefold())

    def test_invalid_arguments_return_sanitized_technical_error(self) -> None:
        result = json.loads(
            self.dispatcher.call("get_order_status", {"unexpected": "value"})
        )
        self.assertEqual(result["status"], "technical_error")
        self.assertNotIn("customer", str(result).casefold())

    def test_installment_tool_schema_rejects_out_of_range_counts(self) -> None:
        price_tool = next(
            tool for tool in TOOL_DEFINITIONS if tool["name"] == "calculate_price"
        )
        schema = price_tool["parameters"]["properties"]["installments"]
        self.assertEqual(schema["minimum"], 1)
        self.assertEqual(schema["maximum"], 12)

    def test_search_dispatch_supports_remaining_pages_and_specification_filters(self) -> None:
        definition = next(t for t in TOOL_DEFINITIONS if t["name"] == "search_products")
        self.assertEqual(set(definition["parameters"]["required"]), set(definition["parameters"]["properties"]))
        arguments = dict(query="", category="Violões", max_price_brl=1000,
                         only_available=True, limit=8, offset=8,
                         specification_key=None, specification_value=None)
        page = json.loads(self.dispatcher.call("search_products", arguments))
        self.assertIn(107, [p["product_id"] for p in page["products"]])
        arguments.update(offset=0, specification_key="electronics", specification_value="yes")
        filtered = json.loads(self.dispatcher.call("search_products", arguments))
        self.assertEqual(filtered["status"], "ok")
        self.assertEqual(filtered["products"][0]["product_id"], 107)


if __name__ == "__main__":
    unittest.main()
