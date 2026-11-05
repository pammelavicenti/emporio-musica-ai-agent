from __future__ import annotations

import unittest
from decimal import Decimal
from pathlib import Path

from emporio_agent.repository import StoreRepository, parse_specifications


DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class StoreRepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository = StoreRepository(DATA_DIR)

    def test_loads_expected_source_counts(self) -> None:
        self.assertEqual(len(self.repository.tables["products"]), 65)
        self.assertEqual(len(self.repository.tables["orders"]), 20)
        self.assertEqual(len(self.repository.tables["customers"]), 50)

    def test_available_guitars_under_1000_are_filtered_and_sorted(self) -> None:
        result = self.repository.search_products(
            category="Violões", max_price_brl=1000, only_available=True
        )
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["products"])
        prices = [float(item["current_price_brl"]) for item in result["products"]]
        self.assertEqual(prices, sorted(prices))
        self.assertTrue(all(price <= 1000 for price in prices))
        self.assertTrue(all(item["available_for_sale"] for item in result["products"]))
        self.assertNotIn(96, [item["product_id"] for item in result["products"]])

    def test_discontinued_product_is_unavailable_even_with_stock(self) -> None:
        result = self.repository.search_products(
            query="Ibanez Bass 2X Electric Bass", only_available=False
        )
        product = result["products"][0]
        self.assertEqual(product["catalog_status"], "discontinued")
        self.assertGreater(product["stock_quantity"], 0)
        self.assertFalse(product["available_for_sale"])
        self.assertEqual(product["availability_reason"], "discontinued")

    def test_catalog_pages_include_shelby_beyond_initial_eight(self) -> None:
        filters = dict(category="Violões", max_price_brl=1000, only_available=True)
        first = self.repository.search_products(**filters)
        self.assertEqual((first["count"], first["returned_count"]), (12, 8))
        self.assertTrue(first["truncated"])
        self.assertEqual(first["next_offset"], 8)
        self.assertNotIn(107, [p["product_id"] for p in first["products"]])
        second = self.repository.search_products(**filters, offset=first["next_offset"])
        self.assertEqual(second["returned_count"], 4)
        self.assertIsNone(second["next_offset"])
        self.assertTrue(second["truncated"])  # this page alone is still a subset
        products = first["products"] + second["products"]
        self.assertEqual(len({p["product_id"] for p in products}), 12)
        shelby = next(p for p in products if p["product_id"] == 107)
        self.assertEqual(shelby["current_price_brl"], "799.00")
        self.assertEqual(shelby["specifications"]["electronics"], "yes")

    def test_specification_filter_searches_full_catalog_before_pagination(self) -> None:
        result = self.repository.search_products(
            category="Violões", max_price_brl=1000,
            specification_key="electronics", specification_value="YES", limit=1,
        )
        self.assertGreater(result["count"], 0)
        self.assertEqual(result["products"][0]["product_id"], 107)
        self.assertEqual(result["products"][0]["current_price_brl"], "799.00")
        self.assertTrue(all(p["specifications"]["electronics"] == "yes" for p in result["products"]))
        nylon = self.repository.search_products(
            category="Violões", max_price_brl=1000,
            specification_key="strings", specification_value="nylon", limit=20,
        )
        self.assertFalse(nylon["truncated"])
        self.assertTrue(all(p["specifications"]["strings"] == "nylon" for p in nylon["products"]))

    def test_catalog_prices_preserve_source_cents(self) -> None:
        result = self.repository.search_products(query="Giannini GN-15")
        product = result["products"][0]
        source = self.repository.products[str(product["product_id"])]
        self.assertEqual(Decimal(source["price_brl"]), Decimal("689.00"))
        self.assertEqual(product["list_price_brl"], "689.00")
        self.assertEqual(product["current_price_brl"], "689.00")

    def test_page_bounds_and_incomplete_specification_filter_are_rejected(self) -> None:
        for arguments in ({"limit": 0}, {"limit": 21}, {"limit": True},
                          {"offset": -1}, {"offset": 1.5},
                          {"specification_key": "electronics"},
                          {"specification_value": "yes"}):
            with self.subTest(arguments=arguments):
                self.assertEqual(self.repository.search_products(**arguments)["status"], "invalid_request")

    def test_empty_search_and_exhausted_page_have_consistent_metadata(self) -> None:
        for arguments in ({"query": "nonexistent-model"}, {"offset": 1000}):
            with self.subTest(arguments=arguments):
                result = self.repository.search_products(**arguments)
                self.assertEqual(result["returned_count"], 0)
                self.assertEqual(result["products"], [])
                self.assertIsNone(result["next_offset"])

    def test_coming_soon_product_is_unavailable_even_with_stock(self) -> None:
        result = self.repository.search_products(
            query="Kala KA-ABP-CTG", only_available=False
        )
        product = result["products"][0]
        self.assertEqual(product["catalog_status"], "coming_soon")
        self.assertGreater(product["stock_quantity"], 0)
        self.assertFalse(product["available_for_sale"])

    def test_active_promotion_uses_decimal_math(self) -> None:
        result = self.repository.calculate_price(127, "debit")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["product"]["list_price_brl"], "359.00")
        self.assertEqual(result["final_price_brl"], "323.10")

    def test_product_tools_return_structured_specifications(self) -> None:
        result = self.repository.search_products(
            query="Yamaha C40 Nylon Natural", only_available=True
        )
        product = result["products"][0]
        self.assertEqual(product["specifications_status"], "ok")
        self.assertIsInstance(product["specifications"], dict)
        self.assertEqual(product["specifications"]["top"], "Spruce")
        self.assertEqual(product["specifications"]["electronics"], "no")

    def test_malformed_specifications_are_reported_without_raw_passthrough(self) -> None:
        specifications, status = parse_specifications("not-json")
        self.assertIsNone(specifications)
        self.assertEqual(status, "invalid_json")
        specifications, status = parse_specifications('["not", "an", "object"]')
        self.assertIsNone(specifications)
        self.assertEqual(status, "unexpected_json_type")

    def test_pix_does_not_stack_with_active_promotion(self) -> None:
        result = self.repository.calculate_price(127, "pix")
        self.assertEqual(result["final_price_brl"], "323.10")
        self.assertIn("does not stack", result["discount_rule"])

    def test_pix_discount_applies_to_non_promotional_product(self) -> None:
        result = self.repository.calculate_price(81, "pix")
        self.assertEqual(result["final_price_brl"], "569.91")

    def test_conflicting_installment_rules_are_not_silently_resolved(self) -> None:
        result = self.repository.calculate_price(128, "credit", 6)
        self.assertEqual(result["status"], "policy_ambiguity")
        self.assertEqual(
            result["installment_assessment"], "needs_manager_confirmation"
        )

    def test_zero_and_out_of_range_installments_are_rejected(self) -> None:
        for installments in (0, -1, 13):
            with self.subTest(installments=installments):
                result = self.repository.calculate_price(
                    81, "credit", installments
                )
                self.assertEqual(result["status"], "invalid_request")

    def test_none_installments_explicitly_defaults_to_one(self) -> None:
        result = self.repository.calculate_price(81, "credit", None)
        self.assertEqual(result["installments"], 1)
        self.assertEqual(result["installment_values_brl"], ["599.90"])

    def test_installment_schedule_sums_exactly_to_final_price(self) -> None:
        result = self.repository.calculate_price(81, "credit", 3)
        values = [Decimal(value) for value in result["installment_values_brl"]]
        self.assertEqual(sum(values), Decimal(result["final_price_brl"]))
        self.assertEqual(result["installment_total_brl"], result["final_price_brl"])
        self.assertEqual(result["installment_value_brl"], "199.97")
        self.assertEqual(result["last_installment_value_brl"], "199.96")
        self.assertEqual(result["rounding_adjustment_brl"], "-0.01")
        self.assertIn("last installment", result["rounding_note"])

    def test_order_lookup_limits_data_after_verification(self) -> None:
        result = self.repository.get_order_status(1, "pedro.oliveira@jmail.com")
        self.assertEqual(result["status"], "ok")
        serialized = str(result)
        self.assertNotIn("Pedro Henrique", serialized)
        self.assertNotIn("(67)", serialized)
        self.assertNotIn("pedro.oliveira@jmail.com", serialized)

    def test_bad_email_and_unknown_order_have_same_privacy_response(self) -> None:
        wrong_email = self.repository.get_order_status(1, "wrong@example.com")
        unknown_order = self.repository.get_order_status(999, "wrong@example.com")
        self.assertEqual(wrong_email, unknown_order)
        self.assertEqual(wrong_email["status"], "not_found_or_not_authorized")


if __name__ == "__main__":
    unittest.main()
