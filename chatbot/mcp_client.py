from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any, Sequence


LOGGER = logging.getLogger("mcp-client")


class MCPError(RuntimeError):
    """Sale cuando el servidor MCP devuelve un error de transporte o protocolo."""


class MCPClient:
    def __init__(
        self,
        command: Sequence[str],
        *,
        cwd: str | Path | None = None,
        environment: dict[str, str] | None = None,
        server_name: str = "mcp-server",
        log_event: Any | None = None,
    ) -> None:
        self.command = list(command)
        self.cwd = str(cwd) if cwd else None
        self.environment = environment
        self.server_name = server_name
        self.log_event = log_event
        self.process: subprocess.Popen[str] | None = None
        self._request_id = 0
        self.server_info: dict[str, Any] = {}
        self.protocol_version: str | None = None
        self.tools: list[dict[str, Any]] = []

    def __enter__(self) -> "MCPClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def start(self) -> None:
        if self.process is not None:
            return
        LOGGER.info("Empezando %s: %s", self.server_name, " ".join(self.command))
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=sys.stderr,
            text=True,
            bufsize=1,
        )
        initialization = self.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "networking-chatbot", "version": "0.1.0"},
            },
        )
        self.protocol_version = initialization.get("protocolVersion")
        self.server_info = initialization.get("serverInfo", {})
        self.notify("notifications/initialized")
        listing = self.request("tools/list", {})
        self.tools = listing.get("tools", [])
        LOGGER.info("%s exposes %d tool(s)", self.server_name, len(self.tools))

    def close(self) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=2)
        self.process = None

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }
        self._record("request", method, request)
        self._send(request)
        if self.process is None or self.process.stdout is None:
            raise MCPError(f"{self.server_name} no está corriendo")
        while True:
            line = self.process.stdout.readline()
            if not line:
                return_code = self.process.poll()
                raise MCPError(
                    f"{self.server_name} conexión cerrada (return code {return_code})"
                )
            try:
                message = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MCPError(f"JSON invalido de {self.server_name}: {line!r}") from exc
            if message.get("id") != self._request_id:
                LOGGER.warning("Ignorando respuesta de ID invalido: %s", message.get("id"))
                continue
            self._record("response", method, message)
            if "error" in message:
                raise MCPError(f"{self.server_name} error: {message['error']}")
            return message.get("result", {})

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def _send(self, message: dict[str, Any]) -> None:
        if self.process is None or self.process.stdin is None:
            raise MCPError(f"{self.server_name} no está corriendo")
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _record(self, direction: str, method: str, message: dict[str, Any]) -> None:
        if self.log_event is not None:
            self.log_event(
                {
                    "component": self.server_name,
                    "direction": direction,
                    "method": method,
                    "message": message,
                }
            )
