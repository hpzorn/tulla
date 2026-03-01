# /tulla — Ontology-Driven Idea Lifecycle Agent

Tulla is an autonomous agent that takes a raw idea and drives it through a structured pipeline — discovery, research, planning, and implementation — producing code at the end. Each phase is backed by an ontology and validated with SHACL, so the agent can't skip steps or produce incomplete work.

## CLI Usage

```bash
tulla run <agent> --idea <N> [options]
tulla status --idea <N>
tulla reset <N> [--agent <scope>] [-y]
tulla project-init [--project-id <id>] [--claude-md <path>]
tulla promote-adr [<adr-id>] [--project-id <id>]
```

### Agents

| Agent | Purpose |
|-------|---------|
| `discovery` | Discover upstream/downstream context for an idea (D1-D5 phases) |
| `research` | Deep research on an idea's domain (R1-R6 phases) |
| `planning` | Generate PRD with requirements from discovery+research artifacts (P1-P6) |
| `implementation` | Loop-based: Find requirement, implement, commit, verify, repeat |
| `epistemology` | Reflective analysis: pool, idea, domain, problem, contradiction, signal |
| `lightweight` | Single-pass workflow for incremental changes (bugfix, small features, chores) with architecture conformance and KG tracing |

### Common Options

- `--idea <N>` (required) — Idea ID to process
- `--mode <mode>` — Agent-specific mode (e.g. `upstream`/`downstream` for discovery; `pool`/`idea`/`domain` etc. for epistemology)
- `--dry-run` — Show execution plan without running
- `--work-dir <path>` — Override work directory
- `--from <phase>` — Resume from a specific phase (e.g. `d3`)
- `--directive <text>` — High-priority instruction injected into every phase prompt
- `--description <text>` — Short description of the change (lightweight agent only)
- `--discovery-dir <path>` — Path to discovery artifacts (for planning/research)
- `--research-dir <path>` — Path to research artifacts (for planning)
- `--research-mode <mode>` — Research pipeline mode: `groundwork`, `spike`, or `discovery-fed` (auto-detected if omitted)
- `-v` / `--verbose` — DEBUG-level console logging

### Status Command

```bash
tulla status --idea <N>
```

Shows PRD requirement completion status. Exit code 0 = all done, 2 = work remains.

### Reset Command

```bash
tulla reset <N> [--agent discovery|research|planning|all] [-y]
```

Clears A-Box phase facts for an idea so re-runs start clean.

### Project Commands

```bash
tulla project-init [--project-id <id>] [--claude-md ./CLAUDE.md]
tulla promote-adr [adr-58-1] [--project-id <id>]
```

`project-init` bootstraps a project from a CLAUDE.md file, extracting ADRs into the ontology. `promote-adr` promotes an idea-scope ADR to project scope.

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success / all complete |
| 1 | Failure (phase error, bad input) |
| 2 | Incomplete (work remains) |
| 124 | Timeout |

## Prerequisites

- **ontology-server** must be running at `http://localhost:8100` (or set `TULLA_ONTOLOGY_SERVER_URL`)
- Idea must exist in the idea pool (use ontology-server MCP tools to create/query ideas)
- For planning: discovery and optionally research artifacts must exist
- For implementation: a PRD must exist (stored as ontology facts with context `prd-idea-<N>`)

## Configuration

Environment variables use the `TULLA_` prefix:

- `TULLA_WORK_BASE_DIR` — Base directory for work artifacts (default: `./work`)
- `TULLA_IDEAS_DIR` — Directory for idea files (default: `~/.claude/ideas`)
- `TULLA_ONTOLOGY_SERVER_URL` — Ontology server URL (default: `http://localhost:8100`)

Alternatively, pass `--config path/to/config.yaml` to the top-level `tulla` command. See [`config.example.yaml`](config.example.yaml) for a full annotated example.

## When to Use

- Starting work on a new idea: `tulla run discovery --idea <N>`
- Deepening understanding: `tulla run research --idea <N> --discovery-dir <path>`
- Creating a PRD: `tulla run planning --idea <N> --discovery-dir <path> --research-dir <path>`
- Implementing requirements: `tulla run implementation --idea <N>`
- Quick incremental changes: `tulla run lightweight --idea <N> --description "fix typo in README"`
- Checking progress: `tulla status --idea <N>`
- Reflecting on the idea pool: `tulla run epistemology --idea <N> --mode pool`
