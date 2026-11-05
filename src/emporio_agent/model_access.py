from __future__ import annotations

from typing import Any

from google.genai import types


class ModelAccessError(RuntimeError):
    """Raised when an account-specific model check cannot be confirmed."""


PROBE_TOOL = types.FunctionDeclaration(
    name="healthcheck",
    description="Return a fixed health-check result for model access validation.",
    parameters_json_schema={
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
)


def _short_model_name(name: str) -> str:
    return name.removeprefix("models/")


def validate_model_access(client: Any, model: str) -> dict[str, Any]:
    """Confirm that the configured account lists the model and can call a function."""
    catalog = client.models.list()
    model_ids = sorted(
        _short_model_name(item.name) for item in catalog if item.name
    )
    selected_model = _short_model_name(model)
    if selected_model not in model_ids:
        raise ModelAccessError(
            "The configured model is not listed for this API account/project."
        )

    response = client.models.generate_content(
        model=selected_model,
        contents="Call the healthcheck function exactly once.",
        config=types.GenerateContentConfig(
            tools=[types.Tool(function_declarations=[PROBE_TOOL])],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY", allowed_function_names=["healthcheck"]
                )
            ),
        ),
    )
    function_calls = response.function_calls or []
    if not any(call.name == "healthcheck" for call in function_calls):
        raise ModelAccessError(
            "The model is listed, but a Gemini function call was not confirmed."
        )
    return {
        "model": selected_model,
        "listed_for_account": True,
        "function_call_confirmed": True,
    }

