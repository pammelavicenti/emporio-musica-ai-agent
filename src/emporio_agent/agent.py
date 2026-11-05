from __future__ import annotations

import json
from typing import Any

from google.genai import types

from emporio_agent.prompt import SYSTEM_PROMPT
from emporio_agent.tools import GEMINI_FUNCTION_DECLARATIONS, ToolDispatcher


class AgentError(RuntimeError):
    """A safe, user-facing failure from the LLM orchestration layer."""


class SupportAgent:
    def __init__(
        self,
        client: Any,
        model: str,
        dispatcher: ToolDispatcher,
        max_tool_rounds: int = 6,
    ):
        self.client = client
        self.model = model
        self.dispatcher = dispatcher
        self.max_tool_rounds = max_tool_rounds
        self.history: list[types.Content] = []
        declarations = [
            types.FunctionDeclaration(**definition)
            for definition in GEMINI_FUNCTION_DECLARATIONS
        ]
        self.generation_config = types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[types.Tool(function_declarations=declarations)],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )

    def chat(self, user_message: str) -> str:
        if not user_message.strip():
            return "Pode me dizer como eu posso ajudar?"
        self.history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_message.strip())],
            )
        )

        for _ in range(self.max_tool_rounds):
            try:
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=self.history,
                    config=self.generation_config,
                )
            except Exception as exc:
                raise AgentError(
                    "Não consegui acessar o modelo agora. Confira sua conexão, chave "
                    "de API e configuração do modelo."
                ) from exc

            candidates = response.candidates or []
            model_content = candidates[0].content if candidates else None
            if model_content is None:
                raise AgentError("O modelo não retornou conteúdo utilizável.")
            self.history.append(model_content)

            function_calls = response.function_calls or []
            if not function_calls:
                text = (response.text or "").strip()
                if not text:
                    raise AgentError("O modelo não retornou uma resposta de texto.")
                return text

            function_response_parts = []
            for call in function_calls:
                name = call.name or "unknown_tool"
                try:
                    arguments = dict(call.args or {})
                    if not isinstance(arguments, dict):
                        raise ValueError("Tool arguments must be an object.")
                    result = json.loads(self.dispatcher.call(name, arguments))
                except (TypeError, ValueError, json.JSONDecodeError):
                    result = {
                        "status": "technical_error",
                        "message": "The model supplied invalid tool arguments.",
                    }
                function_response_parts.append(
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=getattr(call, "id", None),
                            name=name,
                            response=result,
                        )
                    )
                )
            self.history.append(
                types.Content(role="user", parts=function_response_parts)
            )

        raise AgentError("A consulta excedeu o limite seguro de etapas.")

