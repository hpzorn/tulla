"""P6 Phase -- Export PRD to RDF.

Implements the sixth planning sub-phase that converts the implementation
plan (P4) into RDF triples and writes them as a Turtle file, then
programmatically hydrates the ontology A-box via ``store_fact``.
This creates the ``prd-idea-{N}`` context that the dashboard displays
under "Product Requirements" and that Implementation-Tulla reads to
find work items.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import click

from tulla.core.phase import ParseError, Phase, PhaseContext, PhaseResult, PhaseStatus

from .models import P6Output
from .p4 import _check_homogeneity

logger = logging.getLogger(__name__)

# PRD ontology namespaces (matches planning-tulla.sh)
PRD_NS = "http://impl-ralph.io/prd#"
TRACE_NS = "http://impl-ralph.io/trace#"

_PREFIXES = {
    "http://impl-ralph.io/prd#": "prd:",
    "http://impl-ralph.io/trace#": "trace:",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2001/XMLSchema#": "xsd:",
}


def _compact_uri(uri: str) -> str:
    """Compact a full URI into prefixed form using known namespaces.

    Returns the original string unchanged if no prefix matches.
    """
    for full, prefix in _PREFIXES.items():
        if uri.startswith(full):
            return prefix + uri[len(full):]
    return uri


class P6Phase(Phase[P6Output]):
    """P6: Export PRD to RDF.

    Reads the P4 implementation plan and asks Claude to:
    1. Generate a Turtle RDF file with ``prd:Requirement`` instances
    2. Write a summary file

    After Claude produces the Turtle file, Python parses it with rdflib
    and programmatically calls ``store_fact`` for each triple, avoiding
    the unreliable pattern of Claude making ~220 individual tool calls.

    This is the bridge between planning and implementation — without it,
    the ontology dashboard shows no PRD and Implementation-Tulla has
    no requirements to process.
    """

    phase_id: str = "p6"
    timeout_s: float = 600.0  # 10 minutes — Claude only generates Turtle

    # ------------------------------------------------------------------
    # A-box hydration
    # ------------------------------------------------------------------

    def _hydrate_abox(self, ctx: PhaseContext, turtle_file: Path) -> int:
        """Parse Turtle with rdflib and store each triple via the ontology port.

        Returns the number of triples successfully stored.
        Raises ``RuntimeError`` if more than 10% of triples fail.
        """
        from rdflib import Graph, Literal, URIRef

        ontology_port = ctx.config.get("ontology_port")
        if ontology_port is None:
            ctx.logger.warning("No ontology_port in config — skipping A-box hydration")
            return 0

        prd_context = f"prd-idea-{ctx.idea_id}"

        # Idempotent: clear any previous facts for this context
        cleared = ontology_port.forget_by_context(prd_context)
        if cleared:
            ctx.logger.info("Cleared %d existing facts from context %s", cleared, prd_context)

        g = Graph()
        g.parse(turtle_file, format="turtle")

        stored = 0
        errors = 0
        total = len(g)

        for s, p, o in g:
            subj = _compact_uri(str(s))
            pred = _compact_uri(str(p))
            if isinstance(o, Literal):
                obj = str(o)
            else:
                obj = _compact_uri(str(o))

            try:
                ontology_port.store_fact(subj, pred, obj, context=prd_context)
                stored += 1
            except Exception as exc:
                errors += 1
                ctx.logger.debug("store_fact failed for (%s, %s, %s): %s", subj, pred, obj, exc)

        ctx.logger.info(
            "A-box hydration: %d/%d triples stored (%d errors)",
            stored, total, errors,
        )

        if total > 0 and errors / total > 0.10:
            raise RuntimeError(
                f"A-box hydration error rate too high: {errors}/{total} triples failed"
            )

        return stored

    # ------------------------------------------------------------------
    # Execute override — retry on validation failure (arch:adr-64-1)
    # ------------------------------------------------------------------

    def execute(self, ctx: PhaseContext) -> PhaseResult[P6Output]:
        """Run P6 with retry on granularity validation failure.

        Wraps the base class :meth:`Phase.execute` in a retry loop.
        When ``validate_output`` raises ``ValueError`` (granularity gate),
        feedback about the coarse requirements is injected into the
        context and the phase is re-invoked.  Other errors (``ParseError``,
        ``TimeoutError``) are **not** retried.

        Max retries controlled by ``ctx.config["max_granularity_retries"]``
        (default ``1``).
        """
        max_retries = int(ctx.config.get("max_granularity_retries", 1))
        start = time.monotonic()
        log = ctx.logger

        for attempt in range(1 + max_retries):
            # --- Steps 1-3: input validation, build prompt, get tools ---
            try:
                self.validate_input(ctx)
            except Exception as exc:
                log.warning("Phase input validation failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Input validation failed: {exc}",
                    duration_s=time.monotonic() - start,
                )

            try:
                prompt = self.build_prompt(ctx)
            except Exception as exc:
                log.error("Phase build_prompt failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Prompt build failed: {exc}",
                    duration_s=time.monotonic() - start,
                )

            try:
                tools = self.get_tools(ctx)
            except Exception as exc:
                log.error("Phase get_tools failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Get tools failed: {exc}",
                    duration_s=time.monotonic() - start,
                )

            # --- Step 4: run Claude ---
            cost_usd = 0.0
            try:
                raw = self.run_claude(ctx, prompt, tools)
                if hasattr(raw, "cost_usd"):
                    cost_usd = raw.cost_usd
            except TimeoutError:
                log.warning("Phase timed out")
                return PhaseResult(
                    status=PhaseStatus.TIMEOUT,
                    error="Claude invocation timed out",
                    duration_s=time.monotonic() - start,
                )
            except Exception as exc:
                log.error("Phase run_claude failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Claude invocation failed: {exc}",
                    duration_s=time.monotonic() - start,
                )

            # --- Step 5: parse output ---
            try:
                parsed = self.parse_output(ctx, raw)
            except ParseError as exc:
                log.warning("Phase parse_output failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Output parsing failed: {exc}",
                    duration_s=time.monotonic() - start,
                    metadata={"parse_context": exc.context},
                )
            except Exception as exc:
                log.error("Unexpected parse error: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Output parsing failed: {exc}",
                    duration_s=time.monotonic() - start,
                )

            # --- Step 6: validate output ---
            # Build result envelope for feedback generation before validation
            pre_result = PhaseResult(
                status=PhaseStatus.SUCCESS,
                data=parsed,
                duration_s=time.monotonic() - start,
            )
            try:
                self.validate_output(ctx, parsed)
            except ValueError as exc:
                # Validation failure — retry if attempts remain
                if attempt < max_retries:
                    log.warning(
                        "P6 granularity validation failed (attempt %d/%d), retrying: %s",
                        attempt + 1,
                        1 + max_retries,
                        exc,
                    )
                    ctx.config["granularity_feedback"] = (
                        self._build_granularity_feedback(pre_result)
                    )
                    continue
                # Exhausted retries
                log.warning("Phase output validation failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Output validation failed: {exc}",
                    duration_s=time.monotonic() - start,
                )
            except Exception as exc:
                # Non-validation errors are never retried
                log.warning("Phase output validation failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"Output validation failed: {exc}",
                    duration_s=time.monotonic() - start,
                )

            # --- Step 7: Hydrate A-box from Turtle ---
            try:
                triple_count = self._hydrate_abox(ctx, parsed.turtle_file)
                parsed.triples_stored = triple_count
            except (RuntimeError, Exception) as exc:
                log.error("A-box hydration failed: %s", exc)
                return PhaseResult(
                    status=PhaseStatus.FAILURE,
                    error=f"A-box hydration failed: {exc}",
                    duration_s=time.monotonic() - start,
                )

            # --- Success ---
            elapsed = time.monotonic() - start
            log.info("Phase completed successfully in %.2fs", elapsed)
            return PhaseResult(
                status=PhaseStatus.SUCCESS,
                data=parsed,
                duration_s=elapsed,
                metadata={
                    "cost_usd": cost_usd,
                    "attempts": attempt + 1,
                    "triples_stored": triple_count,
                },
            )

        # Should not be reached, but satisfy type checker
        return PhaseResult(  # pragma: no cover
            status=PhaseStatus.FAILURE,
            error="Retry loop exhausted unexpectedly",
            duration_s=time.monotonic() - start,
        )

    # ------------------------------------------------------------------
    # Template hooks
    # ------------------------------------------------------------------

    def build_prompt(self, ctx: PhaseContext) -> str:
        """Build the P6 PRD export prompt, ported from planning-tulla.sh.

        If ``ctx.config`` contains ``"granularity_feedback"``, the feedback
        is appended as a ``## Granularity Feedback`` section so the LLM
        can address coarse requirements on retry.
        """
        p4_file = ctx.work_dir / "p4-implementation-plan.md"
        output_file = ctx.work_dir / "p6-prd-export.ttl"
        summary_file = ctx.work_dir / "p6-prd-summary.md"
        planning_date = date.today().isoformat()
        idea_id = ctx.idea_id

        prompt = (
            f"You are conducting Phase P6: Export PRD to RDF for idea {idea_id}.\n"
            "\n"
            "## Goal\n"
            "Convert the implementation plan into RDF requirements that "
            "Implementation-Tulla can consume.\n"
            "This creates the semantic graph of requirements with dependencies "
            "for the ontology-driven implementation loop.\n"
            "\n"
            "## Context\n"
            f"Read the implementation plan: {p4_file}\n"
            "\n"
            "## PRD Ontology Schema\n"
            "\n"
            "Use these namespaces:\n"
            "```turtle\n"
            f"@prefix prd: <{PRD_NS}> .\n"
            f"@prefix trace: <{TRACE_NS}> .\n"
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
            "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "```\n"
            "\n"
            "### Classes\n"
            "- `prd:Requirement` - A single implementable requirement/task\n"
            "- `prd:AcceptanceCriteria` - Success condition for verification\n"
            "\n"
            "### Properties\n"
            "- `prd:title` (string) - Short name for the requirement\n"
            "- `prd:description` (string) - Full requirement text\n"
            "- `prd:status` - One of: `prd:Pending`, `prd:InProgress`, `prd:Complete`\n"
            "- `prd:dependsOn` - Requirement → Requirement (dependency link)\n"
            "- `prd:priority` - One of: `prd:P0`, `prd:P1`, `prd:P2`\n"
            "- `prd:phase` (integer) - Implementation phase number\n"
            "- `prd:taskId` (string) - Original task ID from P4 (e.g., '1.1', '2.3')\n"
            "- `prd:files` (string) - Files to create/modify\n"
            "- `prd:action` (string) - Either 'create' (new file) or 'modify' (edit existing)\n"
            "- `prd:verification` (string) - How to verify completion\n"
            "- `prd:relatedADR` (string, multi-valued) - Links requirement to an architecture decision (e.g. \"arch:adr-{idea_id}-1\")\n"
            "- `prd:qualityFocus` (string) - Quality attribute this requirement primarily addresses (e.g. \"Testability\")\n"
            "- `prd:filesCount` (integer) - Number of files this requirement touches\n"
            "- `prd:descriptionWordCount` (integer) - Word count of the requirement description\n"
            "- `prd:wordsPerFile` (float) - Ratio of description words to files (descriptionWordCount / filesCount)\n"
            "\n"
            "## Instructions\n"
            "\n"
            f"1. Read the implementation plan from {p4_file}\n"
            "\n"
            "2. Extract each task from the 'Implementation Phases' section\n"
            "   - Each 'Task X.Y' becomes a `prd:Requirement` instance\n"
            "   - Use task dependencies to set `prd:dependsOn` relationships\n"
            "   - Phase 1 tasks are P0, Phase 2 are P1, Phase 3 are P2\n"
            "\n"
            f"3. Write Turtle RDF to: {output_file}\n"
            "\n"
            "   Structure:\n"
            "   ```turtle\n"
            f"   @prefix prd: <{PRD_NS}> .\n"
            "   @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n"
            "   @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n"
            "   @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n"
            "\n"
            "   # Requirement 1.1\n"
            f"   prd:req-{idea_id}-1-1 a prd:Requirement ;\n"
            '       prd:taskId "1.1" ;\n'
            '       prd:title "[Task title]" ;\n'
            '       prd:description """[Full task description]""" ;\n'
            "       prd:status prd:Pending ;\n"
            "       prd:priority prd:P0 ;\n"
            "       prd:phase 1 ;\n"
            '       prd:files "path/to/file.py" ;\n'
            '       prd:action "create" ;\n'
            '       prd:verification "[How to verify]" ;\n'
            f'       prd:relatedADR "arch:adr-{idea_id}-N" ;\n'
            '       prd:qualityFocus "[Quality attribute]" .\n'
            "   ```\n"
            "\n"
            "3.5. **Link requirements to architecture (MANDATORY)**\n"
            f'   - FIRST: call mcp__ontology-server__recall_facts with context="arch-idea-{idea_id}" '
            "to retrieve all ADRs, quality goals, and design principles\n"
            "   - For EVERY requirement, determine which ADR(s) it relates to and add "
            "prd:relatedADR to the Turtle output\n"
            "   - For EVERY requirement, identify the primary quality attribute it "
            "addresses (from the architecture quality goals) and add "
            "prd:qualityFocus to the Turtle output\n"
            "   - Every requirement MUST have at least one prd:relatedADR and one prd:qualityFocus.\n"
            "     If a requirement genuinely relates to no ADR, use the closest match — "
            "architecture decisions exist to guide implementation, so the mapping always exists.\n"
            "   - For EACH requirement, also include granularity metrics in the Turtle:\n"
            "     a. Count the files listed in `prd:files` → add as `prd:filesCount` (integer)\n"
            "     b. Count the words in `prd:description` → add as `prd:descriptionWordCount` (integer)\n"
            "     c. Compute wordsPerFile = descriptionWordCount / filesCount → add as `prd:wordsPerFile` (float, rounded to 2 decimals)\n"
            "\n"
            "   NOTE: Do NOT call store_fact — the A-box is hydrated automatically\n"
            "   after the Turtle file is validated.\n"
            "\n"
            f"5. Write a summary to: {summary_file}\n"
            "\n"
            "   Structure:\n"
            "\n"
            f"   # P6: RDF Export Summary\n"
            f"   **Idea**: {idea_id}\n"
            f"   **Date**: {planning_date}\n"
            "\n"
            "   ## Export Status: SUCCESS\n"
            "\n"
            "   ## Requirements Created\n"
            "\n"
            "   | Requirement ID | Title | Priority | Dependencies |\n"
            "   |----------------|-------|----------|-------------|\n"
            f"   | req-{idea_id}-1-1 | ... | P0 | None |\n"
            f"   | req-{idea_id}-1-2 | ... | P0 | 1.1 |\n"
            "   | ... | ... | ... | ... |\n"
            "\n"
            "   ## Dependency Graph\n"
            "\n"
            "   ```\n"
            "   [ASCII representation of dependency graph]\n"
            "   ```\n"
            "\n"
            "   ## Ontology Location\n"
            "\n"
            f"   - Turtle file: {output_file}\n"
            f'   - Graph context: prd-idea-{idea_id}\n'
            "\n"
            "   ## Next Step\n"
            "\n"
            f"   Run Implementation-Tulla: `tulla run implementation --idea {idea_id}`\n"
            "\n"
            "Be precise with RDF syntax. Each task from P4 becomes exactly one "
            "prd:Requirement."
        )

        # Append granularity feedback if present (set by execute() retry loop)
        feedback = ctx.config.get("granularity_feedback")
        if feedback:
            prompt += (
                "\n\n## Granularity Feedback (MUST address)\n"
                + feedback
            )

        return prompt

    def get_tools(self, ctx: PhaseContext) -> list[dict[str, Any]]:
        """Return tool definitions available during P6."""
        return [
            {"name": "Read"},
            {"name": "Write"},
            {"name": "mcp__ontology-server__recall_facts"},
        ]

    def parse_output(self, ctx: PhaseContext, raw: Any) -> P6Output:
        """Parse P6 output by checking for the Turtle and summary files.

        Counts requirements from the Turtle file (``prd:Requirement`` instances).
        Raises :class:`ParseError` if the Turtle file is missing.
        """
        turtle_file = ctx.work_dir / "p6-prd-export.ttl"
        summary_file = ctx.work_dir / "p6-prd-summary.md"
        idea_id = ctx.idea_id

        if not turtle_file.exists():
            raise ParseError(
                f"p6-prd-export.ttl not found in {ctx.work_dir}",
                raw_output=raw,
                context={"work_dir": str(ctx.work_dir)},
            )

        content = turtle_file.read_text(encoding="utf-8")

        # Count prd:Requirement instances
        req_count = len(re.findall(r"a\s+prd:Requirement", content))

        # Count architecture traceability links
        adr_links = len(re.findall(r"prd:relatedADR", content))
        quality_links = len(re.findall(r"prd:qualityFocus", content))

        if req_count > 0 and adr_links == 0:
            ctx.logger.warning(
                "P6 Turtle has %d requirements but zero prd:relatedADR links",
                req_count,
            )
        if req_count > 0 and quality_links == 0:
            ctx.logger.warning(
                "P6 Turtle has %d requirements but zero prd:qualityFocus links",
                req_count,
            )

        # -- Per-requirement granularity extraction --
        max_files = int(ctx.config.get("max_files_per_requirement", 3))
        min_wpf = float(ctx.config.get("min_wpf_blocking", 12.0))

        coarse_requirements: list[dict[str, Any]] = []
        for req_match in re.finditer(
            r"(prd:req-[\w-]+)\s+a\s+prd:Requirement\s*;(.*?)(?:\.\s*$|\.\s*\n)",
            content,
            re.DOTALL | re.MULTILINE,
        ):
            req_id = req_match.group(1)
            req_body = req_match.group(2)

            # Check for @cross-cutting annotation escape
            if "@cross-cutting" in req_body:
                continue

            files = _extract_turtle_files(req_body)
            description = _extract_turtle_description(req_body)

            file_count = len(files)
            word_count = len(description.split()) if description else 0
            wpf = word_count / file_count if file_count > 0 else 0.0
            homogeneous = _check_homogeneity(files)

            if file_count > max_files and not homogeneous and wpf < min_wpf:
                coarse_requirements.append({
                    "requirement": req_id,
                    "file_count": file_count,
                    "word_count": word_count,
                    "wpf": round(wpf, 2),
                    "homogeneous": homogeneous,
                })

        granularity_passed = len(coarse_requirements) == 0

        return P6Output(
            turtle_file=turtle_file,
            summary_file=summary_file,
            requirements_exported=req_count,
            prd_context=f"prd-idea-{idea_id}",
            adr_links=adr_links,
            quality_links=quality_links,
            coarse_requirements=coarse_requirements,
            granularity_passed=granularity_passed,
        )

    def validate_output(self, ctx: PhaseContext, parsed: P6Output) -> None:
        """Blocking gate: raise ValueError when granularity check fails.

        Per ADR-64-2 the P6 gate is **blocking** because P6 produces the
        final RDF artifact consumed by Implementation-Tulla.  When
        ``granularity_passed`` is ``False``, each coarse requirement is
        logged as a warning and echoed to stderr, then a ``ValueError``
        is raised which triggers the retry mechanism in ``execute()``.
        """
        if parsed.granularity_passed:
            return

        lines: list[str] = []
        for entry in parsed.coarse_requirements:
            msg = (
                f"P6 blocking: Requirement {entry['requirement']} is too coarse "
                f"(files={entry['file_count']}, wpf={entry['wpf']})"
            )
            ctx.logger.warning(msg)
            click.echo(msg, err=True)
            lines.append(
                f"  {entry['requirement']}: "
                f"files={entry['file_count']}, wpf={entry['wpf']}"
            )

        raise ValueError(
            "P6 granularity gate failed — coarse requirements:\n"
            + "\n".join(lines)
        )

    def _build_granularity_feedback(self, result: PhaseResult[P6Output]) -> str:
        """Build Template A feedback with specific metrics and split instructions.

        Uses the CRITIC framework (Concrete, Referenced, Instructive,
        Targeted, Iterative, Constructive) to provide actionable feedback
        for each coarse requirement, grouping files by directory to
        suggest split boundaries.

        Args:
            result: PhaseResult containing P6Output with coarse_requirements.

        Returns:
            Markdown-formatted feedback string.
        """
        if result.data is None or not result.data.coarse_requirements:
            return ""

        sections: list[str] = []

        for entry in result.data.coarse_requirements:
            req_id = entry["requirement"]
            file_count = entry["file_count"]
            wpf = entry["wpf"]
            word_count = entry["word_count"]

            # --- Concrete: show exact metrics ---
            metrics = (
                f"### {req_id}\n"
                f"- **Files**: {file_count} (max allowed: 3)\n"
                f"- **Words-per-file (wpf)**: {wpf} (min required: 12.0)\n"
                f"- **Total description words**: {word_count}\n"
            )

            # --- Referenced: group files by directory for split suggestions ---
            files = self._extract_files_for_requirement(req_id, result)
            dir_groups = _group_files_by_directory(files)

            split_plan = "- **Suggested splits by directory**:\n"
            split_idx = 1
            for directory, dir_files in sorted(dir_groups.items()):
                file_list = ", ".join(f"`{f}`" for f in dir_files)
                split_plan += (
                    f"  {split_idx}. **`{directory}/`** → new requirement "
                    f"covering: {file_list}\n"
                )
                split_idx += 1

            # --- Instructive + Targeted: CRITIC splitting instructions ---
            instructions = (
                "- **Action required**: Split this requirement so each sub-requirement:\n"
                "  1. Touches at most **3 files**\n"
                "  2. Has a description with at least **12 words per file**\n"
                "  3. Covers files from a **single directory** (cohesive change)\n"
                "  4. Has its own `prd:dependsOn` links where needed\n"
            )

            sections.append(f"{metrics}{split_plan}{instructions}")

        header = (
            "The following requirements are **too coarse** and must be split "
            "into smaller, more focused requirements.\n\n"
        )

        return header + "\n".join(sections)

    def _extract_files_for_requirement(
        self, req_id: str, result: PhaseResult[P6Output]
    ) -> list[str]:
        """Extract file paths for a specific requirement from the Turtle content.

        Reads the Turtle file referenced in the result data and extracts
        ``prd:files`` values for the given requirement ID.
        """
        if result.data is None:
            return []

        turtle_path = result.data.turtle_file
        if not turtle_path.exists():
            return []

        content = turtle_path.read_text(encoding="utf-8")

        # Find the specific requirement block
        pattern = (
            rf"{re.escape(req_id)}\s+a\s+prd:Requirement\s*;"
            r"(.*?)(?:\.\s*$|\.\s*\n)"
        )
        match = re.search(pattern, content, re.DOTALL | re.MULTILINE)
        if not match:
            return []

        return _extract_turtle_files(match.group(1))

    def get_timeout_seconds(self) -> float:
        """Return the P6 timeout in seconds (10 minutes)."""
        return self.timeout_s


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _extract_turtle_files(req_body: str) -> list[str]:
    """Extract file paths from ``prd:files`` values in a Turtle requirement block.

    Handles both single-value and comma-separated file lists within quotes.
    """
    files: list[str] = []
    for match in re.finditer(r'prd:files\s+"([^"]*)"', req_body):
        raw = match.group(1).strip()
        # Split on commas or whitespace for multi-file values
        parts = [p.strip() for p in re.split(r"[,\s]+", raw) if p.strip()]
        files.extend(parts)
    return files


def _group_files_by_directory(files: list[str]) -> dict[str, list[str]]:
    """Group file paths by their parent directory.

    Returns a dict mapping directory paths to lists of filenames within
    that directory.  Files without a directory component are grouped
    under ``"."``.
    """
    groups: dict[str, list[str]] = defaultdict(list)
    for f in files:
        directory = os.path.dirname(f) or "."
        groups[directory].append(os.path.basename(f))
    return dict(groups)


def _extract_turtle_description(req_body: str) -> str:
    """Extract the ``prd:description`` value from a Turtle requirement block.

    Supports both single-line ``"..."`` and multi-line ``\"\"\"...\"\"\"`` strings.
    """
    # Try triple-quoted first
    match = re.search(r'prd:description\s+"""(.*?)"""', req_body, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Fall back to single-quoted
    match = re.search(r'prd:description\s+"([^"]*)"', req_body)
    if match:
        return match.group(1).strip()
    return ""
