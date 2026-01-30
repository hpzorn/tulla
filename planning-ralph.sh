#!/bin/bash
# planning-ralph.sh - Implementation Planning from Discovery
#
# Takes discovery documents and creates actionable implementation plans
# using existing internal capabilities. Only emits research requests
# when truly blocked by unknowns.
#
# Workflow Position:
#   Discovery-Ralph → Planning-Ralph → Implementation
#                          ↓
#             (if blocked by unknowns)
#                          ↓
#                    Research-Ralph
#                          ↓
#                    Planning-Ralph (retry)
#
# Planning Protocol Phases:
#   P1: Load Discovery Context   (5 min)  - Read D1-D5 documents
#   P2: Codebase Analysis        (20 min) - Analyze internal implementations
#   P3: Architecture Design      (15 min) - Connect existing pieces
#   P4: Implementation Plan      (20 min) - File-level, task-level detail
#   P5: Research Requests        (5 min)  - Emit blocking unknowns (if any)
#
# Usage: ./planning-ralph.sh --idea IDEA_ID [--once] [--dry-run] [--interactive]
#
# Reference: https://ghuntley.com/ralph/

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/planning-ralph.conf"

# Load config if exists
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
fi

# shellcheck source=./hygiene-lib.sh
source "$SCRIPT_DIR/hygiene-lib.sh"

# Defaults (can be overridden in config)
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/work}"
DRY_RUN="${DRY_RUN:-false}"
SINGLE_RUN="${SINGLE_RUN:-false}"
SPECIFIC_IDEA="${SPECIFIC_IDEA:-}"
INTERACTIVE="${INTERACTIVE:-false}"
CLEAN="${CLEAN:-true}"

# Budget Control
MAX_BUDGET_USD="${MAX_BUDGET_USD:-5.00}"

# Phase Time Boxes (in minutes)
P1_DISCOVERY_LOAD_MINUTES="${P1_DISCOVERY_LOAD_MINUTES:-5}"
P2_CODEBASE_ANALYSIS_MINUTES="${P2_CODEBASE_ANALYSIS_MINUTES:-20}"
P3_ARCHITECTURE_DESIGN_MINUTES="${P3_ARCHITECTURE_DESIGN_MINUTES:-15}"
P4_IMPLEMENTATION_PLAN_MINUTES="${P4_IMPLEMENTATION_PLAN_MINUTES:-20}"
P5_RESEARCH_REQUESTS_MINUTES="${P5_RESEARCH_REQUESTS_MINUTES:-5}"
P6_RDF_EXPORT_MINUTES="${P6_RDF_EXPORT_MINUTES:-10}"

# PRD Ontology Namespaces
PRD_NS="http://impl-ralph.io/prd#"
TRACE_NS="http://impl-ralph.io/trace#"

# Known internal paths for codebase analysis
SKILLS_DIR="${SKILLS_DIR:-$HOME/.claude/skills}"
VISUAL_TOOLS_DIR="${VISUAL_TOOLS_DIR:-$HOME/visual-tools}"
MCP_SERVERS_DIR="${MCP_SERVERS_DIR:-$HOME/.claude/mcp-servers}"

# =============================================================================
# Argument Parsing
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --once)
            SINGLE_RUN=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --idea)
            SPECIFIC_IDEA="$2"
            shift 2
            ;;
        --interactive)
            INTERACTIVE=true
            shift
            ;;
        --max-budget)
            MAX_BUDGET_USD="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 --idea IDEA_ID [--once] [--dry-run] [--interactive] [--max-budget USD]"
            echo ""
            echo "Options:"
            echo "  --idea ID        Required: Process a specific idea"
            echo "  --once           Run once and exit (don't loop)"
            echo "  --dry-run        Show what would be done without executing"
            echo "  --interactive    Pause for human review between phases"
            echo "  --max-budget USD Max API cost per Claude call (default: 5.00)"
            echo "  --help           Show this help message"
            echo ""
            echo "Requires discovery documents in: work/discovery-<ID>-*/ or work/discovery-<ID>-manual/"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate required arguments
