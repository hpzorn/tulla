#!/bin/bash
echo 'WARNING: This script is deprecated. Use ralph run planning instead.' >&2
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
P4B_PERSONA_WALKTHROUGH_MINUTES="${P4B_PERSONA_WALKTHROUGH_MINUTES:-15}"
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
# Helper: Find research directory (optional — only for downstream research
# that answered discovery's RQs)
# =============================================================================

find_research_dir() {
    local idea_id="$1"

    local candidates=()

    # Look for custom-named research directories
    for dir in "$WORK_DIR"/idea-"${idea_id}"-research "$WORK_DIR"/idea-"${idea_id}"-[0-9]*; do
        if [[ -d "$dir" ]]; then
            candidates+=("$dir")
        fi
    done

    # Pick the most recent directory that has an r3 (RQ) file — this confirms
    # it was a research run, not just a work directory
    local best=""
    for dir in "${candidates[@]}"; do
        if [[ -f "$dir/r3-research-questions.md" ]]; then
            best="$dir"
        fi
    done

    if [[ -n "$best" ]]; then
        echo "$best"
        return 0
    fi

    return 1  # no research dir found — not an error, research is optional
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
    local research_dir="${4:-}"
    local output_file="$planning_work_dir/p1-discovery-context.md"

    log_info "P1: Load Discovery Context (${P1_DISCOVERY_LOAD_MINUTES} min time-box)"
    if [[ -n "$research_dir" ]]; then
        log_info "P1: Including downstream research findings from $research_dir"
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would load discovery from $discovery_dir"
        if [[ -n "$research_dir" ]]; then
            log_info "[DRY RUN] Would also load research from $research_dir"
        fi
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P1_DISCOVERY_LOAD_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    # Build research loading instructions (only if research dir exists)
    local research_instructions=""
    local research_output_section=""
    if [[ -n "$research_dir" ]]; then
        research_instructions="
3. Read downstream research findings from: ${research_dir}
   These are answers to the research questions identified in discovery (D4/D5).
   - r3-research-questions.md (the RQs that were investigated)
   - r4-literature-review.md (literature review per RQ)
   - r5-research-findings.md (experiments and prototypes)
   - r6-research-synthesis.md (conclusions and recommendations)

   Use Glob to find files if names vary slightly.
   These findings SUPERSEDE the open questions from D5 — the RQs have been answered.
"
        research_output_section="
   ## Research Findings (answers to discovery RQs)
   **Research Source**: ${research_dir}

   For each RQ that was investigated:
   ### RQ: [question]
   **Answer**: [key finding from R4/R5/R6]
   **Implication for planning**: [how this constrains or informs the architecture]

   ## Resolved Blockers
   [List blockers from D4 that are now resolved by research, with the resolution]
"
    fi

    local step_after_discovery="3"
    if [[ -n "$research_dir" ]]; then
        step_after_discovery="4"
    fi

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write,Glob" \
        -p "You are conducting Phase P1: Load Discovery Context for idea ${idea_id}.

## Goal
Load and synthesize all discovery documents$(if [[ -n "$research_dir" ]]; then echo " and downstream research findings"; fi) into a unified planning context.

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
${research_instructions}
${step_after_discovery}. Write a consolidated context to: ${output_file}

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
${research_output_section}
   ## Open Research Questions (from D5)
   [List any questions that still need research-ralph, or 'None — all resolved by downstream research' if research answered them]

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
    local schema_context_file="$SCRIPT_DIR/prompts/isaqb-schema-context.md"

    log_info "P3: Architecture Design (${P3_ARCHITECTURE_DESIGN_MINUTES} min time-box)"

    # Load iSAQB schema context if available
    local schema_context_block=""
    if [[ -f "$schema_context_file" ]]; then
        schema_context_block=$(cat "$schema_context_file")
        log_info "P3: Loaded iSAQB schema context from $schema_context_file"
    else
        log_warn "P3: iSAQB schema context not found at $schema_context_file — proceeding without"
    fi

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
        --allowedTools "Read,Write,mcp__ontology-server__query_ontology,mcp__ontology-server__sparql_query" \
        -p "You are conducting Phase P3: Architecture Design for idea ${idea_id}.

## Goal
Design how existing components will be connected to achieve the goal.
Minimize new code; maximize reuse of existing capabilities.

## Context
- Discovery context: ${p1_file}
- Codebase analysis: ${p2_file}

Read both files thoroughly before designing.

## iSAQB Architecture Schema

${schema_context_block}

Use the iSAQB schema above to inform your architecture design. You can query
the ontology-server via SPARQL (mcp__ontology-server__query_ontology or
mcp__ontology-server__sparql_query) to look up patterns, quality attributes,
tradeoffs, and design principles relevant to this idea.

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

## Quality Goals (isaqb:QualityGoal)

Select the top-3-to-5 quality attributes (from ISO 25010:2023 via the schema) for this project.
Query isaqb:conflictsWith to identify tradeoffs between them.

| Priority | Quality Attribute | Sub-Attributes | Rationale |
|----------|-------------------|----------------|-----------|
| 1 | [e.g. Maintainability] | [Modularity, Testability] | [Why this matters for this idea] |
| 2 | [e.g. Reliability] | [FaultTolerance] | [Why] |
| ... | ... | ... | ... |

### Quality Tradeoffs

| Attribute A | conflicts with | Attribute B | Resolution |
|-------------|---------------|-------------|------------|
| [e.g. PerformanceEfficiency] | ↔ | [e.g. Maintainability] | [How we resolve this tension] |

## Design Principles (isaqb:DesignPrinciple)

For each principle, note which isaqb:PrincipleCategory it belongs to.

1. **[Principle Name]** (Category: [Abstraction/Modularization/...]) — [How it applies here]
2. ...

## Architectural Patterns (isaqb:ArchitecturalPattern)

Query isaqb:addresses and isaqb:embodies to select patterns that match our quality goals and principles.

| Pattern | Addresses Quality | Embodies Principle | Relevance |
|---------|------------------|--------------------|-----------|
| [e.g. Ports & Adapters] | [Maintainability, Testability] | [Separation of Concerns] | R1 |
| ... | ... | ... | ... |

## System Architecture

### High-Level Flow

\`\`\`
[User Input] → [Component A] → [Component B] → [Output]
                     ↓
              [Component C]
\`\`\`

### Building Blocks (isaqb:ArchitecturalView — BuildingBlock)

#### Component: [Name]
**Type**: [New/Existing/Extended]
**Source**: [Location if existing, or 'new']
**Responsibility**: [What it does]
**Inputs**: [What it receives]
**Outputs**: [What it produces]
**Dependencies**: [What it needs]
**Realizes Pattern**: [isaqb:ArchitecturalPattern or DesignPattern if applicable]

[Repeat for each component...]

### Runtime View (isaqb:ArchitecturalView — Runtime)

[Sequence of interactions between building blocks at runtime]

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

## Cross-Cutting Concerns (isaqb:CrossCuttingConcern)

| Concern | Category | Governed By (Decision) | Affected Components |
|---------|----------|----------------------|---------------------|
| [e.g. Error Handling] | [Architecture/Design] | [ADR-N] | [Component list] |
| [e.g. Logging] | [Under-the-Hood] | [ADR-N] | [Component list] |

## Architecture Decisions (isaqb:ArchitectureDecision)

For each key decision, create an ADR with context, options, rationale, and consequences.
Link to quality attributes via isaqb:addresses/isaqb:challenges.

### ADR-1: [Decision Title]
**Status**: Proposed
**Context**: [Why this decision is needed]
**Options Considered**:
1. [Option A] — [pros/cons]
2. [Option B] — [pros/cons]
**Decision**: [Chosen option]
**Rationale**: [Why this option was chosen]
**Consequences**:
- Addresses: [quality attributes positively affected]
- Challenges: [quality attributes negatively affected]
- Mitigates: [risks addressed]

[Repeat for each major decision...]

## Quality Scenarios (isaqb:QualityScenario)

Write testable quality scenarios for the top quality goals.

| ID | Quality Attribute | Stimulus | Environment | Response | Measure |
|----|-------------------|----------|-------------|----------|---------|
| QS-1 | [e.g. Reliability] | [Trigger event] | [Under what conditions] | [System behavior] | [Measurable threshold] |
| QS-2 | ... | ... | ... | ... | ... |

## File Structure

\`\`\`
[project-root]/
├── [file1] - [purpose]
├── [file2] - [purpose]
└── [dir]/
    ├── [file3] - [purpose]
    └── [file4] - [purpose]
\`\`\`

## Risk Assessment (isaqb:Risk)

| Risk | Severity | Likelihood | Mitigation | Mitigated By (Decision) |
|------|----------|------------|------------|------------------------|
| [Risk 1] | [Critical/High/Medium/Low] | [High/Medium/Low] | [How to handle] | [ADR-N if applicable] |

## Unknowns Requiring Research

| Unknown | Why It Matters | Blocking? |
|---------|----------------|-----------|
| [Unknown 1] | [Impact] | Yes/No |

If 'Yes' to any blocking unknown, we will emit research requests in P5.

Be concrete and specific. This design will be translated directly into implementation tasks.
Link requirements to quality attributes (isaqb:addressesQuality) and decisions (isaqb:justifiedBy) where applicable." 2>&1 | tee -a "$LOG_FILE"

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
# Phase P4b: Persona Walkthrough — Simulate User Journeys
# =============================================================================

run_p4b_persona_walkthrough() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local p1_file="$planning_work_dir/p1-discovery-context.md"
    local p3_file="$planning_work_dir/p3-architecture-design.md"
    local p4_file="$planning_work_dir/p4-implementation-plan.md"
    local output_file="$planning_work_dir/p4b-persona-walkthrough.md"

    log_info "P4b: Persona Walkthrough (${P4B_PERSONA_WALKTHROUGH_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run persona walkthrough"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$P4B_PERSONA_WALKTHROUGH_MINUTES")
    local planning_date
    planning_date=$(date +%Y-%m-%d)

    # Find discovery directory for D2 personas
    local discovery_dir
    discovery_dir=$(find_discovery_dir "$idea_id" 2>/dev/null || echo "")
    local d2_file=""
    if [[ -n "$discovery_dir" ]]; then
        # Try both naming conventions
        for candidate in "$discovery_dir/d2-personas.md" "$discovery_dir/D2-personas.md"; do
            if [[ -f "$candidate" ]]; then
                d2_file="$candidate"
                break
            fi
        done
    fi

    local d2_instruction=""
    if [[ -n "$d2_file" ]]; then
        d2_instruction="- Original persona definitions: ${d2_file}"
    fi

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "Read,Write" \
        -p "You are conducting Phase P4b: Persona Walkthrough for idea ${idea_id}.

## Goal
Simulate a concrete, step-by-step user journey for EACH persona from discovery.
Walk through the ACTUAL implementation plan (P4) as if you are each persona
using the finished product. Identify gaps where the plan breaks the user
experience — especially mismatches between architecture decisions and how
real users interact with the system.

## Context
Read ALL of these:
- Discovery context (contains persona summaries): ${p1_file}
${d2_instruction}
- Architecture design: ${p3_file}
- Implementation plan: ${p4_file}

## Instructions

For each persona identified in D2/P1, simulate their primary user journey
step by step. Be concrete — name the actual tools, URLs, commands, and
interfaces they would use. At each step, verify the implementation plan
supports it.

Write to: ${output_file}

Structure:

# P4b: Persona Walkthrough
**Idea**: ${idea_id}
**Date**: ${planning_date}

## Walkthrough Method

For each persona, simulate their PRIMARY user journey (from D2's JTBD)
against the P4 implementation plan. At each step ask:
1. What does the persona physically do? (click, type, run)
2. What system component handles it? (from P3/P4)
3. Does the implementation plan cover this interaction?
4. What could go wrong at this step?

---

## Persona 1: [Name from D2]

**Journey**: [Primary JTBD from D2]

### Step 1: [Concrete action, e.g., 'Opens Chrome, navigates to http://localhost:8100/dashboard/']
**System path**: [Which P4 components handle this: route, middleware, template...]
**Covered by plan?**: YES/NO — [cite specific P4 task]
**Gap?**: [If NO or partial — describe what breaks]

### Step 2: [Next action]
**System path**: [...]
**Covered by plan?**: YES/NO
**Gap?**: [...]

[Continue for all steps in the journey...]

### Persona 1 Verdict: PASS / GAPS FOUND
**Gaps found**:
- [Gap 1: what breaks, which P4 task should address it but doesn't]
- [Gap 2: ...]

---

## Persona 2: [Name from D2]
[Same structure...]

---

## Cross-Persona Gap Summary

| # | Gap | Affected Personas | Severity | Blocks Implementation? |
|---|-----|-------------------|----------|----------------------|
| 1 | [Description] | [Which personas] | Critical/High/Medium/Low | Yes/No |
| 2 | ... | ... | ... | ... |

## Blocking Gaps (must fix before implementation)

For each gap with 'Blocks Implementation = Yes':

### Gap N: [Title]
**Problem**: [What breaks in the user journey]
**Root cause**: [Why P4 doesn't cover this — architecture assumption? Missing requirement?]
**Proposed fix**: [New task or modification to existing P4 task]
**Affected P4 tasks**: [Which tasks need updating]

## Non-Blocking Gaps (should fix, but can proceed)

[Same structure, lower priority]

## Verdict

**PASS** — All persona journeys are fully supported by the implementation plan.
or
**GAPS_FOUND: N blocking, M non-blocking** — Implementation plan needs updates before proceeding.

---
On the FINAL line, output exactly: WALKTHROUGH_PASS or WALKTHROUGH_GAPS

Be ruthlessly concrete. Do not accept hand-wavy 'auth is handled at the perimeter' —
trace exactly how each persona authenticates, what protocol they use, what UI they see.
The whole point of this phase is to catch abstraction-level mismatches between
architecture and real user interaction." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "P4b did not produce $output_file"
        return 1
    fi

    pause_if_interactive "P4b-persona-walkthrough"
    return 0
}

# =============================================================================
# Phase P5: Research Requests (if needed)
# =============================================================================

run_p5_research_requests() {
    local idea_id="$1"
    local planning_work_dir="$2"
    local p4_file="$planning_work_dir/p4-implementation-plan.md"
    local p4b_file="$planning_work_dir/p4b-persona-walkthrough.md"
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
Read BOTH of these:
- Implementation plan: ${p4_file} — look for the 'Blocked Tasks (Need Research)' section.
- Persona walkthrough: ${p4b_file} — look for 'Blocking Gaps' and the verdict line.

The implementation is BLOCKED if EITHER source has blockers:
- P4 has blocked tasks needing research, OR
- P4b found blocking persona gaps (WALKTHROUGH_GAPS with blocking items)

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
        --allowedTools "Read,Write,mcp__ontology-server__store_fact" \
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

4. After writing the Turtle file, use mcp__ontology-server__store_fact to add each requirement to the A-box fact store.
   - Context: \"prd-${idea_id}\"
   - For each triple (subject, predicate, object) in the Turtle file, call store_fact with:
     subject=the requirement URI (e.g. \"prd:req-${idea_id}-1-1\")
     predicate=the property (e.g. \"rdf:type\", \"prd:title\", \"prd:status\", etc.)
     object=the value
     context=\"prd-${idea_id}\"
   - Do NOT use add_triple — that writes to the T-box (ontology schema), not the A-box (fact store).
     Implementation-Ralph reads requirements via recall_facts, which only sees the A-box.

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

    # Find research directory (optional — only exists if research-ralph ran
    # downstream of discovery to answer RQs from D4/D5)
    local research_dir=""
    if research_dir=$(find_research_dir "$idea_id"); then
        log_info "Found downstream research at: $research_dir"
    else
        log_info "No downstream research found (proceeding with discovery only)"
        research_dir=""
    fi

    # Create planning work directory
    local planning_work_dir="$WORK_DIR/planning-$idea_id-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$planning_work_dir"

    log_info "Processing idea: $idea_id"
    log_info "Planning work directory: $planning_work_dir"

    # Phase P1: Load Discovery Context (+ research findings if available)
    log_phase "P1. DISCOVERY LOAD"
    if ! run_p1_discovery_load "$idea_id" "$planning_work_dir" "$discovery_dir" "$research_dir"; then
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

    # Phase P4b: Persona Walkthrough
    log_phase "P4b. PERSONA WALKTHROUGH"
    if ! run_p4b_persona_walkthrough "$idea_id" "$planning_work_dir"; then
        log_error "P4b failed"
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
| P4b | p4b-persona-walkthrough.md | Persona journey validation |
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
