from __future__ import annotations

import csv
import json
import unicodedata
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any


CENT = Decimal("0.01")


class DataSourceError(RuntimeError):
    """Raised when a required local data source cannot be loaded."""


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def money(value: Decimal) -> str:
    return str(value.quantize(CENT, rounding=ROUND_HALF_UP))


def parse_specifications(raw_specs: str) -> tuple[dict[str, Any] | None, str]:
    """Parse the JSON object stored in the product `specs` CSV field.

    A malformed value is reported as source data quality metadata instead of being
    passed through as an opaque string to the model.
    """
    try:
        parsed = json.loads(raw_specs)
    except (TypeError, json.JSONDecodeError):
        return None, "invalid_json"
    if not isinstance(parsed, dict):
        return None, "unexpected_json_type"
    return parsed, "ok"


class StoreRepository:
    """Read-only access to the store CSVs with deterministic business rules."""

    REQUIRED_TABLES = (
        "categories",
        "customers",
        "orders",
        "order_items",
        "products",
        "promotions",
    )

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.tables = {name: self._load_table(name) for name in self.REQUIRED_TABLES}
        self.products = {row["product_id"]: row for row in self.tables["products"]}
        self.categories = {
            row["category_id"]: row for row in self.tables["categories"]
        }
        self.customers = {
            row["customer_id"]: row for row in self.tables["customers"]
        }
        self.orders = {row["order_id"]: row for row in self.tables["orders"]}
        self.active_promotions = {
            row["product_id"]: row
            for row in self.tables["promotions"]
            if row["is_active"] == "1"
        }

    def _load_table(self, table_name: str) -> list[dict[str, str]]:
        matches = list(self.data_dir.glob(f"* - {table_name}.csv"))
        if len(matches) != 1:
            raise DataSourceError(
                f"Expected one CSV for {table_name!r}, found {len(matches)}."
            )
        try:
            with matches[0].open(encoding="utf-8-sig", newline="") as stream:
                return list(csv.DictReader(stream))
        except (OSError, UnicodeError, csv.Error) as exc:
            raise DataSourceError(f"Could not load {matches[0].name}.") from exc

    def _category_name(self, product: dict[str, str]) -> str:
        category = self.categories.get(product["category_id"])
        return category["name"] if category else "Unknown"

    def _promotion_details(self, product: dict[str, str]) -> dict[str, Any] | None:
        promotion = self.active_promotions.get(product["product_id"])
        if not promotion:
            return None
        original = Decimal(product["price_brl"])
        percentage = Decimal(promotion["discount_percent"])
        promotional = original * (Decimal("100") - percentage) / Decimal("100")
        return {
            "description": promotion["description"],
            "discount_percent": money(percentage),
            "promotional_price_brl": money(promotional),
        }

    def _public_product(self, product: dict[str, str]) -> dict[str, Any]:
        stock = int(product["stock_quantity"])
        status = product["status"]
        available = status == "active" and stock > 0
        specifications, specifications_status = parse_specifications(product["specs"])
        result: dict[str, Any] = {
            "product_id": int(product["product_id"]),
            "name": product["name"],
            "category": self._category_name(product),
            "description": product["description"],
            "specifications": specifications,
            "specifications_status": specifications_status,
            "list_price_brl": money(Decimal(product["price_brl"])),
            "stock_quantity": stock,
            "catalog_status": status,
            "available_for_sale": available,
            "availability_reason": (
                "available"
                if available
                else "discontinued"
                if status == "discontinued"
                else "coming_soon"
                if status == "coming_soon"
                else "out_of_stock"
            ),
        }
        promotion = self._promotion_details(product)
        if promotion:
            result["active_promotion"] = promotion
            result["current_price_brl"] = promotion["promotional_price_brl"]
        else:
            result["active_promotion"] = None
            result["current_price_brl"] = result["list_price_brl"]
        return result

    def search_products(
        self,
        query: str = "",
        category: str | None = None,
        max_price_brl: float | int | str | None = None,
        only_available: bool = True,
        limit: int = 8,
        offset: int = 0,
        specification_key: str | None = None,
        specification_value: str | None = None,
    ) -> dict[str, Any]:
        if (
            isinstance(limit, bool)
            or not isinstance(limit, int)
            or not 1 <= limit <= 20
            or isinstance(offset, bool)
            or not isinstance(offset, int)
            or offset < 0
        ):
            return {"status": "invalid_request", "message": "Invalid page bounds."}
        if (specification_key is None) != (specification_value is None):
            return {
                "status": "invalid_request",
                "message": "Supply both specification key and value.",
            }
        query_terms = normalize_text(query).split()
        normalized_category = normalize_text(category or "")
        try:
            max_price = (
                Decimal(str(max_price_brl)) if max_price_brl is not None else None
            )
        except Exception:
            return {"status": "invalid_request", "message": "Invalid maximum price."}

        matches: list[dict[str, Any]] = []
        for product in self.tables["products"]:
            public = self._public_product(product)
            haystack = normalize_text(
                " ".join(
                    (
                        product["name"],
                        product["description"],
                        self._category_name(product),
                        product["specs"],
                    )
                )
            )
            if query_terms and not all(term in haystack for term in query_terms):
                continue
            if normalized_category and normalized_category not in normalize_text(
                self._category_name(product)
            ):
                continue
            if only_available and not public["available_for_sale"]:
                continue
            if max_price is not None and Decimal(public["current_price_brl"]) > max_price:
                continue
            if specification_key is not None:
                specs = public["specifications"] or {}
                if specification_key not in specs or normalize_text(
                    str(specs[specification_key])
                ) != normalize_text(specification_value):
                    continue
            matches.append(public)

        matches.sort(key=lambda item: (Decimal(item["current_price_brl"]), item["name"]))
        page = matches[offset : offset + limit]
        next_offset = (
            offset + len(page) if offset + len(page) < len(matches) else None
        )
        return {
            "status": "ok" if matches else "no_results",
            "count": len(matches),
            "products": page,
            "returned_count": len(page),
            "offset": offset,
            "next_offset": next_offset,
            "truncated": offset > 0 or next_offset is not None,
        }

    def calculate_price(
        self,
        product_id: int,
        payment_method: str,
        installments: int | None = None,
    ) -> dict[str, Any]:
        product = self.products.get(str(product_id))
        if product is None:
            return {"status": "not_found", "message": "Product was not found."}

        public = self._public_product(product)
        original = Decimal(product["price_brl"])
        promotion = self._promotion_details(product)
        current = (
            Decimal(promotion["promotional_price_brl"]) if promotion else original
        )
        method = normalize_text(payment_method).replace(" ", "_")
        aliases = {
            "cartao_de_credito": "credit",
            "credito": "credit",
            "credit_card": "credit",
            "cartao_de_debito": "debit",
            "debito": "debit",
            "boleto_bancario": "boleto",
        }
        method = aliases.get(method, method)
        if method not in {"pix", "credit", "debit", "boleto"}:
            return {"status": "invalid_request", "message": "Unsupported payment method."}

        discount_note = "No payment discount applies."
        if method == "pix":
            if promotion:
                discount_note = (
                    "The active promotion applies; the 5% PIX discount does not stack."
                )
            else:
                current = original * Decimal("0.95")
                discount_note = "A 5% PIX discount applies to the list price."

        final_total = current.quantize(CENT, rounding=ROUND_HALF_UP)
        result: dict[str, Any] = {
            "status": "ok" if public["available_for_sale"] else "unavailable",
            "product": public,
            "payment_method": method,
            "final_price_brl": money(final_total),
            "discount_rule": discount_note,
            "installment_assessment": None,
        }

        if method != "credit":
            if installments not in (None, 1):
                return {
                    "status": "invalid_request",
                    "message": "Installments are only supported for credit card payments.",
                }
            return result

        count = 1 if installments is None else installments
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= 12:
            return {
                "status": "invalid_request",
                "message": "Credit card installments must be between 1 and 12.",
            }
        regular_installment = (final_total / count).quantize(
            CENT, rounding=ROUND_HALF_UP
        )
        installment_values = [regular_installment] * max(0, count - 1)
        last_installment = final_total - sum(
            installment_values, start=Decimal("0.00")
        )
        installment_values.append(last_installment)
        installment_sum = sum(installment_values, start=Decimal("0.00"))
        rounding_adjustment = last_installment - regular_installment
        minimum_installment = min(installment_values)
        assessment = "allowed"
        reason = "The summary table and detailed installment rules agree."
        if count <= 3:
            if minimum_installment < Decimal("50"):
                assessment = "not_allowed"
                reason = "Detailed rules exclude installments below BRL 50.00."
            elif minimum_installment < Decimal("100"):
                assessment = "needs_manager_confirmation"
                reason = (
                    "The payment summary says a BRL 100.00 minimum, while detailed "
                    "rules allow up to 3 installments with a BRL 50.00 floor."
                )
        elif count <= 6:
            if minimum_installment < Decimal("80"):
                assessment = "not_allowed"
                reason = "Detailed rules require at least BRL 80.00 per installment."
            elif minimum_installment < Decimal("100"):
                assessment = "needs_manager_confirmation"
                reason = (
                    "The payment summary says BRL 100.00 minimum, while detailed "
                    "rules say BRL 80.00 for 4 to 6 installments."
                )
        elif minimum_installment < Decimal("100"):
            assessment = "not_allowed"
            reason = "Both policy sections require at least BRL 100.00."

        result["installments"] = count
        result["installment_value_brl"] = money(regular_installment)
        result["last_installment_value_brl"] = money(last_installment)
        result["installment_values_brl"] = [
            money(value) for value in installment_values
        ]
        result["installment_total_brl"] = money(installment_sum)
        result["rounding_adjustment_brl"] = money(rounding_adjustment)
        result["rounding_note"] = (
            "The last installment is adjusted so the installment sum exactly matches "
            "the final price."
            if rounding_adjustment
            else "No rounding adjustment is required."
        )
        result["installment_assessment"] = assessment
        result["installment_policy_note"] = reason
        if assessment == "needs_manager_confirmation":
            result["status"] = "policy_ambiguity"
        return result

    def get_order_status(self, order_id: int, email: str) -> dict[str, Any]:
        """Return a privacy-limited order view after exact e-mail verification.

        Missing orders and failed verification intentionally share one response so the
        endpoint cannot be used to enumerate valid order IDs.
        """
        order = self.orders.get(str(order_id))
        customer = self.customers.get(order["customer_id"]) if order else None
        if (
            not order
            or not customer
            or normalize_text(customer["email"].strip())
            != normalize_text(email.strip())
        ):
            return {
                "status": "not_found_or_not_authorized",
                "message": "Order not found or verification details did not match.",
            }

        items = []
        for item in self.tables["order_items"]:
            if item["order_id"] != str(order_id):
                continue
            product = self.products.get(item["product_id"])
            items.append(
                {
                    "quantity": int(item["quantity"]),
                    "product_id": int(item["product_id"]),
                    "product_name": product["name"] if product else "Unknown product",
                }
            )
        return {
            "status": "ok",
            "order": {
                "order_id": int(order["order_id"]),
                "order_date": order["order_date"],
                "order_status": order["status"],
                "total_brl": money(Decimal(order["total_brl"])),
                "payment_method": order["payment_method"],
                "tracking_code": order["tracking_code"] or None,
                "estimated_delivery": order["estimated_delivery"] or None,
                "notes": order["notes"] or None,
                "items": items,
            },
            "privacy_note": (
                "Prototype verification uses order ID plus exact registered e-mail; "
                "this is not strong authentication."
            ),
        }
