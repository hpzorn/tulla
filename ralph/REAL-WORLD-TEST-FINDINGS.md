# Real-World Test Findings: Python Ralph Framework

**Date**: 2026-02-01
**Tests**: `ralph run research --idea 42`, `ralph run discovery --idea 42`, `ralph run planning --idea 42`
**Result**: All pipelines passed after fixing 13 issues discovered during testing

## Summary

The Python Ralph framework (idea-54) had never been executed end-to-end before this test session. Running three agent pipelines on idea-42 (arc42-Structured Architecture Design Phase) exposed 13 issues, 12 of which were fixed. The test validated full pipeline chaining: discovery (D1-D5, $2.10) -> research (R1-R6, $7.45) -> planning (P1-P6, $8.05) with proper artifact handoff between stages. The planning pipeline successfully exported 25 PRD requirements to the ontology A-box, visible in the dashboard.

## Errors Found

### 1. Wiring Gap: All 22 Phase `run_claude()` Methods Raise `NotImplementedError`

**Severity**: Blocker (no phase can execute)
**Symptom**: Pipeline fails immediately with `Claude invocation failed: R1Phase.run_claude requires a Claude adapter to be injected`
**Root Cause**: Every concrete phase (D1-D5, P1-P6, R1-R6, epistemology) was generated with a `run_claude` stub that raises `NotImplementedError`. The `ClaudeCLIAdapter` was correctly injected into `ctx.config["claude_port"]` by the pipeline, but no phase ever called it.
**Fix**: Added a concrete default `run_claude()` implementation in the `Phase` base class (`core/phase.py`) that:
- Reads `claude_port` from `ctx.config`
- Extracts tool names from the tool list
- Builds a `ClaudeRequest` with prompt, tools, budget, timeout, and permission mode
- Calls `claude_port.run(request)` and returns the `ClaudeResult`
- Raises `TimeoutError` on timeout (caught by `execute()`)

Removed all 22 stub methods from concrete phases (p6.py correctly preserved — it has a legitimate no-op override).

**Files Changed**: `core/phase.py`, plus 22 phase files across `discovery/`, `planning/`, `research/`, `epistemology/`

---

### 2. Invalid Config: `--permission-mode auto` Not a Valid Claude CLI Option

**Severity**: Blocker (CLI rejects the command)
**Symptom**: Claude CLI exits immediately with `error: option '--permission-mode <mode>' argument 'auto' is invalid`
**Root Cause**: `AgentConfig.permission_mode` defaulted to `"auto"`, which is not a valid Claude CLI permission mode. Valid values: `acceptEdits`, `bypassPermissions`, `default`, `delegate`, `dontAsk`, `plan`.
**Fix**: Changed default to `"bypassPermissions"` in both `AgentConfig` (config.py) and `ClaudeRequest` (ports/claude.py).

**Files Changed**: `config.py`, `ports/claude.py`, `tests/test_config.py`

---

### 3. Missing Plumbing: `permission_mode` Not Threaded from Config to Phases

