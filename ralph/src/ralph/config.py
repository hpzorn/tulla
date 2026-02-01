"""Centralised configuration for Ralph.

Provides :class:`AgentConfig` for per-agent settings and
:class:`RalphConfig` as the root configuration object.  Values are
resolved with the following precedence (highest → lowest):

1. Explicit keyword overrides (CLI flags, ``from_yaml(..., **overrides)``)
2. Environment variables (``RALPH_`` prefix)
3. YAML configuration file
4. Built-in defaults
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


# ---------------------------------------------------------------------------
# Per-agent configuration
# ---------------------------------------------------------------------------


class AgentConfig(BaseSettings):
    """Configuration for a single Ralph agent/phase.

    Attributes:
        budget_usd: Maximum dollar spend for the agent.
        max_retries: How many times to retry on transient failure.
        permission_mode: Claude permission mode (``"auto"``, ``"acceptEdits"``, …).
        phase_timeout_minutes: Wall-clock timeout for the phase in minutes.
    """

    budget_usd: float = 5.0
    max_retries: int = 2
    permission_mode: str = "auto"
    phase_timeout_minutes: int = 15


# ---------------------------------------------------------------------------
# Root configuration
# ---------------------------------------------------------------------------


class RalphConfig(BaseSettings):
    """Root configuration for the Ralph system.

    Environment variables are read with the ``RALPH_`` prefix, e.g.
    ``RALPH_WORK_BASE_DIR`` maps to ``work_base_dir``.
    """

    model_config = SettingsConfigDict(
        env_prefix="RALPH_",
        env_nested_delimiter="__",
    )

    work_base_dir: Path = Field(
        default=Path("./work"),
        description="Base directory for work artifacts.",
    )
    ideas_dir: Path = Field(
        default=Path.home() / ".claude" / "ideas",
        description="Directory where idea files are stored.",
    )
    ontology_server_url: str = Field(
        default="http://localhost:3000",
        description="URL of the ontology-server MCP endpoint.",
    )

    # Per-agent configurations with tailored defaults
    discovery: AgentConfig = Field(default_factory=AgentConfig)
    planning: AgentConfig = Field(default_factory=AgentConfig)
    research: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            budget_usd=8.0,
            phase_timeout_minutes=30,
        ),
    )
    implementation: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            budget_usd=10.0,
            permission_mode="acceptEdits",
        ),
    )
    epistemology: AgentConfig = Field(default_factory=AgentConfig)

    # -----------------------------------------------------------------
    # YAML loading
    # -----------------------------------------------------------------

    @classmethod
    def from_yaml(
        cls,
        path: str | Path,
        **overrides: Any,
    ) -> RalphConfig:
        """Load configuration from a YAML file with optional overrides.

        Parameters:
            path: Path to the YAML configuration file.
            **overrides: Keyword arguments that take highest precedence,
                overriding both YAML values and environment variables.

        Returns:
            A fully resolved :class:`RalphConfig` instance.
        """
        yaml_path = Path(path)
        if yaml_path.exists():
            with open(yaml_path) as fh:
                yaml_data: dict[str, Any] = yaml.safe_load(fh) or {}
        else:
            yaml_data = {}

        # Merge: YAML provides the base, overrides win
        merged = {**yaml_data, **overrides}
        return cls(**merged)