if [[ -z "$SPECIFIC_IDEA" ]]; then
    echo "Error: --idea IDEA_ID is required"
    echo "Usage: $0 --idea IDEA_ID [--once] [--dry-run] [--interactive]"
    exit 1
fi

# =============================================================================
# Logging
# =============================================================================

LOG_FILE="${WORK_DIR}/planning-ralph.log"

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE" >&2
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }
log_phase() {
    echo "" >&2
    echo "============================================================" >&2
    log "PHASE" "$@"
    echo "============================================================" >&2
}

# =============================================================================
# Interactive Mode
# =============================================================================

pause_if_interactive() {
    local phase="$1"
    if [[ "$INTERACTIVE" == "true" ]]; then
        echo "" >&2
        read -rp "[INTERACTIVE] Phase '$phase' complete. Press Enter to continue, or Ctrl+C to abort... " </dev/tty
    fi
}

# =============================================================================
# Setup
# =============================================================================

setup() {
    mkdir -p "$WORK_DIR"
    touch "$LOG_FILE"
    log_info "Planning-Ralph starting..."
    log_info "Work directory: $WORK_DIR"
    log_info "Idea: $SPECIFIC_IDEA"
    log_info "Dry run: $DRY_RUN"
    log_info "Interactive: $INTERACTIVE"
}

# =============================================================================
# Helper: Find discovery directory
# =============================================================================

find_discovery_dir() {
    local idea_id="$1"

    # Look for discovery directories in order of preference
    local candidates=(
        "$WORK_DIR/discovery-${idea_id}-manual"
        "$WORK_DIR/discovery-${idea_id}"
    )

    # Also look for timestamped directories
    for dir in "$WORK_DIR"/discovery-"${idea_id}"-[0-9]*; do
        if [[ -d "$dir" ]]; then
            candidates+=("$dir")
        fi
    done

    for dir in "${candidates[@]}"; do
        if [[ -d "$dir" ]] && [[ -f "$dir/D1-inventory.md" || -f "$dir/DISCOVERY-SUMMARY.md" ]]; then
            echo "$dir"
            return 0
        fi
    done

    log_error "No discovery directory found for idea $idea_id"
    log_error "Expected: $WORK_DIR/discovery-${idea_id}-* with D1-inventory.md or DISCOVERY-SUMMARY.md"
    return 1
}

# =============================================================================
# Helper: Get timeout command
# =============================================================================

get_timeout_cmd() {
    local minutes="$1"
    if command -v timeout &>/dev/null; then
        echo "timeout ${minutes}m"
    elif command -v gtimeout &>/dev/null; then
        echo "gtimeout ${minutes}m"
    else
        echo ""
    fi
}

# =============================================================================
# Phase P1: Load Discovery Context
# =============================================================================

run_p1_discovery_load() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local discovery_dir="$3"
    local output_file="$planning_work_dir/p1-discovery-context.md"

    log_info "P1: Load Discovery Context (${P1_DISCOVERY_LOAD_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would load discovery from $discovery_dir"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P1_DISCOVERY_LOAD_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write,Glob" \
        -p "You are conducting Phase P1: Load Discovery Context for idea ${idea_id}.

## Goal
Load and synthesize all discovery documents into a unified planning context.

## Instructions

1. Read the original idea: use mcp__idea-pool__read_idea with identifier ${idea_id}

2. Read all discovery documents from: ${discovery_dir}
   - D1-inventory.md (technical inventory)
   - D2-personas.md (user personas)
   - D3-value-mapping.md (value proposition)
   - D4-gap-analysis.md (gaps identified)
   - D5-research-brief.md (research questions if any)
   - DISCOVERY-SUMMARY.md (summary)

   Use Glob to find files if names vary slightly.

