"""CommitPhase — git commit subprocess, no Claude.

Part of the Implementation loop. This phase creates a git commit for
the files changed during implementation. It uses subprocess directly
and does NOT invoke Claude.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from .models import CommitOutput, FindOutput

logger = logging.getLogger(__name__)


class CommitPhase:
    """Create a git commit for implemented changes.

    Stages the files listed in the requirement and commits with a
    standardised message. Uses subprocess directly — no Claude invocation.
    """

    phase_id: str = "commit"

    def execute(
        self,
        requirement: FindOutput,
        project_root: Path,
    ) -> CommitOutput:
        """Commit the implemented changes.

        Parameters:
            requirement: The requirement that was implemented.
            project_root: Root directory of the git repository.

        Returns:
            A :class:`CommitOutput` with the commit result.
        """
        req_id = requirement.requirement_id or "unknown"
        message = f"impl({req_id}): {requirement.title}"

        try:
            # Stage relevant files
            root_name = project_root.name
            for file_path in requirement.files:
                resolved = project_root / file_path
                if not resolved.exists():
                    # LLM sometimes returns paths prefixed with the project
                    # dir name (e.g. "ralph/src/..." when project_root is
                    # already .../ralph), causing doubled paths. Strip it.
                    p = Path(file_path)
                    if p.parts and p.parts[0] == root_name:
                        resolved = project_root / Path(*p.parts[1:])
                if resolved.exists():
                    subprocess.run(
                        ["git", "add", str(resolved)],
                        cwd=str(project_root),
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                else:
                    logger.warning("File not found for staging: %s", resolved)

            # Check if there are staged changes
            status_result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=True,
            )

            if not status_result.stdout.strip():
                logger.info("No staged changes for %s, skipping commit", req_id)
                return CommitOutput(
                    requirement_id=req_id,
                    committed=False,
                    message="No staged changes",
                )

            # Commit
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=True,
            )

            # Extract commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                cwd=str(project_root),
                capture_output=True,
                text=True,
                check=True,
            )
            commit_hash = hash_result.stdout.strip()

            logger.info("Committed %s as %s", req_id, commit_hash)
            return CommitOutput(
                requirement_id=req_id,
                commit_hash=commit_hash,
                committed=True,
                message=message,
            )

        except subprocess.CalledProcessError as exc:
            logger.error("Git commit failed for %s: %s", req_id, exc.stderr)
            return CommitOutput(
                requirement_id=req_id,
                committed=False,
                message=f"Git error: {exc.stderr.strip()}",
            )
