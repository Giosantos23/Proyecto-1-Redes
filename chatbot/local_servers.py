from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from .audit_log import AuditLog
from .mcp_client import MCPClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HR_SERVER_DIR = PROJECT_ROOT / "mcp_servers" / "hr_server"


class LocalMCPBundle:
    def __init__(self, *, include_official: bool = False, audit_log: AuditLog | None = None) -> None:
        self.include_official = include_official
        self.audit_log = audit_log
        self.clients: list[MCPClient] = []

    def __enter__(self) -> "LocalMCPBundle":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        self.close()

    def start(self) -> None:
        if self.clients:
            return
        self.clients.append(
            MCPClient(
                [sys.executable, "server.py"],
                cwd=HR_SERVER_DIR,
                environment=os.environ.copy(),
                server_name="hr-local-server",
                log_event=self._log,
            )
        )
        try:
            for client in self.clients:
                client.start()
            if self.include_official:
                self._start_official_servers()
        except Exception:
            self.close()
            raise

    def _start_official_servers(self) -> None:
        filesystem_dir = Path(
            os.getenv("FILESYSTEM_ALLOWED_DIR", str(PROJECT_ROOT / "demo_workspace"))
        )
        if not filesystem_dir.is_absolute():
            filesystem_dir = PROJECT_ROOT / filesystem_dir
        filesystem_dir.mkdir(parents=True, exist_ok=True)
        self.clients.append(
            MCPClient(
                ["npx", "-y", "@modelcontextprotocol/server-filesystem", str(filesystem_dir)],
                cwd=PROJECT_ROOT,
                environment=os.environ.copy(),
                server_name="official-filesystem-server",
                log_event=self._log,
            )
        )
        self.clients.append(
            MCPClient(
                ["uvx", "mcp-server-git"],
                cwd=PROJECT_ROOT,
                environment=os.environ.copy(),
                server_name="official-git-server",
                log_event=self._log,
            )
        )
        for client in self.clients[-2:]:
            client.start()

    def close(self) -> None:
        for client in reversed(self.clients):
            client.close()
        self.clients.clear()

    def _log(self, event: dict[str, Any]) -> None:
        if self.audit_log is not None:
            self.audit_log.write(event)
