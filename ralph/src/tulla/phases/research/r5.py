"""R5 Phase - Experiments & Prototyping.

Implements the fifth research sub-phase that runs experiments and builds
prototypes to answer questions that literature review could not resolve.

R5 has special characteristics:
- Extended timeout (120 minutes)
- ``acceptEdits`` permission mode
- Retry loop on experiment failure (maps to ``max_retries`` parameter)
"""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from tulla.core.phase import ParseError, Phase, PhaseContext
from tulla.core.phase_facts import group_upstream_facts
from tulla.phases.research import RESEARCH_IDENTITY, build_northstar_section

from .models import R5Output


class R5Phase(Phase[R5Output]):
    """R5: Experiments & Prototyping phase.

    Constructs a prompt that asks Claude to run experiments and build
    prototypes for unresolved research questions.  Writes results to
    ``r5-research-findings.md`` inside the work directory.

    This phase has an extended timeout (120 min) and uses
    ``acceptEdits`` permission mode to allow code modifications.
    The ``max_retries`` parameter controls how many times a failed
    experiment is retried before giving up.
    """

    phase_id: str = "r5"
    timeout_s: float = 7200.0  # 120 minutes (extended)

    def __init__(self, max_retries: int = 2) -> None:
        self._max_retries = max_retries

    @property
    def max_retries(self) -> int:
        """Maximum retries for failed experiments."""
        return self._max_retries

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the R5 experiments & prototyping prompt."""
        output_file = ctx.work_dir / "r5-research-findings.md"
        r3_file = ctx.work_dir / "r3-research-questions.md"
        r4_file = ctx.work_dir / "r4-literature-review.md"
        research_date = date.today().isoformat()

        raw_facts = ctx.config.get("upstream_facts", [])
        grouped = group_upstream_facts(raw_facts)
        northstar_section = build_northstar_section(grouped)
        upstream_section = ""
        if grouped:
            upstream_section = (
                "## Upstream Facts\n"
                f"{json.dumps(grouped, indent=2)}\n"
                "\n"
            )

        return (
            RESEARCH_IDENTITY
            + f"## Phase R5: Experiments & Prototyping\n"
            f"**Idea**: {ctx.idea_id}\n"
            "\n"
            f"{northstar_section}"
            f"{upstream_section}"
            "## Goal\n"
            "Run experiments and build prototypes to answer research questions\n"
            "that could not be fully resolved by literature review.\n"
            "\n"
            "## Context\n"
            f"- Research questions: {r3_file}\n"
            f"- Literature review: {r4_file}\n"
            f"- Max retries per experiment: {self._max_retries}\n"
            "\n"
            "## Instructions\n"
            "\n"
            "1. Read the literature review for open items that need experimentation.\n"
            "2. Read the research questions for acceptance criteria.\n"
            "\n"
            "3. For each open item, design and run an experiment:\n"
            "   - Write prototype code in the work directory\n"
            "   - Execute the prototype and capture results\n"
            "   - If an experiment fails, retry up to "
            f"{self._max_retries} times with adjustments\n"
            "   - Document what worked and what didn't\n"
            "\n"
            f"4. Write the findings to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            "   # R5: Research Findings\n"
            f"   **Idea**: {ctx.idea_id}\n"
            f"   **Date**: {research_date}\n"
            f"   **Permission Mode**: acceptEdits\n"
            "\n"
            "   ## Experiments\n"
            "\n"
            "   ### Experiment 1: [Title]\n"
            "   **RQ**: [Which research question this addresses]\n"
            "   **Hypothesis**: [What we expected]\n"
            "   **Setup**: [What was built/configured]\n"
            "   **Result**: PASS / FAIL\n"
            "   **Retries**: [N of " + str(self._max_retries) + "]\n"
            "   **Finding**: [What we learned]\n"
            "   **Artefacts**: [Files created in work dir]\n"
            "\n"
            "   ### Experiment 2: ...\n"
            "\n"
            "   ## Summary\n"
            "   | Experiment | RQ | Result | Retries |\n"
            "   |------------|-----|--------|--------|\n"
            "   | Exp 1 | RQ1 | PASS | 0 |\n"
            "\n"
            "   ## Implications for Implementation\n"
            "   [How these findings affect the implementation plan]\n"
            "\n"
            "Be rigorous. Document failures as thoroughly as successes."
        )

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during R5.

        R5 has an expanded toolset including Edit for code modifications.
        """
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "Edit"},
            {"name": "Glob"},
            {"name": "Grep"},
            {"name": "Bash"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> R5Output:
        """Parse R5 output by reading ``r5-research-findings.md`` from *work_dir*.

        Extracts experiment counts, results, and implementation implications.
        Raises :class:`ParseError` if the output file is missing.
        """
        from tulla.core.markdown_extract import extract_field, extract_section, trim_text

        output_file = ctx.work_dir / "r5-research-findings.md"

        if not output_file.exists():
            raise ParseError(
                f"r5-research-findings.md not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = output_file.read_text(encoding="utf-8")

        # Split on ### Experiment N: headings.
        exp_parts = re.split(r"(?=###\s+Experiment\s+\d+:)", content)
        exp_results = []
        experiments_run = 0
        experiments_passed = 0

        for part in exp_parts:
            m = re.match(r"###\s+Experiment\s+\d+:\s*([^\n]+)\n(.*)", part, re.DOTALL)
            if not m:
                continue
            experiments_run += 1
            title = m.group(1).strip()
            body = m.group(2).strip()
            result = extract_field(body, "Result")
            if result.upper() == "PASS":
                experiments_passed += 1
            exp_results.append({
                "title": title,
                "rq": extract_field(body, "RQ"),
                "result": result,
                "finding": extract_field(body, "Finding"),
            })

        impl_section = extract_section(content, "Implications for Implementation")
        impl_implications = trim_text(impl_section) if impl_section else ""

        return R5Output(
            output_file=output_file,
            experiments_run=experiments_run,
            experiments_passed=experiments_passed,
            experiment_results=json.dumps(exp_results),
            impl_implications=impl_implications,
        )

    def get_timeout_seconds(self) -> float:
        """Return the R5 timeout in seconds (120 minutes, extended)."""
        return self.timeout_s
