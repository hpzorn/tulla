"""Centralised configuration for Tulla.

Provides :class:`AgentConfig` for per-agent settings and
:class:`TullaConfig` as the root configuration object.  Values are
resolved with the following precedence (highest → lowest):

1. Explicit keyword overrides (CLI flags, ``from_yaml(..., **overrides)``)
2. Environment variables (``RALPH_`` prefix)
3. YAML configuration file
4. Built-in defaults
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


# ---------------------------------------------------------------------------
# Per-agent configuration
# ---------------------------------------------------------------------------


class AgentConfig(BaseSettings):
    """Configuration for a single Tulla agent/phase.

    Attributes:
        budget_usd: Maximum dollar spend for the agent.
        max_retries: How many times to retry on transient failure.
        permission_mode: Claude permission mode (``"auto"``, ``"acceptEdits"``, …).
        phase_timeout_minutes: Wall-clock timeout for the phase in minutes.
    """

    budget_usd: float = 5.0
    max_retries: int = 2
    permission_mode: str = "bypassPermissions"
    phase_timeout_minutes: int = 15

    # Granularity thresholds (research-validated defaults)
    max_files_per_requirement: int = 3
    min_wpf_blocking: float = 12.0
    min_wpf_advisory: float = 15.0
    max_granularity_retries: int = 1

    # Per-phase timeout overrides (phase_id -> seconds).
    # Empty by default; phases fall back to their class-level timeout_s.
    phase_timeouts: dict[str, float] = Field(default_factory=dict)

    # Ontology query limits
    ontology_query_limit: int = 500
    hydration_error_threshold: float = 0.10

    # Annotation thresholds (implementation phases)
    apf_min: int = 2
    apf_max: int = 5
    novel_word_threshold: int = 5
    verbose_word_limit: int = 50


# ---------------------------------------------------------------------------
# Root configuration
# ---------------------------------------------------------------------------


class TullaConfig(BaseSettings):
    """Root configuration for the Tulla system.

    Environment variables are read with the ``RALPH_`` prefix, e.g.
    ``RALPH_WORK_BASE_DIR`` maps to ``work_base_dir``.
    """

    model_config = SettingsConfigDict(
        env_prefix="TULLA_",
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
        default="http://localhost:8100",
        description="URL of the ontology-server HTTP endpoint.",
    )

    @model_validator(mode="after")
    def _resolve_paths(self) -> TullaConfig:
        """Resolve relative paths to absolute at creation time.

        Prevents cwd-dependent path resolution when the Claude CLI
        subprocess has a different working directory than the Python
        process that created the config.
        """
        if not self.work_base_dir.is_absolute():
            object.__setattr__(
                self, "work_base_dir", self.work_base_dir.resolve()
            )
        return self

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
            budget_usd=30.0,
            permission_mode="acceptEdits",
        ),
    )
    lightweight: AgentConfig = Field(
        default_factory=lambda: AgentConfig(
            budget_usd=1.0,
            phase_timeout_minutes=3,
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
    ) -> TullaConfig:
        """Load configuration from a YAML file with optional overrides.

        Parameters:
            path: Path to the YAML configuration file.
            **overrides: Keyword arguments that take highest precedence,
                overriding both YAML values and environment variables.

        Returns:
            A fully resolved :class:`TullaConfig` instance.
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
