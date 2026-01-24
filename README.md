# Research-First Ralph

Autonomous idea-to-implementation loop with mandatory research phase.

Extends Geoffrey Huntley's [Ralph Wiggum loop](https://ghuntley.com/ralph/) with:
- **Mandatory research phase** before implementation
- **Idea pool integration** via MCP for continuous multi-task processing
- **Decomposition** of large ideas into sub-ideas
- **Dependency tracking** and blocking detection
- **PRD-driven implementation**
- **Lifecycle state tracking** with automatic transitions

## The Loop

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RESEARCH-FIRST RALPH                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│   ┌─────────┐    ┌───────────┐    ┌───────────┐    ┌─────┐          │
│   │ BACKLOG │───▶│ RESEARCH  │───▶│ DECOMPOSE │───▶│ PRD │          │
│   └─────────┘    └───────────┘    └───────────┘    └─────┘          │
│        ▲               │                │              │             │
│        │               ▼                ▼              ▼             │
│        │         ┌──────────┐    ┌──────────┐   ┌───────────┐       │
│        │         │INVALIDATE│    │ CHILDREN │   │ IMPLEMENT │       │
│        │         │  / PARK  │    │ → BACKLOG│   │  (Ralph)  │       │
│        │         └──────────┘    └──────────┘   └───────────┘       │
│        │                                              │              │
│        │         ┌──────────────────┐                 │              │
│        └─────────│    COMPLETED     │◀────────────────┘              │
│                  │ / BLOCKED / FAIL │                                │
│                  └──────────────────┘                                │
└─────────────────────────────────────────────────────────────────────┘
```

## Lifecycle States

```
backlog ──► researching ──► researched ──► scoped ──► implementing ──► completed
                │                │                          │
                ▼                ▼                          ▼
           invalidated     decomposing               blocked/failed
              parked      (→ children)
```

| State | Meaning |
|-------|---------|
| `backlog` | Queued for Ralph to process |
| `researching` | Research phase active |
| `researched` | Research done, ready for scoping |
| `invalidated` | Dead end, won't implement |
| `parked` | Needs human decision |
| `decomposing` | Breaking into sub-ideas |
| `scoped` | PRD created |
| `implementing` | Code being written |
| `blocked` | Stuck on dependency |
| `completed` | Done! |
| `failed` | Gave up after retries |

## Quick Start

```bash
# Run the loop (processes ideas continuously)
./research-ralph.sh

# Process a single idea and exit
./research-ralph.sh --once --idea 13

# Dry run to see what would happen
./research-ralph.sh --dry-run --idea 5

# Interactive mode (pause between phases for review)
./research-ralph.sh --interactive --idea 13
```

## Requirements

- `claude` CLI (Claude Code) installed and authenticated
- `idea-pool` MCP server configured with the following tools:
  - `get_workable_ideas()` - Find ideas ready for processing
  - `set_lifecycle()` - Change idea state
  - `read_idea()` / `append_to_idea()` - Read and update ideas
  - `create_sub_idea()` - Create child ideas
  - `add_dependency()` - Track blocking relationships
  - `check_parent_completion()` - Roll up child completions
  - `get_ralph_status()` - Dashboard view
- Bash 4.0+

## Usage

```
./research-ralph.sh [--once] [--dry-run] [--idea IDEA_ID] [--interactive]

Options:
  --once        Run once and exit (don't loop continuously)
  --dry-run     Show what would be done without executing
  --idea ID     Process a specific idea by number or pattern
  --interactive Pause for human review between phases
  --help        Show help message
```

## Phases

### 1. Extract (Idea Selection)

Queries the idea pool for the next workable idea:
- State: `backlog`
- Not blocked by dependencies
- Prioritized by the idea pool server

### 2. Research (Mandatory)

**This phase cannot be skipped.** Transitions idea to `researching` state.

The agent must:
- Read the idea content
- Search for prior art (existing implementations, tools)
- Look for academic papers or blog posts
- Identify theoretical foundations
- Document failure modes and pitfalls

Writes research notes directly to the idea via `append_to_idea()`.

**Research outcomes:**
- `proceed` → Continue to decomposition check (state: `researched`)
- `invalidate` → Mark as dead end (state: `invalidated`)
- `park` → Needs human decision (state: `parked`)

Time-boxed to prevent research paralysis (default: 30 minutes).

### 3. Decomposition Check

Evaluates if the idea is too large for atomic implementation:
- More than 5 success criteria needed?
- More than 3 independent components?

If decomposition is needed:
- Creates child ideas via `create_sub_idea()`
- Sets up dependencies via `add_dependency()`
- Parent enters `decomposing` state
- Children are added to `backlog`
- Loop continues to process children

If atomic, continues to PRD phase.

### 4. PRD Creation

Creates a Product Requirements Document (state: `scoped`):
- Problem Statement
- Research Summary
- Proposed Solution
- Success Criteria (max 5 for atomic ideas)
- Non-Goals
- Technical Approach
- Risks & Mitigations
- Estimated Complexity (S/M/L)

PRD is appended directly to the idea file.

### 5. Implementation (Classic Ralph)

The core Ralph loop (state: `implementing`):
```
while retries < max:
    result = claude("Implement the PRD...")
    if result == COMPLETE: break
    if result == BLOCKED: create_dependency(); break
    retries++
```

**Implementation outcomes:**
- `COMPLETE` → All success criteria met (state: `completed`)
- `BLOCKED: reason` → Dependency discovered (state: `blocked`)
- `STUCK: reason` → Retry or eventually fail (state: `failed`)

On completion, checks if any parent idea can now complete via `check_parent_completion()`.

## Configuration

Edit `research-ralph.conf` to customize:

```bash
# Research time limit (minutes)
RESEARCH_TIME_BOX_MINUTES=30

# Max implementation retries before failure
MAX_IMPLEMENTATION_RETRIES=3

# Decomposition thresholds
MAX_SUCCESS_CRITERIA=5
MAX_INDEPENDENT_COMPONENTS=3

# Sleep interval when no ideas (seconds)
SLEEP_INTERVAL=3600

# Enable interactive mode by default
INTERACTIVE=false
```

## Key Differences from Original Ralph

| Aspect | Original Ralph | Research-First Ralph |
|--------|---------------|---------------------|
| Input | Single PROMPT.md | Idea pool (many ideas) |
| Research | None (jump to code) | Mandatory pre-phase |
| Decomposition | None | Auto-splits large ideas |
| Dependencies | None | Tracks blocking relationships |
| Documentation | Optional | PRD required |
| State tracking | File on disk | Idea pool lifecycle |
| Failure handling | None | Retry with limits |
| Scope | One task | Continuous multi-task |

## MCP Tools Used

| Tool | Purpose |
|------|---------|
| `get_workable_ideas()` | Find ideas ready for processing |
| `get_ralph_status()` | Dashboard of all idea states |
| `set_lifecycle()` | Transition idea between states |
| `read_idea()` | Get full idea content |
| `append_to_idea()` | Add research notes, PRD |
| `create_sub_idea()` | Decompose into children |
| `add_dependency()` | Track blocking relationships |
| `check_parent_completion()` | Roll up when children complete |

## References

- [ghuntley.com/ralph](https://ghuntley.com/ralph/) — Original technique
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — Claude Code CLI
- [snarktank/ralph](https://github.com/snarktank/ralph) — PRD-driven autonomous agent

## License

MIT
