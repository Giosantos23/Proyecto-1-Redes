from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .agent import ChatbotAgent, MCPToolRouter
from .audit_log import AuditLog
from .local_servers import LocalMCPBundle, PROJECT_ROOT


LOG_PATH = PROJECT_ROOT / "logs" / "mcp_interactions.jsonl"


def load_local_env() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Networks Project MCP chatbot")
    parser.add_argument(
        "--with-official",
        action="store_true",
        help="Start the official Filesystem and Git MCP servers too.",
    )
    parser.add_argument(
        "--demo-hr",
        action="store_true",
        help="Run a deterministic HR server demonstration without calling an LLM.",
    )
    parser.add_argument("--message", help="Ask one question and exit.")
    parser.add_argument("--model", help="Override GEMINI_MODEL for this run.")
    parser.add_argument("--debug", action="store_true", help="Enable diagnostic logs.")
    return parser.parse_args()


def print_hr_demo(client: object) -> None:
    calls = [
        ("consultar_directorio", {"query": "Ana"}),
        ("consultar_vacaciones", {"employee_id": "EMP-001", "year": 2026}),
        (
            "registrar_solicitud_permiso",
            {
                "employee_id": "EMP-001",
                "start_date": "2026-09-10",
                "end_date": "2026-09-12",
                "reason": "Personal matter",
            },
        ),
    ]
    print("\nHR MCP deterministic demonstration\n")
    for name, arguments in calls:
        result = client.call_tool(name, arguments)
        print(f"Tool: {name}")
        for content in result.get("content", []):
            if content.get("type") == "text":
                print(content["text"])
        print()


def run() -> int:
    load_local_env()
    args = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )
    audit = AuditLog(LOG_PATH)
    with LocalMCPBundle(include_official=args.with_official, audit_log=audit) as bundle:
        if args.demo_hr:
            print_hr_demo(bundle.clients[0])
            return 0
        router = MCPToolRouter(bundle.clients)
        agent = ChatbotAgent(router, model=args.model)
        if args.message:
            print(agent.ask(args.message))
            return 0
        print("Networks Project MCP chatbot. Type 'exit' or 'quit' to leave.")
        while True:
            try:
                user_text = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if user_text.lower() in {"exit", "quit"}:
                break
            if not user_text:
                continue
            try:
                answer = agent.ask(user_text)
            except Exception as exc:
                print(f"Error: {exc}", file=sys.stderr)
                continue
            print(f"Assistant: {answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
