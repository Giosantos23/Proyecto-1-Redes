from __future__ import annotations

import subprocess
from pathlib import Path

from chatbot.audit_log import AuditLog
from chatbot.local_servers import LocalMCPBundle, PROJECT_ROOT


DEMO_REPOSITORY = PROJECT_ROOT / "demo_workspace" / "mcp-git-demo"
README_CONTENT = """# MCP Git Demo

Este README fue creado a través del servidor MCP de sistema de archivos.
El archivo fue agregado y confirmado a través del servidor MCP de Git oficial.
"""


def tool_text(result: dict) -> str:
    return "\n".join(
        item.get("text", "") for item in result.get("content", []) if item.get("type") == "text"
    )


def main() -> None:
    DEMO_REPOSITORY.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main", str(DEMO_REPOSITORY)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(DEMO_REPOSITORY), "config", "user.name", "UVG MCP Demo"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(DEMO_REPOSITORY), "config", "user.email", "mcp-demo@example.test"],
        check=True,
    )

    audit = AuditLog(PROJECT_ROOT / "logs" / "mcp_interactions.jsonl")
    with LocalMCPBundle(include_official=True, audit_log=audit) as bundle:
        filesystem = next(client for client in bundle.clients if client.server_name == "official-filesystem-server")
        git = next(client for client in bundle.clients if client.server_name == "official-git-server")

        write_result = filesystem.call_tool(
            "write_file", {"path": str(DEMO_REPOSITORY / "README.md"), "content": README_CONTENT}
        )
        add_result = git.call_tool(
            "git_add", {"repo_path": str(DEMO_REPOSITORY), "files": ["README.md"]}
        )
        commit_result = git.call_tool(
            "git_commit", {"repo_path": str(DEMO_REPOSITORY), "message": "docs: agregar MCP Git README"}
        )
        status_result = git.call_tool("git_status", {"repo_path": str(DEMO_REPOSITORY)})
        log_result = git.call_tool(
            "git_log", {"repo_path": str(DEMO_REPOSITORY), "max_count": 5}
        )

    print("Demostración del sistema de archivos oficial + Git MCP")
    print("\nFilesystem / write_file:\n" + tool_text(write_result))
    print("\nGit / git_add:\n" + tool_text(add_result))
    print("\nGit / git_commit:\n" + tool_text(commit_result))
    print("\nGit / git_status:\n" + tool_text(status_result))
    print("\nGit / git_log:\n" + tool_text(log_result))
    print(f"\nRepositorio: {DEMO_REPOSITORY}")


if __name__ == "__main__":
    main()
