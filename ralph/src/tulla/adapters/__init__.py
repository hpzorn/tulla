"""Adapters for external services.

Provides concrete implementations of ports for Claude, Codex, OpenCode, and ontology-server.

# @pattern:PortsAndAdapters -- Adapters implement abstract ports defined in tulla.ports
"""

from tulla.adapters.claude_cli import ClaudeCLIAdapter
from tulla.adapters.codex_cli import CodexCLIAdapter
from tulla.adapters.opencode_cli import OpenCodeCLIAdapter
from tulla.adapters.ontology_mcp import OntologyMCPAdapter

__all__ = [
    "ClaudeCLIAdapter",
    "CodexCLIAdapter",
    "OpenCodeCLIAdapter",
    "OntologyMCPAdapter",
]
