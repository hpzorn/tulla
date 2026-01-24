# Handover: Research-First Ralph Implementation

**Date:** 2026-01-24
**From:** Idea Pool Server Developer
**To:** Ralph Loop Implementation Agent
**Status:** Ready for implementation

---

## Overview

You are implementing **Research-First Ralph** - an autonomous loop that processes ideas from the idea pool through research, PRD creation, and implementation phases.

The idea pool MCP server has been extended with all necessary tools. Your job is to create the bash loop and prompts that drive the workflow.

## Reference Document

Full specification: `idea-13-research-first-ralph-autonomous-idea-to-implementa.md`

Key quote from Geoffrey Huntley's original Ralph:
> *"That's the beauty of Ralph - the technique is deterministically bad in an undeterministic world."*

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        YOUR IMPLEMENTATION                          │
│                                                                     │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │                    research-ralph.sh                         │  │
│   │                                                              │  │
│   │   while true; do                                             │  │
│   │     1. Query idea pool for next workable idea                │  │
│   │     2. Run research phase (claude-code)                      │  │
│   │     3. Run PRD creation (claude-code)                        │  │
│   │     4. Run implementation loop (classic Ralph)               │  │
│   │     5. Update status                                         │  │
│   │   done                                                       │  │
│   └──────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│   ┌──────────────────────────────────────────────────────────────┐  │
│   │              Idea Pool MCP Server (ALREADY DONE)             │  │
│   │                                                              │  │
│   │   • get_workable_ideas()     • set_lifecycle()               │  │
│   │   • create_sub_idea()        • add_dependency()              │  │
│   │   • check_parent_completion() • get_ralph_status()           │  │
│   └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Lifecycle States

Ideas flow through these states:

```
seed ──────► backlog ──────► researching ──────► researched ──────► scoped ──────► implementing ──────► completed
               │                  │                   │                                  │
               │                  ▼                   ▼                                  ▼
               │            invalidated            parked                          blocked/failed
               │            (dead end)         (needs human)
               │
               └──► decomposing ──► spawns children to backlog
```

### State Definitions

| State | Meaning | Next States |
|-------|---------|-------------|
| `seed` | Raw capture in seeds/ | `backlog` |
| `backlog` | Queued for Ralph | `researching` |
| `researching` | Academic groundwork active | `researched`, `invalidated`, `parked` |
| `researched` | Research done, ready for PRD | `decomposing`, `scoped` |
| `invalidated` | Dead end, won't implement | (terminal) |
| `parked` | Needs human input | `backlog`, `researching` |
| `decomposing` | Breaking into sub-ideas | `scoped` + children→`backlog` |
| `scoped` | PRD created | `implementing` |
| `implementing` | Code being written | `completed`, `failed`, `blocked` |
| `blocked` | Stuck on dependency | `backlog`, `implementing` |
| `completed` | Done! | (terminal) |
| `failed` | Gave up after retries | `backlog` (for retry) |

---

## MCP Tools Available

### Querying Ideas

```python
# Get next idea to work on (backlog + unblocked)
get_workable_ideas(limit=10)
# Returns: List of ideas ready for processing

# Get all ideas in a specific state
get_ideas_by_lifecycle(lifecycle="backlog")

# Full workflow dashboard
get_ralph_status()
```

### State Transitions

```python
# Change lifecycle state
set_lifecycle(
    identifier="13",           # Idea number or filename
    new_state="researching",   # Target state
    reason="Starting research" # Optional note
)

# Convenience: move to backlog with priority
move_to_backlog(identifier="13", priority="high")
```

### Dependencies & Decomposition

```python
# Create child idea
create_sub_idea(
    parent_identifier="13",
    title="Implement lifecycle state machine",
    content="## Goal\nBuild the state machine...",
    auto_number=True  # Creates idea-13a, idea-13b, etc.
)

# Add blocking relationship
add_dependency(
    idea_identifier="13b",
    blocked_by="13a"  # 13b can't start until 13a completes
)

# Check if parent can complete
check_parent_completion(identifier="13")

# View dependencies
get_idea_dependencies(identifier="13")
```

### Reading/Writing

```python
# Read idea content
read_idea(identifier="13")

# Update idea content
update_idea(identifier="13", content="# Full markdown content...")

# Append notes
append_to_idea(identifier="13", content="## Research Notes\n...")
```

---

## Expected Loop Behavior

### Phase 1: Extract
```bash
# Query for next workable idea
IDEA=$(claude --print "Use get_workable_ideas(). Return ONLY the filepath of the first idea, nothing else. If none available, return 'NONE'.")
```

### Phase 2: Research
```bash
# Transition state
claude "Use set_lifecycle('$IDEA_ID', 'researching')"

# Do research
claude "
You are researching idea: $IDEA_PATH

Tasks:
1. Read the idea with read_idea()
2. Search for prior art (web search, academic papers)
3. Document findings in research-notes.md
4. Determine outcome:
   - 'proceed' if novel and feasible
   - 'invalidate' if already solved or fundamentally flawed
   - 'park' if needs human decision

Write research notes using append_to_idea().
Return ONLY one word: proceed, invalidate, or park
"
```

**On invalidate:**
```bash
claude "Use set_lifecycle('$IDEA_ID', 'invalidated', reason='[explanation]')"
```

**On park:**
```bash
claude "Use set_lifecycle('$IDEA_ID', 'parked', reason='[what human input needed]')"
```

