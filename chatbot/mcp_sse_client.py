
from __future__ import annotations

import json
import logging
import threading
import queue
import time
from typing import Any

import requests
import sseclient

from .mcp_client import MCPError

LOGGER = logging.getLogger("mcp-sse-client")


class MCPSSEClient:
    def __init__(
        self,
        url: str,
        *,
        server_name: str = "remote-mcp-server",
        log_event: Any | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.server_name = server_name
        self.log_event = log_event
        self._request_id = 0
        self.server_info: dict[str, Any] = {}
        self.protocol_version: str | None = None
        self.tools: list[dict[str, Any]] = []
        
        self._endpoint: str | None = None
        self._response_queues: dict[int, queue.Queue] = {}
        self._sse_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def __enter__(self) -> "MCPSSEClient":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def start(self) -> None:
        LOGGER.info("Conectado a server remoto: %s", self.url)
        
        self._sse_thread = threading.Thread(target=self._listen, daemon=True)
        self._sse_thread.start()
        
        timeout = 10
        start_time = time.time()
        while self._endpoint is None and time.time() - start_time < timeout:
            time.sleep(0.1)
            
        if self._endpoint is None:
            raise MCPError(f"Fallo al recibir endpoint SSE de {self.url}")
            
        initialization = self.request(
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "chatbot", "version": "0.1.0"},
            },
        )
        self.protocol_version = initialization.get("protocolVersion")
        self.server_info = initialization.get("serverInfo", {})
        self.notify("notifications/initialized")
        
        listing = self.request("tools/list", {})
        self.tools = listing.get("tools", [])
        LOGGER.info("%s expone %d tool", self.server_name, len(self.tools))

    def _listen(self) -> None:
        try:
            response = requests.get(f"{self.url}/sse", stream=True, timeout=30)
            client = sseclient.SSEClient(response)
            for event in client.events():
                if self._stop_event.is_set():
                    break
                    
                if event.event == "endpoint":
                    self._endpoint = event.data
                    LOGGER.info("SSE endpoint recibido: %s", self._endpoint)
                elif event.data:
                    try:
                        message = json.loads(event.data)
                        msg_id = message.get("id")
                        if msg_id in self._response_queues:
                            self._response_queues[msg_id].put(message)
                        else:
                            LOGGER.debug("Se recibe mensaje no solicitado: %s", message)
                    except json.JSONDecodeError:
                        LOGGER.error("JSON inválido desde SSE: %s", event.data)
        except Exception as exc:
            if not self._stop_event.is_set():
                LOGGER.error("Error de conexión SSE: %s", exc)

    def close(self) -> None:
        self._stop_event.set()
        self._endpoint = None

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        req_id = self._request_id
        
        request_msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }
        
        q = queue.Queue()
        self._response_queues[req_id] = q
        
        try:
            self._record("request", method, request_msg)
            self._send(request_msg)
            
            try:
                message = q.get(timeout=15)
                self._record("response", method, message)
                
                if "error" in message:
                    raise MCPError(f"{self.server_name} error: {message['error']}")
                return message.get("result", {})
            except queue.Empty:
                raise MCPError(f"Timeout al esperar respuesta para {method} (id={req_id})")
        finally:
            del self._response_queues[req_id]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.request("tools/call", {"name": name, "arguments": arguments})

    def _send(self, message: dict[str, Any]) -> None:
        if self._endpoint is None:
            raise MCPError("No endpoint SSE disponible para enviar mensaje")
            
        url = f"{self.url}{self._endpoint}"
        resp = requests.post(url, json=message, timeout=10)
        if resp.status_code != 202:
            raise MCPError(f"Error HTTP {resp.status_code} enviando mensaje a {url}")

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