3. Write a consolidated context to: ${output_file}

   Structure:

   # P1: Discovery Context
   **Idea**: ${idea_id}
   **Date**: ${planning_date}
   **Discovery Source**: ${discovery_dir}

   ## Idea Summary
   [One paragraph summary of what we're building]

   ## User Persona
   [Key persona characteristics from D2]

   ## Value Proposition
   [Core value from D3]

   ## Existing Capabilities (from D1)

   ### Available Tools
   | Tool/Skill | Type | Relevance |
   |------------|------|-----------|
   | ... | MCP/Skill/Library | High/Medium/Low |

   ### Validated Technologies
   [What has been tested and works]

   ## Gaps to Address (from D4)

   | Gap | Priority | Type |
   |-----|----------|------|
   | ... | P0/P1/P2 | Implementation/Research/Design |

   ## Open Research Questions (from D5)
   [List any questions that need research-ralph, or 'None' if all clear]

   ## Planning Constraints
   - Must use: [existing tools/patterns]
   - Should avoid: [anti-patterns identified]
   - Success criteria: [from D3]

Be thorough but concise. This context drives all subsequent planning." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "P1 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "P1-discovery-load"
    return 0
}

# =============================================================================
# Phase P2: Codebase Analysis
# =============================================================================

run_p2_codebase_analysis() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local p1_file="$planning_work_dir/p1-discovery-context.md"
    local output_file="$planning_work_dir/p2-codebase-analysis.md"

    log_info "P2: Codebase Analysis (${P2_CODEBASE_ANALYSIS_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would analyze codebase"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P2_CODEBASE_ANALYSIS_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "Read,Write,Glob,Grep" \
        -p "You are conducting Phase P2: Codebase Analysis for idea ${idea_id}.

## Goal
Deeply analyze internal implementations to understand HOW existing tools work,
not just WHAT they do. This enables accurate planning.

## Context
Read the discovery context: ${p1_file}

## Internal Paths to Analyze

1. **Skills Directory**: ${SKILLS_DIR}
   - Look for presentation skills (beamer-inovex, typst-presentation)
   - Understand skill structure, how they work

2. **Visual Tools**: ${VISUAL_TOOLS_DIR}
   - MCP servers for rendering (kpi-cards, process-flow, compose-scene)
   - nano-banana for image generation

3. **MCP Servers Config**: ${MCP_SERVERS_DIR}
   - How are MCP tools configured and called?

## Instructions