### Phase 3: Decomposition Check
```bash
claude "Use set_lifecycle('$IDEA_ID', 'researched')"

# Check if needs decomposition
DECOMP=$(claude --print "
Read idea $IDEA_ID and its research notes.
If the idea needs >5 success criteria OR has >3 independent components:
  - Use create_sub_idea() for each component
  - Return 'decomposed'
Otherwise:
  - Return 'atomic'
")
```

**If decomposed:** Parent stays in `decomposing`, loop continues to pick children from backlog.

### Phase 4: PRD Creation
```bash
claude "Use set_lifecycle('$IDEA_ID', 'scoped')"

claude "
Create a PRD for idea $IDEA_ID.

Read the idea and research notes, then append a PRD section:

## PRD

### Problem Statement
[From idea]

### Research Summary
[Key findings]

### Proposed Solution
[Approach]

### Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
(max 5 for atomic ideas)

### Non-Goals
[What we're NOT doing]

### Technical Approach
[Implementation plan]

Use append_to_idea() to add the PRD.
"
```

### Phase 5: Implementation (Classic Ralph)
```bash
claude "Use set_lifecycle('$IDEA_ID', 'implementing')"

# Classic Ralph loop
RETRIES=0
MAX_RETRIES=3

while [ $RETRIES -lt $MAX_RETRIES ]; do
    RESULT=$(claude "
    Implement the PRD for idea $IDEA_ID.

    Read the idea file to get the PRD and success criteria.
    Work until ALL success criteria checkboxes are checked.

    If you discover a missing dependency:
      - Use create_sub_idea() to capture it
      - Use add_dependency() to mark the block
      - Return 'BLOCKED: [reason]'

    If all criteria met:
      - Return 'COMPLETE'

    If stuck after good effort:
      - Return 'STUCK: [reason]'

    <promise>ALL_SUCCESS_CRITERIA_MET</promise>
    ")

    case "$RESULT" in
        COMPLETE*)
            claude "Use set_lifecycle('$IDEA_ID', 'completed')"
            claude "Use check_parent_completion('$IDEA_ID')"  # Rollup check
            break
            ;;
        BLOCKED*)
            claude "Use set_lifecycle('$IDEA_ID', 'blocked', reason='${RESULT#BLOCKED: }')"
            break
            ;;
        *)
            RETRIES=$((RETRIES + 1))
            ;;
    esac
done

if [ $RETRIES -ge $MAX_RETRIES ]; then
    claude "Use set_lifecycle('$IDEA_ID', 'failed', reason='Max retries exceeded')"
fi
```

---

## File Structure

```
~/ideas/
├── idea-13-research-first-ralph-autonomous-idea-to-implementa.md  # This feature's spec
├── idea-13a-lifecycle-state-machine.md      # Sub-idea (example)
├── idea-13b-dependency-tracking.md          # Sub-idea (example)
├── seeds/                                    # Raw captures
├── mcp-server/
│   └── idea_pool_server.py                  # MCP server (DONE)
├── research-ralph/                          # YOUR IMPLEMENTATION
│   ├── research-ralph.sh                    # Main loop script
│   ├── prompts/
│   │   ├── research.md                      # Research phase prompt
│   │   ├── decompose.md                     # Decomposition prompt
│   │   ├── prd.md                           # PRD creation prompt
│   │   └── implement.md                     # Implementation prompt
│   └── README.md                            # Usage docs
└── HANDOVER-research-ralph.md               # This file
```

---

## Open Decisions (Your Call)

1. **Research depth**: Time-box (30 min)? Source count (min 3)? Let the LLM decide?

2. **Decomposition heuristics**: The spec says >5 criteria or >3 components. Adjust as needed.

3. **Human checkpoints**: Full autonomy or optional review gates? Consider a `--interactive` flag.

4. **Sleep behavior**: When no workable ideas, sleep for how long? 1 hour? Configurable?

5. **Cost tracking**: Log API costs per idea? Set budget limits?

6. **Parallelism**: Single-threaded to start. Consider multiple instances later.

---

## Success Criteria for Your Implementation

- [ ] Loop runs continuously without crashing
- [ ] Correctly identifies workable ideas (backlog + unblocked)
- [ ] Research phase produces research notes before proceeding
- [ ] Invalid/parked ideas don't proceed to implementation
- [ ] Large ideas get decomposed into sub-ideas
- [ ] Sub-ideas link back to parent
- [ ] Parent completes only when all children complete
- [ ] Blocked ideas don't spin (detected and state updated)
- [ ] Failed ideas marked after retry limit
- [ ] Clean logging of state transitions

---

## Testing Suggestions

1. **Happy path**: Create a small idea in backlog, run loop, verify completion

2. **Invalidation**: Create idea that duplicates existing solution, verify research catches it

3. **Decomposition**: Create large idea, verify it spawns children

4. **Blocking**: Create two ideas where B depends on A, verify ordering

5. **Parent rollup**: Complete all children, verify parent auto-completes

---

## Quick Start

```bash
# 1. Ensure idea pool server is running
cd ~/ideas/mcp-server
# (server should be configured in Claude Code MCP settings)

# 2. Move an idea to backlog
claude "Use move_to_backlog('13', priority='high')"

# 3. Check status
claude "Use get_ralph_status()"

# 4. Run your loop
cd ~/ideas/research-ralph
./research-ralph.sh
```

---

## Contact

Questions about the MCP server tools? The implementation is in:
`~/ideas/mcp-server/idea_pool_server.py`

The tools are well-documented with docstrings. Use `read_idea("13")` to see the full spec.

Good luck! 🚀
