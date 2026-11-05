from __future__ import annotations

import json
from typing import Any, Callable

from emporio_agent.policies import PolicyStore
from emporio_agent.repository import StoreRepository


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "name": "search_products",
        "description": (
            "Search the live product catalog. Always use for product names, prices, "
            "stock, availability, categories, structured specifications, or recommendations. "
            "Results are paginated: count is the total matching all filters; use next_offset "
            "with unchanged filters to read remaining results, or filter by a specification."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Free-text terms from a product name, model, description, or "
                        "specification. Leave empty when filtering only by category."
                    ),
                },
                "category": {
                    "type": ["string", "null"],
                    "description": (
                        "Catalog category such as Violões, Guitarras, Baixos, "
                        "Teclados e Pianos, or Ukuleles. Use this field for requests "
                        "about an instrument type instead of putting it in query."
                    ),
                },
                "max_price_brl": {
                    "type": ["number", "null"],
                    "description": "Maximum current price in BRL, or null for no limit.",
                },
                "only_available": {
                    "type": "boolean",
                    "description": "Whether to exclude unavailable catalog items.",
                },
                "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                "offset": {
                    "type": "integer", "minimum": 0,
                    "description": "Start at 0; use next_offset for subsequent pages.",
                },
                "specification_key": {
                    "type": ["string", "null"],
                    "description": "Exact specification key, e.g. electronics or strings; null for no filter.",
                },
                "specification_value": {
                    "type": ["string", "null"],
                    "description": "Exact value (case/accent insensitive), e.g. yes or nylon; supply with key, or both null.",
                },
            },
            "required": ["query", "category", "max_price_brl", "only_available", "limit", "offset", "specification_key", "specification_value"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "calculate_price",
        "description": (
            "Calculate an exact payable price, promotion/PIX rule, and credit-card "
            "installment eligibility and cent-accurate installment schedule for one product."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer"},
                "payment_method": {
                    "type": "string",
                    "enum": ["pix", "credit", "debit", "boleto"],
                },
                "installments": {
                    "type": ["integer", "null"],
                    "minimum": 1,
                    "maximum": 12,
                },
            },
            "required": ["product_id", "payment_method", "installments"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_order_status",
        "description": (
            "Look up an order after privacy verification. Require both the order ID "
            "and the exact e-mail registered with that order."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "integer"},
                "email": {"type": "string"},
            },
            "required": ["order_id", "email"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "search_policies",
        "description": (
            "Search reviewed store policy sections for hours, address, contact, "
            "payments, returns, exchanges, delivery, warranty, privacy, or scope."
        ),
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


GEMINI_FUNCTION_DECLARATIONS = [
    {
        "name": definition["name"],
        "description": definition["description"],
        "parameters_json_schema": definition["parameters"],
    }
    for definition in TOOL_DEFINITIONS
]


class ToolDispatcher:
    def __init__(self, repository: StoreRepository, policies: PolicyStore):
        self.repository = repository
        self.policies = policies
        self.handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "search_products": repository.search_products,
            "calculate_price": repository.calculate_price,
            "get_order_status": repository.get_order_status,
            "search_policies": policies.search,
        }

    def call(self, name: str, arguments: dict[str, Any]) -> str:
        handler = self.handlers.get(name)
        if handler is None:
            return json.dumps(
                {"status": "technical_error", "message": "Unknown tool."},
                ensure_ascii=False,
            )
        try:
            result = handler(**arguments)
        except TypeError:
            result = {
                "status": "technical_error",
                "message": "Tool arguments were invalid.",
            }
        except Exception:
            result = {
                "status": "technical_error",
                "message": "The data source could not be consulted.",
            }
        return json.dumps(result, ensure_ascii=False)