1. Use Glob to find relevant files:
   - \`${SKILLS_DIR}/**/*.md\` for skill definitions
   - \`${VISUAL_TOOLS_DIR}/**/server.py\` for MCP servers
   - \`${VISUAL_TOOLS_DIR}/**/pyproject.toml\` for dependencies

2. Read key implementation files to understand:
   - How are skills structured? What's the interface?
   - How do MCP tools receive and return data?
   - What patterns are used for composition?
   - What are the actual function signatures?

3. Write analysis to: ${output_file}

   Structure:

   # P2: Codebase Analysis
   **Idea**: ${idea_id}
   **Date**: ${planning_date}

   ## Skill Architecture

   ### Skill Structure
   [How skills are defined and invoked]

   ### Key Skills for This Project

   #### beamer-inovex
   **Location**: [path]
   **Interface**: [how to invoke]
   **Key Functions**: [what it provides]
   **Limitations**: [what it can't do]

   #### typst-presentation
   **Location**: [path]
   **Interface**: [how to invoke]
   **Key Functions**: [what it provides]
   **Limitations**: [what it can't do]

   ## MCP Server Architecture

   ### Server Structure
   [How MCP servers work, common patterns]

   ### Key Servers for This Project

   #### compose-scene
   **Location**: [path]
   **Tools Exposed**: [list]
   **Input/Output Format**: [describe]
   **Integration Pattern**: [how to use]

   #### kpi-cards
   **Location**: [path]
   **Tools Exposed**: [list]
   **Input/Output Format**: [describe]

   [Continue for other relevant servers...]

   ## Integration Patterns

   ### Existing Composition Patterns
   [How are tools currently composed together?]

   ### Data Flow
   [How does data flow between components?]

   ### Error Handling
   [How do existing tools handle errors?]

   ## Reusable Components

   | Component | Location | Can Reuse For |
   |-----------|----------|---------------|
   | ... | ... | ... |

   ## Extension Points

   [Where can we add new functionality without rewriting?]
   - Skill extension: [how]
   - MCP tool addition: [how]
   - Template addition: [how]

   ## Code Quality Observations

   [Patterns to follow, anti-patterns to avoid]

Focus on UNDERSTANDING the code deeply enough to write a precise implementation plan." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "P2 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "P2-codebase-analysis"
    return 0
}

# =============================================================================
# Phase P3: Architecture Design
# =============================================================================

run_p3_architecture_design() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local p1_file="$planning_work_dir/p1-discovery-context.md"
    local p2_file="$planning_work_dir/p2-codebase-analysis.md"
    local output_file="$planning_work_dir/p3-architecture-design.md"

    log_info "P3: Architecture Design (${P3_ARCHITECTURE_DESIGN_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would design architecture"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P3_ARCHITECTURE_DESIGN_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "Read,Write" \
        -p "You are conducting Phase P3: Architecture Design for idea ${idea_id}.

## Goal
Design how existing components will be connected to achieve the goal.
Minimize new code; maximize reuse of existing capabilities.

## Context
- Discovery context: ${p1_file}
- Codebase analysis: ${p2_file}

Read both files thoroughly before designing.

## Instructions

Design an architecture that:
1. Reuses existing tools/skills wherever possible
2. Creates minimal new code (glue/orchestration)
3. Is concrete enough to implement directly
4. Addresses all gaps identified in discovery

Write to: ${output_file}

Structure:

# P3: Architecture Design
**Idea**: ${idea_id}
**Date**: ${planning_date}

## Design Principles

1. [Principle 1 from the analysis]
2. [Principle 2]
...

## System Architecture

### High-Level Flow

\`\`\`
[User Input] → [Component A] → [Component B] → [Output]
                     ↓
              [Component C]
\`\`\`

### Components

#### Component: [Name]
**Type**: [New/Existing/Extended]
**Source**: [Location if existing, or 'new']
**Responsibility**: [What it does]
**Inputs**: [What it receives]
**Outputs**: [What it produces]
**Dependencies**: [What it needs]

[Repeat for each component...]

## Data Flow

### Input Format
[What the user provides]

### Intermediate Formats
[Data structures between components]

### Output Format
[Final deliverable]

## Integration Plan

### Existing → Existing Connections
[How to connect existing tools]

### New Orchestration Layer
[What new code is needed to connect things]

## File Structure

\`\`\`
[project-root]/
├── [file1] - [purpose]
├── [file2] - [purpose]
└── [dir]/
    ├── [file3] - [purpose]
    └── [file4] - [purpose]
\`\`\`

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| [Decision 1] | [Choice] | [Why] |
| [Decision 2] | [Choice] | [Why] |

## Unknowns Requiring Research

| Unknown | Why It Matters | Blocking? |
|---------|----------------|-----------|
| [Unknown 1] | [Impact] | Yes/No |

If 'Yes' to any blocking unknown, we will emit research requests in P5.

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| [Risk 1] | [How to handle] |

Be concrete and specific. This design will be translated directly into implementation tasks." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "P3 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "P3-architecture-design"
    return 0
}

# =============================================================================
# Phase P4: Implementation Plan
# =============================================================================

run_p4_implementation_plan() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local p1_file="$planning_work_dir/p1-discovery-context.md"
    local p2_file="$planning_work_dir/p2-codebase-analysis.md"
    local p3_file="$planning_work_dir/p3-architecture-design.md"
    local output_file="$planning_work_dir/p4-implementation-plan.md"

    log_info "P4: Implementation Plan (${P4_IMPLEMENTATION_PLAN_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create implementation plan"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P4_IMPLEMENTATION_PLAN_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "Read,Write" \
        -p "You are conducting Phase P4: Implementation Plan for idea ${idea_id}.

## Goal
Create a detailed, executable implementation plan with file-level and task-level specificity.
Someone should be able to implement this without asking any questions.

## Context
- Discovery: ${p1_file}
- Codebase: ${p2_file}
- Architecture: ${p3_file}

Read all three files before planning.

## Instructions

Write to: ${output_file}

Structure:

# P4: Implementation Plan
**Idea**: ${idea_id}
**Date**: ${planning_date}
**Estimated Effort**: [S/M/L]

## Prerequisites

Before starting:
- [ ] [Prerequisite 1]
- [ ] [Prerequisite 2]

## Implementation Phases

### Phase 1: [Name] (P0 - Critical Path)

**Goal**: [What this phase achieves]
**Deliverable**: [Concrete output]

#### Task 1.1: [Task Name]
**File(s)**: \`path/to/file.py\`
**Action**: Create/Modify/Extend
**Details**:
\`\`\`python
# Pseudocode or actual code structure
class NewComponent:
    def __init__(self, ...):
        ...

    def main_method(self, ...):
        # Step 1: ...
        # Step 2: ...
\`\`\`
**Dependencies**: None / Task X.Y
**Verification**: How to test this works

#### Task 1.2: [Task Name]
**File(s)**: \`path/to/file.py\`
...

### Phase 2: [Name] (P1 - Important)

[Same structure...]

### Phase 3: [Name] (P2 - Nice to Have)

[Same structure...]

## File Changes Summary

| File | Action | Phase | Lines (est) |
|------|--------|-------|-------------|
| \`path/to/file1.py\` | Create | 1 | ~50 |
| \`path/to/file2.py\` | Modify | 1 | ~20 |
| ... | ... | ... | ... |

## Testing Plan

### Unit Tests
| Test | What It Verifies |
|------|------------------|
| test_1 | ... |

### Integration Tests
| Test | What It Verifies |
|------|------------------|
| test_1 | ... |

### Manual Verification
1. [Step 1]: Expected result
2. [Step 2]: Expected result

## Rollback Plan

If implementation fails:
1. [How to revert]
2. [What to clean up]

## Success Criteria

From discovery, verify:
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Blocked Tasks (Need Research)

| Task | Blocked By | Research Question |
|------|------------|-------------------|
| [Task if any] | [Unknown] | [Question for research-ralph] |

If this table is empty, proceed directly to implementation.
If not empty, P5 will emit research requests.

Be extremely specific. Include actual file paths, function names, and code structures." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "P4 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "P4-implementation-plan"
    return 0
}

# =============================================================================
# Phase P5: Research Requests (if needed)
# =============================================================================

run_p5_research_requests() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local p4_file="$planning_work_dir/p4-implementation-plan.md"
    local output_file="$planning_work_dir/p5-research-requests.md"

    log_info "P5: Research Requests (${P5_RESEARCH_REQUESTS_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would check for research needs"
        echo "ready"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P5_RESEARCH_REQUESTS_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "Read,Write" \
        -p "You are conducting Phase P5: Research Requests for idea ${idea_id}.

## Goal
Determine if implementation can proceed, or if research is needed first.

## Context
Read the implementation plan: ${p4_file}

Look for the 'Blocked Tasks (Need Research)' section.

## Instructions

Write to: ${output_file}

If NO blocked tasks (table is empty):

   # P5: Research Requests
   **Idea**: ${idea_id}
   **Date**: ${planning_date}

   ## Status: READY TO IMPLEMENT

   No blocking unknowns identified. Implementation can proceed.

   ## Planning Artifacts
   - p1-discovery-context.md
   - p2-codebase-analysis.md
   - p3-architecture-design.md
   - p4-implementation-plan.md

   ## Next Step
   Execute the implementation plan in p4-implementation-plan.md

   ---
   ready

If BLOCKED tasks exist:

   # P5: Research Requests
   **Idea**: ${idea_id}
   **Date**: ${planning_date}

   ## Status: BLOCKED - RESEARCH NEEDED

   The following unknowns must be resolved before implementation.

   ## Research Requests

   ### RR1: [Research Request Title]
   **Blocking Task**: [Which task from P4]
   **Question**: [Specific, answerable question]
   **Why We Can't Proceed**: [What breaks without this answer]
   **Suggested Approach**: [How research-ralph should investigate]
   **Acceptable Answer Format**: [What kind of answer we need]

   ### RR2: [If multiple]
   ...

   ## Handoff to Research-Ralph

   Run: \`./research-ralph.sh --idea ${idea_id}\` with focus on:
   - [RR1 question]
   - [RR2 question if any]

   After research completes, re-run planning-ralph to update the plan.

   ---
   blocked

Output ONLY 'ready' or 'blocked' on the final line." 2>&1 | tee -a "$LOG_FILE" >&2

    if [[ ! -f "$output_file" ]]; then
        log_error "P5 did not produce $output_file"
        return 1
    fi

    # Extract status
    local status
    status=$(tail -5 "$output_file" | grep -iE '^(ready|blocked)' | head -1 | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

    if [[ -z "$status" ]]; then
        status="ready"
    fi

    log_info "P5 status: $status"
    pause_if_interactive "P5-research-requests"
    echo "$status"
}

# =============================================================================
# Phase P6: Export to RDF (for Implementation-Ralph)
# =============================================================================

run_p6_rdf_export() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local p4_file="$planning_work_dir/p4-implementation-plan.md"
    local output_file="$planning_work_dir/p6-prd-ontology.ttl"
    local summary_file="$planning_work_dir/p6-rdf-export.md"

    log_info "P6: Export to RDF (${P6_RDF_EXPORT_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would export PRD to RDF"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P6_RDF_EXPORT_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    # Pre-create output files
    touch "$output_file"
    touch "$summary_file"

    $timeout_cmd claude --permission-mode acceptEdits \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "Read,Write,mcp__ontology-server__add_triple,mcp__ontology-server__store_fact" \
        -p "You are conducting Phase P6: Export PRD to RDF for idea ${idea_id}.

## Goal
Convert the implementation plan into RDF requirements that Implementation-Ralph can consume.
This creates the semantic graph of requirements with dependencies for the ontology-driven implementation loop.

## Context
Read the implementation plan: ${p4_file}

## PRD Ontology Schema

Use these namespaces:
\`\`\`turtle
@prefix prd: <${PRD_NS}> .
@prefix trace: <${TRACE_NS}> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
\`\`\`

### Classes
- \`prd:Requirement\` - A single implementable requirement/task
- \`prd:AcceptanceCriteria\` - Success condition for verification

### Properties
- \`prd:title\` (string) - Short name for the requirement
- \`prd:description\` (string) - Full requirement text
- \`prd:status\` - One of: \`prd:Pending\`, \`prd:InProgress\`, \`prd:Complete\`
- \`prd:dependsOn\` - Requirement → Requirement (dependency link)
- \`prd:priority\` - One of: \`prd:P0\`, \`prd:P1\`, \`prd:P2\`
- \`prd:phase\` (integer) - Implementation phase number
- \`prd:taskId\` (string) - Original task ID from P4 (e.g., '1.1', '2.3')
- \`prd:files\` (string) - Files to create/modify
- \`prd:action\` (string) - Either 'create' (new file) or 'modify' (edit existing file in its native language). IMPORTANT: when action is 'modify', Implementation-Ralph will edit the file in place using its native language (bash for .sh, markdown for .md, etc.) — it will NOT create a Python substitute.
- \`prd:verification\` (string) - How to verify completion

## Instructions

1. Read the implementation plan from ${p4_file}

2. Extract each task from the 'Implementation Phases' section
   - Each 'Task X.Y' becomes a \`prd:Requirement\` instance
   - Use task dependencies to set \`prd:dependsOn\` relationships
   - Phase 1 tasks are P0, Phase 2 are P1, Phase 3 are P2

3. Write Turtle RDF to: ${output_file}

   Structure:
   \`\`\`turtle
   @prefix prd: <${PRD_NS}> .
   @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
   @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
   @prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

   # Requirement 1.1
   prd:req-${idea_id}-1-1 a prd:Requirement ;
       prd:taskId \"1.1\" ;
       prd:title \"[Task title]\" ;
       prd:description \"\"\"[Full task description including code structure]\"\"\" ;
       prd:status prd:Pending ;
       prd:priority prd:P0 ;
       prd:phase 1 ;
       prd:files \"path/to/file.py\" ;
       prd:action \"create\" ;
       prd:verification \"[How to verify]\" .

   # Requirement 1.2 (depends on 1.1, modifies existing file)
   prd:req-${idea_id}-1-2 a prd:Requirement ;
       prd:taskId \"1.2\" ;
       prd:title \"[Task title]\" ;
       prd:description \"\"\"[Full task description — when action is modify, include exact insertion points and code in the file's native language]\"\"\" ;
       prd:status prd:Pending ;
       prd:priority prd:P0 ;
       prd:phase 1 ;
       prd:files \"path/to/existing-script.sh\" ;
       prd:action \"modify\" ;
       prd:verification \"[How to verify]\" ;
       prd:dependsOn prd:req-${idea_id}-1-1 .

   # Continue for all tasks...
   \`\`\`

4. After writing the Turtle file, use mcp__ontology-server__add_triple to add each requirement to the ontology-server
   - Context/graph: \"prd-${idea_id}\"
   - Add each triple from the Turtle file

5. Write a summary to: ${summary_file}

   Structure:

   # P6: RDF Export Summary
   **Idea**: ${idea_id}
   **Date**: ${planning_date}

   ## Export Status: SUCCESS

   ## Requirements Created

   | Requirement ID | Title | Priority | Dependencies |
   |----------------|-------|----------|--------------|
   | req-${idea_id}-1-1 | ... | P0 | None |
   | req-${idea_id}-1-2 | ... | P0 | 1.1 |
   | ... | ... | ... | ... |

   ## Dependency Graph

   \`\`\`
   [ASCII representation of dependency graph]
   \`\`\`

   ## Ontology Location

   - Turtle file: ${output_file}
   - Graph context: prd-${idea_id}

   ## Next Step

   Run Implementation-Ralph:
   \`\`\`
   ./implementation-ralph.sh --idea ${idea_id}
   \`\`\`

Be precise with RDF syntax. Each task from P4 becomes exactly one prd:Requirement." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -s "$output_file" ]]; then
        log_error "P6 did not produce RDF output in $output_file"
        return 1
    fi

    log_info "P6 complete: RDF exported to $output_file"
    pause_if_interactive "P6-rdf-export"
    return 0
}

# =============================================================================
# Main Processing
# =============================================================================

process_idea() {
    local idea_id="$1"

    # Find discovery directory
    local discovery_dir
    if ! discovery_dir=$(find_discovery_dir "$idea_id"); then
        log_error "Cannot proceed without discovery documents"
        log_error "Run discovery-ralph first: ./discovery-ralph.sh --idea $idea_id"
        return 1
    fi

    log_info "Found discovery at: $discovery_dir"

    # Create planning work directory
    local planning_work_dir="$WORK_DIR/planning-$idea_id-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$planning_work_dir"

    log_info "Processing idea: $idea_id"
    log_info "Planning work directory: $planning_work_dir"

    # Phase P1: Load Discovery Context
    log_phase "P1. DISCOVERY LOAD"
    if ! run_p1_discovery_load "$idea_id" "$planning_work_dir" "$discovery_dir"; then
        log_error "P1 failed"
        return 1
    fi

    # Phase P2: Codebase Analysis
    log_phase "P2. CODEBASE ANALYSIS"
    if ! run_p2_codebase_analysis "$idea_id" "$planning_work_dir"; then
        log_error "P2 failed"
        return 1
    fi

    # Phase P3: Architecture Design
    log_phase "P3. ARCHITECTURE DESIGN"
    if ! run_p3_architecture_design "$idea_id" "$planning_work_dir"; then
        log_error "P3 failed"
        return 1
    fi

    # Phase P4: Implementation Plan
    log_phase "P4. IMPLEMENTATION PLAN"
    if ! run_p4_implementation_plan "$idea_id" "$planning_work_dir"; then
        log_error "P4 failed"
        return 1
    fi

    # Phase P5: Research Requests
    log_phase "P5. RESEARCH REQUESTS"
    local status
    status=$(run_p5_research_requests "$idea_id" "$planning_work_dir")

    # Pre-flight hygiene before P6 export to avoid stale ontology state
    if [[ "$status" == "ready" ]] && [[ "$CLEAN" == "true" ]]; then
        log_info "Running pre-flight hygiene before P6 export..."
        if ! run_preflight_hygiene "prd-${idea_id}" "$LOG_FILE" "$MAX_BUDGET_USD"; then
            log_warn "Pre-flight hygiene failed — proceeding with P6 anyway"
        fi
    fi

    # Phase P6: Export to RDF (only if ready to implement)
    if [[ "$status" == "ready" ]]; then
        log_phase "P6. RDF EXPORT"
        if ! run_p6_rdf_export "$idea_id" "$planning_work_dir"; then
            log_warn "P6 failed - RDF export unsuccessful, but plan is still usable"
        fi
    fi

    # Create summary
    local summary_file="$planning_work_dir/PLANNING-SUMMARY.md"
    cat > "$summary_file" << EOF
# Planning Summary: Idea ${idea_id}

## Status: $(echo "$status" | tr '[:lower:]' '[:upper:]')

## Planning Complete: $(date -Iseconds)

## Artifacts

| Phase | Document | Description |
|-------|----------|-------------|
| P1 | p1-discovery-context.md | Discovery synthesis |
| P2 | p2-codebase-analysis.md | Internal codebase analysis |
| P3 | p3-architecture-design.md | Architecture design |
| P4 | p4-implementation-plan.md | Detailed implementation plan |
| P5 | p5-research-requests.md | Research needs (if any) |
| P6 | p6-prd-ontology.ttl | PRD as RDF (for Implementation-Ralph) |

## Next Steps

EOF

    if [[ "$status" == "ready" ]]; then
        cat >> "$summary_file" << EOF
**Implementation can proceed.**

### Option 1: Implementation-Ralph (Ontology-Driven)

Requirements exported to RDF: \`p6-prd-ontology.ttl\`

Run the ontology-driven implementation loop:
\`\`\`
./implementation-ralph.sh --idea ${idea_id}
\`\`\`

This provides:
- SHACL-based completion verification
- Automatic trace links (code → requirements)
- Dependency-aware work selection

### Option 2: Manual Implementation

Execute tasks from \`p4-implementation-plan.md\` manually.
EOF
        log_info "Planning complete: READY TO IMPLEMENT"
        log_info "Plan location: $planning_work_dir/p4-implementation-plan.md"
        log_info "PRD RDF: $planning_work_dir/p6-prd-ontology.ttl"
    else
        cat >> "$summary_file" << EOF
**Research needed before implementation.**

See \`p5-research-requests.md\` for research questions.

Run research-ralph:
\`\`\`
./research-ralph.sh --idea ${idea_id}
\`\`\`

Then re-run planning-ralph to update the plan:
\`\`\`
./planning-ralph.sh --idea ${idea_id}
\`\`\`
EOF
        log_warn "Planning blocked: RESEARCH NEEDED"
        log_warn "See: $planning_work_dir/p5-research-requests.md"
    fi

    log_info "Planning summary: $summary_file"
    return 0
}

# =============================================================================
# Main
# =============================================================================

main() {
    setup

    if process_idea "$SPECIFIC_IDEA"; then
        log_info "Planning-Ralph complete for idea $SPECIFIC_IDEA"
        exit 0
    else
        log_error "Planning-Ralph failed for idea $SPECIFIC_IDEA"
        exit 1
    fi
}

# =============================================================================
# Entry Point
# =============================================================================

main "$@"
