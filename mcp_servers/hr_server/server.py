from __future__ import annotations

import json
import logging
import sys
from datetime import date
from typing import Any, Callable

from database import HRDatabase


PROTOCOL_VERSION = "2025-11-25"
SERVER_NAME = "hr-local-server"
SERVER_VERSION = "0.1.0"

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
LOGGER = logging.getLogger(SERVER_NAME)


class RPCError(Exception):

    def __init__(self, code: int, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def text_result(value: Any, is_error: bool = False) -> dict[str, Any]:
    serialized = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, indent=2)
    return {
        "content": [{"type": "text", "text": serialized}],
        "isError": is_error,
    }


def tool_error(message: str) -> dict[str, Any]:
    return text_result({"error": message}, is_error=True)


def require_string(arguments: dict[str, Any], name: str, max_length: int = 200) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or not value.strip():
        raise RPCError(-32602, f"Parameter '{name}' must be a non-empty string")
    value = value.strip()
    if len(value) > max_length:
        raise RPCError(-32602, f"Parameter '{name}' exceeds the maximum length")
    return value


def require_year(arguments: dict[str, Any]) -> int:
    value = arguments.get("year")
    if isinstance(value, bool) or not isinstance(value, int) or not 2000 <= value <= 2100:
        raise RPCError(-32602, "Parameter 'year' must be an integer between 2000 and 2100")
    return value


def parse_iso_date(arguments: dict[str, Any], name: str) -> str:
    value = require_string(arguments, name, max_length=10)
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise RPCError(-32602, f"Parameter '{name}' must use YYYY-MM-DD format") from exc
    return value


TOOLS: list[dict[str, Any]] = [
    {
        "name": "consultar_directorio",
        "description": "Buscar el directorio de empleados ficticios por nombre, departamento o título de trabajo.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search text."}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "consultar_vacaciones",
        "description": "Retornar los días de vacaciones autorizados, utilizados y disponibles para un empleado y año.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Employee identifier, e.g. EMP-001."},
                "year": {"type": "integer", "description": "Calendar year."},
            },
            "required": ["employee_id", "year"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False},
    },
    {
        "name": "registrar_solicitud_permiso",
        "description": "Registrar una solicitud de permiso pendiente para un empleado después de validar las fechas e identidad.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "employee_id": {"type": "string", "description": "Identificador del empleado, e.g. EMP-001."},
                "start_date": {"type": "string", "description": "Primer día en formato YYYY-MM-DD."},
                "end_date": {"type": "string", "description": "Último día en formato YYYY-MM-DD."},
                "reason": {"type": "string", "description": "Breve razón para la solicitud."},
            },
            "required": ["employee_id", "start_date", "end_date", "reason"],
            "additionalProperties": False,
        },
        "annotations": {"readOnlyHint": False, "destructiveHint": False, "openWorldHint": False},
    },
]


def build_handlers(database: HRDatabase) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    def directory(arguments: dict[str, Any]) -> dict[str, Any]:
        query = require_string(arguments, "query", max_length=100)
        if len(query) < 2:
            raise RPCError(-32602, "'query' debe contener al menos 2 caracteres para evitar búsquedas demasiado amplias")
        matches = database.search_directory(query)
        return text_result({"count": len(matches), "employees": matches})

    def vacations(arguments: dict[str, Any]) -> dict[str, Any]:
        employee_id = require_string(arguments, "employee_id", max_length=30)
        year = require_year(arguments)
        balance = database.vacation_balance(employee_id, year)
        if balance is None:
            raise RPCError(-32602, "No balance de vacaciones encontrado para el empleado y año especificados")
        return text_result(balance)

    def leave_request(arguments: dict[str, Any]) -> dict[str, Any]:
        employee_id = require_string(arguments, "employee_id", max_length=30)
        start_date = parse_iso_date(arguments, "start_date")
        end_date = parse_iso_date(arguments, "end_date")
        if end_date < start_date:
            raise RPCError(-32602, "'end_date' no puede ser anterior a 'start_date'")
        reason = require_string(arguments, "reason", max_length=300)
        if database.find_employee(employee_id) is None:
            raise RPCError(-32602, "El empleado no existe en la base de datos ficticia de RR.HH.")
        request = database.create_leave_request(employee_id, start_date, end_date, reason)
        return text_result({"message": "Solicitud de permiso registrada", "request": request})

    return {
        "consultar_directorio": directory,
        "consultar_vacaciones": vacations,
        "registrar_solicitud_permiso": leave_request,
    }


def response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def error_response(request_id: Any, error: RPCError) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": error.code, "message": error.message}
    if error.data is not None:
        payload["data"] = error.data
    return {"jsonrpc": "2.0", "id": request_id, "error": payload}


def dispatch(request: dict[str, Any], database: HRDatabase) -> dict[str, Any] | None:
    request_id = request.get("id")
    method = request.get("method")
    if request.get("jsonrpc") != "2.0" or not isinstance(method, str):
        if "id" in request:
            return error_response(request_id, RPCError(-32600, "Invalid Request"))
        return None

    if method == "notifications/initialized" or method.startswith("notifications/"):
        return None
    if method == "initialize":
        requested = request.get("params", {}).get("protocolVersion", PROTOCOL_VERSION)
        negotiated = requested if requested in {PROTOCOL_VERSION, "2024-11-05"} else PROTOCOL_VERSION
        return response(
            request_id,
            {
                "protocolVersion": negotiated,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": "Usa las herramientas de RR.HH. solo con registros ficticios de empleados.",
            },
        )
    if method == "tools/list":
        return response(request_id, {"tools": TOOLS})
    if method == "tools/call":
        params = request.get("params") or {}
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in HANDLERS:
            raise RPCError(-32602, f"Unknown tool: {name}")
        if not isinstance(arguments, dict):
            raise RPCError(-32602, "Tool arguments must be an object")
        try:
            return response(request_id, HANDLERS[name](arguments))
        except RPCError as exc:
            return response(request_id, tool_error(exc.message))
    if "id" in request:
        return error_response(request_id, RPCError(-32601, f"Method not found: {method}"))
    return None


DATABASE = HRDatabase()
DATABASE.initialize()
HANDLERS = build_handlers(DATABASE)


def main() -> None:
    LOGGER.info("Started %s", SERVER_NAME)
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise RPCError(-32600, "Invalid Request")
            result = dispatch(request, DATABASE)
        except json.JSONDecodeError:
            result = error_response(None, RPCError(-32700, "Parse error"))
        except RPCError as exc:
            result = error_response(None, exc)
        except Exception as exc:
            LOGGER.exception("Unhandled server error")
            result = error_response(None, RPCError(-32603, "Internal error"))
        if result is not None:
            sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
