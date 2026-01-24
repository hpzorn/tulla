# Research-First Ralph

Autonomous idea-to-implementation loop with mandatory research phase.

Extends Geoffrey Huntley's [Ralph Wiggum loop](https://ghuntley.com/ralph/) with:
- **Mandatory research phase** before implementation
- **Idea pool integration** for continuous multi-task processing
- **PRD-driven implementation**
- **Status tracking** and completion marking

## The Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                     RESEARCH-FIRST RALPH                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌─────────┐     ┌──────────┐     ┌─────┐     ┌────────────┐  │
│   │  IDEA   │────▶│ RESEARCH │────▶│ PRD │────▶│ IMPLEMENT  │  │
│   │  POOL   │     │  PHASE   │     │     │     │   (Ralph)  │  │
│   └─────────┘     └──────────┘     └─────┘     └────────────┘  │
│        ▲                                              │         │
│        │         ┌──────────────────┐                 │         │
│        └─────────│  UPDATE STATUS   │◀────────────────┘         │
│                  │ (done/tried/fail)│                           │
│                  └──────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Run the loop (processes ideas continuously)
./research-ralph.sh

# Process a single idea and exit
./research-ralph.sh --once --idea 13

# Dry run to see what would happen
./research-ralph.sh --dry-run --idea 5
```

## Requirements

- `claude` CLI (Claude Code) installed and authenticated
- `idea-pool` MCP server configured (for idea selection/status updates)
- Bash 4.0+

## Usage

```
./research-ralph.sh [--once] [--dry-run] [--idea IDEA_ID]

Options:
  --once      Run once and exit (don't loop continuously)
  --dry-run   Show what would be done without executing
  --idea ID   Process a specific idea by number or pattern
  --help      Show help message
```

## Phases

### 1. Extract (Idea Selection)

Queries the idea pool for the next workable idea based on:
- Lifecycle: `sprout` or `growing` (ready for implementation)
- Has a concrete problem statement
- Not blocked by dependencies
- Prioritized by novelty, complexity, and recency

### 2. Research (Mandatory)

**This phase cannot be skipped.** The agent must:
- Conduct literature review (papers, docs, blog posts)
- Document prior art (existing implementations)
- Identify theoretical foundations
- Catalog failure modes and pitfalls

Output: `research-notes.md`

Time-boxed to prevent research paralysis (default: 30 minutes).

### 3. PRD Creation

Based on the idea and research notes, creates a Product Requirements Document with:
- Problem Statement
- Research Summary
- Proposed Solution
- Success Criteria (checkboxes)
- Non-Goals
- Technical Approach
- Risks & Mitigations
- Estimated Complexity (S/M/L)

Output: `prd.md`

### 4. Implementation (Classic Ralph)

The core Ralph loop:
```bash
while :; do cat prd.md | claude ; done
```

Runs until the agent creates a `DONE` file indicating all PRD success criteria are met.

Limited to prevent infinite loops (default: 10 iterations).

### 5. Mark Complete

Updates the idea status in the pool:
- `implemented` - PRD fulfilled, code works
- `tried` - Attempted but blocked/deferred
- `failed` - Fundamental issue discovered

Creates a completion record with:
- Final status
- Work directory location
- Implementation summary
- Lessons learned

## Configuration

Edit `research-ralph.conf` to customize:

```bash
# Where your ideas live
IDEA_POOL_DIR="$HOME/ideas"

# Work directory for artifacts
WORK_DIR="./work"

# Research time limit (minutes)
RESEARCH_TIME_BOX_MINUTES=30

# Max implementation loop iterations
MAX_IMPLEMENTATION_LOOPS=10

# Sleep interval when no ideas (seconds)
SLEEP_INTERVAL=3600
```

## Directory Structure

After running, each idea gets a work directory:

```
work/
└── idea-13-20260124-143052/
    ├── idea-source.md      # Original idea content
    ├── research-notes.md   # Research phase output
    ├── prd.md              # Product requirements document
    ├── DONE                 # Completion marker
    ├── completion-record.md # Final status and summary
    └── [implementation files...]
```

## Key Differences from Original Ralph

| Aspect | Original Ralph | Research-First Ralph |
|--------|---------------|---------------------|
| Input | Single PROMPT.md | Idea pool (many ideas) |
| Research | None (jump to code) | Mandatory pre-phase |
| Documentation | Optional | PRD required |
| State tracking | File on disk | Idea pool lifecycle |
| Scope | One task | Continuous multi-task |

## References

- [ghuntley.com/ralph](https://ghuntley.com/ralph/) — Original technique
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — Claude Code CLI
- [snarktank/ralph](https://github.com/snarktank/ralph) — PRD-driven autonomous agent

## License

MIT
