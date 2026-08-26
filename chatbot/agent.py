from __future__ import annotations

import logging
import os
from typing import Any

from .mcp_client import MCPClient, MCPError


LOGGER = logging.getLogger("chatbot-agent")
SYSTEM_PROMPT = """Eres un asistente interno de Recursos Humanos para una empresa ficticia.

Utiliza las herramientas disponibles cuando el usuario pregunte por registros del directorio,
saldos de vacaciones, solicitudes de permiso, archivos o repositorios Git. Nunca inventes
datos de Recursos Humanos. Utiliza únicamente los registros ficticios proporcionados por las
herramientas locales. Antes de realizar una operación que modifique información, resume
claramente lo que se creará y solicita confirmación si el usuario no pidió explícitamente
realizar la acción. La base de datos de demostración no contiene información real de empleados.

Responde siempre en el idioma utilizado por el usuario, salvo que este solicite otro idioma.
"""


class MCPToolRouter:
    def __init__(self, clients: list[MCPClient]) -> None:
        self.clients = clients
        self.tool_to_client: dict[str, MCPClient] = {}
        self.gemini_tools: list[dict[str, Any]] = []
        for client in clients:
            for tool in client.tools:
                name = tool["name"]
                if name in self.tool_to_client:
                    raise ValueError(f"Duplicate MCP tool name: {name}")
                self.tool_to_client[name] = client
                self.gemini_tools.append(
                    {
                        "name": name,
                        "description": tool.get("description", ""),
                        "parameters": self._clean_schema(
                            tool.get("inputSchema", {"type": "object", "properties": {}})
                        ),
                    }
                )

    @classmethod
    def _clean_schema(cls, schema: dict[str, Any]) -> dict[str, Any]:
        allowed = {
            "type",
            "description",
            "properties",
            "required",
            "items",
            "enum",
            "format",
            "nullable",
        }
        cleaned: dict[str, Any] = {}
        for key, value in schema.items():
            if key not in allowed:
                continue
            if key == "properties" and isinstance(value, dict):
                cleaned[key] = {
                    property_name: cls._clean_schema(property_schema)
                    for property_name, property_schema in value.items()
                    if isinstance(property_schema, dict)
                }
            elif key == "items" and isinstance(value, dict):
                cleaned[key] = cls._clean_schema(value)
            else:
                cleaned[key] = value
        return cleaned

    def call(self, name: str, arguments: dict[str, Any]) -> tuple[str, bool]:
        client = self.tool_to_client.get(name)
        if client is None:
            return f"Unknown tool: {name}", True
        try:
            result = client.call_tool(name, arguments)
        except MCPError as exc:
            return str(exc), True
        text_parts = []
        for item in result.get("content", []):
            if item.get("type") == "text":
                text_parts.append(item.get("text", ""))
        text = "\n".join(text_parts) or str(result)
        return text, bool(result.get("isError", False))


class ChatbotAgent:
    def __init__(self, router: MCPToolRouter, model: str | None = None) -> None:
        provider = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
        if provider != "gemini":
            raise RuntimeError(
                "Se utiliza solo Gemini."
            )
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key or api_key == "tu_clave_real":
            raise RuntimeError(
                "GEMINI_API_KEY no está configurada."
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "Instala paquetes requeridos."
            ) from exc
        self._types = types
        self.client = genai.Client(api_key=api_key)
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.router = router
        self.contents: list[Any] = []

    def ask(self, user_text: str) -> str:
        self.contents.append({"role": "user", "parts": [{"text": user_text}]})
        for _ in range(8):
            config = self._generation_config()
            response = self.client.models.generate_content(
                model=self.model,
                contents=self.contents,
                config=config,
            )
            candidate = self._first_candidate(response)
            if candidate is None:
                raise RuntimeError("Gemini returned no candidate response")
            parts = candidate.content.parts
            self.contents.append(candidate.content)
            function_calls = [
                part.function_call
                for part in parts
                if getattr(part, "function_call", None) is not None
            ]
            if not function_calls:
                return self._text_from_parts(parts)
            function_response_parts = []
            for function_call in function_calls:
                name = function_call.name
                arguments = dict(function_call.args or {})
                result_text, is_error = self.router.call(name, arguments)
                response_payload = {"error": result_text} if is_error else {"result": result_text}
                function_response_parts.append(
                    self._types.Part.from_function_response(
                        name=name,
                        response=response_payload,
                        id=getattr(function_call, "id", None),
                    )
                )
            self.contents.append(
                self._types.Content(role="user", parts=function_response_parts)
            )
        raise RuntimeError("Se excedieron los intentos de generación de contenido sin obtener una respuesta final del modelo.")

    def _generation_config(self) -> Any:
        function_declarations = self._types.Tool(
            function_declarations=self.router.gemini_tools
        )
        return self._types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[function_declarations],
        )

    @staticmethod
    def _first_candidate(response: Any) -> Any | None:
        candidates = getattr(response, "candidates", None) or []
        return candidates[0] if candidates else None

    @staticmethod
    def _parts_to_dicts(parts: Any) -> list[dict[str, Any]]:
        result = []
        for part in parts:
            if hasattr(part, "model_dump"):
                result.append(part.model_dump(exclude_none=True))
            elif isinstance(part, dict):
                result.append(part)
            else:
                result.append({"text": str(part)})
        return result

    @staticmethod
    def _text_from_parts(parts: Any) -> str:
        text_parts = [
            part.text
            for part in parts
            if getattr(part, "text", None)
        ]
        return "\n".join(text_parts).strip() or "(Gemini no retorna texto.)"