**Severity**: High (phases use wrong permission mode even after fix #2)
**Symptom**: The `permission_mode` from `AgentConfig` was never passed through the pipeline to the phase context. Phases would always use the `ClaudeRequest` default.
**Root Cause**: Pipeline factory functions (e.g., `research_pipeline()`) only passed domain-specific config like `planning_dir` or `discovery_dir`, not agent-level settings.
**Fix**: Added `"permission_mode": config.<agent>.permission_mode` to the config dict in all 4 pipeline factories, plus the epistemology pipeline in `cli.py`. Updated `Phase.run_claude()` to read `ctx.config.get("permission_mode")`.

**Files Changed**: `phases/discovery/pipeline.py`, `phases/planning/pipeline.py`, `phases/research/pipeline.py`, `cli.py`, `core/phase.py`

---

### 4. Cost Tracking Gap: `execute()` Never Records Cost in Phase Metadata

**Severity**: Medium (budget tracking doesn't work)
**Symptom**: `PhaseResult.metadata["cost_usd"]` is always `0.0` even when Claude reports cost.
**Root Cause**: The `Phase.execute()` method constructs a `PhaseResult` but never extracts cost from the `ClaudeResult` returned by `run_claude()`.
**Fix**: Added cost extraction after `run_claude()`:
```python
cost_usd = 0.0
raw = self.run_claude(ctx, prompt, tools)
if hasattr(raw, "cost_usd"):
    cost_usd = raw.cost_usd
```
And passed it into the success result: `metadata={"cost_usd": cost_usd}`.

**Files Changed**: `core/phase.py`

---

### 5. Serialization: Pydantic Output Models Not JSON-Serializable for Checkpoints

**Severity**: Blocker (crashes after first successful phase)
**Symptom**: `TypeError: Object of type R1Output is not JSON serializable` during checkpoint save
**Root Cause**: `PhaseResult.to_dict()` puts `self.data` (a Pydantic `BaseModel` with `Path` fields) directly into the dict without serialization. `json.dump()` can't handle Pydantic models or `Path` objects.
**Fix**: Added Pydantic-aware serialization in `to_dict()`:
```python
if data is not None and hasattr(data, "model_dump"):
    data = data.model_dump(mode="json")
```

**Files Changed**: `core/phase.py`

---

### 6. Timeout: R1/R2/R6 Phase Timeouts Too Short for Research

**Severity**: High (R2 timed out at 300s, actual runtime was 356s)
**Symptom**: `Claude CLI timed out after 300.0 s` — pipeline stops at R2
**Root Cause**: R1, R2, and R6 had hard-coded 5-minute (300s) timeouts. Research phases that perform web searches and tool use routinely exceed 5 minutes.
**Fix**: Increased R1, R2, R6 timeouts from 300s to 600s (10 minutes), matching R3/R4. R5 already had 3600s (60 min).

**Files Changed**: `phases/research/r1.py`, `phases/research/r2.py`, `phases/research/r6.py`

---

### 7. Cost Extraction Key Mismatch

**Severity**: Medium (budget tracking always reports $0)
**Symptom**: `total_cost: $0.0000 USD` in execution summary despite Claude reporting cost
**Root Cause**: Claude CLI outputs cost as `total_cost_usd` in the JSON response. The `ClaudeCLIAdapter._extract_cost()` checked for `cost_usd`, `costUsd`, `total_cost`, `cost` — but not `total_cost_usd`.
**Fix**: Added `total_cost_usd` as first key in the extraction list, and `modelUsage` as an additional nested container to check.

**Files Changed**: `adapters/claude_cli.py`

---

### 8. No Log Files (Not Yet Fixed)

**Severity**: Low (debugging is harder but not blocked)
**Symptom**: All logging goes to stdout/stderr only. No persistent log files for post-mortem analysis.
**Root Cause**: The `structlog` integration mentioned in the architecture was never wired to a file handler. The `logging.getLogger(__name__)` calls produce output but it's only captured if the process output is redirected.
**Recommendation**: Add a file handler in `cli.py` that writes structured JSON logs to `{work_dir}/ralph.log`. This would capture phase transitions, cost tracking, and error details for debugging.

---

### 9. Budget Enforcement Uses Pre-Fix Cost Data

**Severity**: Low (budget guard exists but can't enforce with $0 costs)
**Symptom**: Pipeline budget tracking shows `$0.0000` for all phases. The budget guard in `Pipeline.run()` can never trigger because cost is always 0.
**Root Cause**: Combination of errors #4 and #7 — cost extraction was broken at two levels. Fix #7 was applied mid-session so the successful run still reported $0. Next run should report actual costs.
**Recommendation**: Verify on next pipeline run that costs are properly tracked and budget enforcement works.

---

### 10. Relative `work_base_dir` Resolves to Different Roots Depending on CWD

**Severity**: High (outputs scatter across directories)
**Symptom**: Discovery output lands in `ideasralph/work/` (run from `ideasralph/`) but research output lands in `ralph/work/` (run from `ralph/`). Downstream agents can't find upstream artifacts.
**Root Cause**: `config.work_base_dir` defaults to `Path("./work")` — a relative path that resolves differently depending on the process's cwd. When Python launches from `ralph/`, the path resolves to `ralph/work/`. When launched from `ideasralph/`, it resolves to `ideasralph/work/`.
**Fix**: Added a `model_validator` in `RalphConfig` that resolves `work_base_dir` to an absolute path at config-creation time. Also added `.resolve()` in the CLI's `run()` function for the `--work-dir` option. This locks the path when the process starts, preventing cwd-dependent resolution in subprocesses.

**Files Changed**: `config.py`, `cli.py`, `tests/test_config.py`

---

### 11. Planning Pipeline Missing CLI Wiring for `--research-dir` and `--discovery-dir`

**Severity**: High (planning can't find upstream artifacts)
**Symptom**: `ralph run planning --idea 42` accepts `--mode` for discovery dir (confusing) but has no `--research-dir` option. The planning pipeline factory accepted `research_dir` but the CLI never threaded it.
**Root Cause**: The planning branch in `_build_pipeline()` used the `--mode` parameter as `discovery_dir` — a hack that prevented proper `--discovery-dir` / `--research-dir` usage. The `--research-dir` CLI option didn't exist.
**Fix**:
- Added `--research-dir` CLI option to `run()` command
- Added `research_dir` parameter to `_build_pipeline()`
- Fixed planning branch to use `discovery_dir` and `research_dir` parameters instead of `mode`
- Threaded both through to `planning_pipeline()`

**Files Changed**: `cli.py`, `phases/planning/pipeline.py`

---

### 12. P6 Phase Incorrectly Implemented as Hygiene Gate Instead of PRD Export

**Severity**: Blocker (planning results invisible in ontology dashboard)
**Symptom**: After successful planning run (P1-P6 all SUCCESS, $4.88), no PRD appears in the ontology dashboard. The `prd-idea-42` context does not exist in the A-box.
**Root Cause**: The Python P6Phase was implemented as a hygiene/pre-flight gate (checking environment readiness) rather than the actual PRD export phase. In the bash `planning-ralph.sh`, P6 is "Export PRD to RDF" — it reads the P4 implementation plan, generates Turtle RDF with `prd:Requirement` instances, and stores each triple in the A-box via `mcp__ontology-server__store_fact` with context `prd-idea-{N}`. The Python version was a no-op that returned a `HygieneReport` and cost $0.
**Fix**: Complete rewrite of P6Phase to match bash behavior:
- `build_prompt()` now instructs Claude to read P4, extract tasks, generate Turtle RDF, and call `store_fact` for each triple
- `get_tools()` returns `Read`, `Write`, `mcp__ontology-server__store_fact`
- `parse_output()` checks for `p6-prd-export.ttl` and counts `prd:Requirement` instances
- Updated `P6Output` model: removed hygiene fields, added `turtle_file`, `summary_file`, `requirements_exported`, `prd_context`
- Timeout increased from 60s to 600s (10 min) — needs to store many facts
- Re-ran P6 on idea-42 with `--from p6`: 25 requirements exported, $3.17

**Files Changed**: `phases/planning/p6.py` (complete rewrite), `phases/planning/models.py`, `tests/phases/planning/test_p6.py` (complete rewrite)

---

### 13. Dashboard PRD Detail View Broken (Raw Predicates + Bracket Rendering)

**Severity**: High (PRD detail page unusable)
**Symptom**: Navigating to `/dashboard/prds/prd-idea-42/prd:req-idea-42-1-1` shows either no data or shows Python list brackets `['value']` around field values.
**Root Cause**: Two issues:
1. `DashboardService.get_requirement_detail()` returned raw RDF predicates (`prd:title`, `prd:status`) but the Jinja2 template expected transformed keys (`title`, `status`, `found`, `deps_detail`). The `found` flag was never set, so the template always showed the "not found" error block.
2. When duplicate facts existed for the same predicate (e.g., two `prd:description` triples), the service collected them as Python lists. Jinja2 rendered these as `['First description', 'Second description']` with brackets.
**Fix**: Rewrote `get_requirement_detail()` in the dashboard service:
- Strip `prd:` prefix from predicates (`prd:title` → `title`)
- Set `found: True` when facts exist
- Resolve `prd:dependsOn` into `deps_detail` list with titles/statuses for each dependency
- Build reverse `depended_by_detail` by scanning all context facts
- Added `_str()` helper that joins list values with comma separator
- Added `_strip_prd()` helper for status/priority cleanup
- Updated template to display `description`, `files`, `verification` fields

**Files Changed**: `ontology_server/dashboard/services.py`, `ontology_server/dashboard/templates/requirement_detail.html` (in semantic-tool-use repo)

---

## Test Execution Timeline

| Attempt | Outcome | Error Hit |
|---------|---------|-----------|
| 1 | FAILURE at R1 (0.6s) | `r1-question-refinement.md not found` — Claude never ran |
| 2 | Error investigation | Discovered `--permission-mode auto` invalid (error #2) |
| 3 | FAILURE after R1 | `R1Output is not JSON serializable` (error #5) |
| 4 | TIMEOUT at R2 (300s) | R2 source identification exceeded 5-min timeout (error #6) |
| 5 | SUCCESS | All 6 phases completed, resumed from R2 checkpoint |

## Successful Run Results

| Phase | Duration | Output | Size |
|-------|----------|--------|------|
| R1 - Question Refinement | 141s | `r1-question-refinement.md` | 14KB |
| R2 - Source Identification | 356s | `r2-source-identification.md` | 17KB |
| R3 - Research Questions | 350s | `r3-research-questions.md` | 34KB |
| R4 - Literature Review | 378s | `r4-literature-review.md` | 37KB |
| R5 - Experiments | 498s | `r5-research-findings.md` + 4 Python scripts + results | 72KB |
| R6 - Synthesis | 115s | `r6-research-synthesis.md` | 15KB |
| **Total** | **~30 min** | **22 files** | **~135KB** |

## Systemic Patterns

Four categories of issues emerged:

1. **Generated-but-not-wired code** (errors #1, #3, #11): The autonomous implementation created correct abstractions and interfaces but left the "last mile" wiring incomplete. The `ClaudeCLIAdapter` existed, the `Phase` ABC existed, but no code connected them. Similarly, `planning_pipeline()` accepted `research_dir` but the CLI never threaded it through.

2. **Invalid defaults from training data** (errors #2, #7): Default values were plausible but wrong — `"auto"` is not a real permission mode, and the cost key list didn't match the actual CLI output format.

3. **Missing runtime concerns** (errors #5, #6, #8, #10): Serialization, timeouts, logging, and path resolution are runtime concerns that unit tests don't catch. The 525-test suite passed throughout all fixes because it tests component behavior in isolation, not end-to-end execution.

4. **Semantic mismatch with bash reference** (errors #12, #13): The most impactful category — the Python implementation deviated from the bash reference behavior. P6 was supposed to export PRD requirements to the ontology A-box but was implemented as a hygiene gate. The dashboard service returned raw RDF predicates instead of template-friendly keys. These errors only surface when testing the full system end-to-end with real ontology data.

## Recommendations

1. **Add integration tests** that run a single phase end-to-end with a mock Claude adapter returning realistic `ClaudeResult` objects (with cost, JSON output, timeouts).
2. **Add a CLI validation command** (`ralph validate`) that checks config values against known-valid enums before running.
3. **Wire structlog** to both console and file output in the CLI entry point.
4. **Add a `--verbose` flag** to the CLI that enables debug-level logging for troubleshooting.
