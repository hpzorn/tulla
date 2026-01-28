#!/bin/bash
# discovery-ralph.sh - Product Discovery Ralph: Context and Value Assessment Loop
#
# Complements research-ralph by providing product/business context:
# - Research-Ralph: "How to build it" (technical deep-dives, PRDs, prototypes)
# - Discovery-Ralph: "What to build & why" (personas, value, integration)
#
# Discovery Protocol Phases:
#   D1: Inventory         (15 min) - What exists? Current state audit
#   D2: Persona Discovery (20 min) - Who uses this? Jobs-to-be-done
#   D3: Value Mapping     (20 min) - Business value, strategic fit, ROI
#   D4: Gap Analysis      (15 min) - What's missing? Prioritize opportunities
#   D5: Integration       (20 min) - Route to research OR integrate research outputs
#
# Modes:
#   --upstream   : Pre-research discovery → spawns research ideas
#   --downstream : Post-research integration → product contextualization
#   (default)    : Auto-detect based on idea lifecycle state
#
# Usage: ./discovery-ralph.sh [--upstream|--downstream] [--idea IDEA_ID] [--once] [--dry-run]
#
# Reference: Complements research-ralph.sh

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/discovery-ralph.conf"

# Load config if exists
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
fi

# Defaults (can be overridden in config)
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/work}"
SLEEP_INTERVAL="${SLEEP_INTERVAL:-3600}"
DRY_RUN="${DRY_RUN:-false}"
SINGLE_RUN="${SINGLE_RUN:-false}"
SPECIFIC_IDEA="${SPECIFIC_IDEA:-}"
INTERACTIVE="${INTERACTIVE:-false}"
MODE="${MODE:-auto}"  # upstream, downstream, or auto

# Budget Control
MAX_BUDGET_USD="${MAX_BUDGET_USD:-5.00}"

# Discovery Protocol Time Boxes (in minutes)
D1_INVENTORY_MINUTES="${D1_INVENTORY_MINUTES:-15}"
D2_PERSONA_MINUTES="${D2_PERSONA_MINUTES:-20}"
D3_VALUE_MINUTES="${D3_VALUE_MINUTES:-20}"
D4_GAP_MINUTES="${D4_GAP_MINUTES:-15}"
D5_INTEGRATION_MINUTES="${D5_INTEGRATION_MINUTES:-20}"

# =============================================================================
# Argument Parsing
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --upstream)
            MODE="upstream"
            shift
            ;;
        --downstream)
            MODE="downstream"
            shift
            ;;
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
            echo "Usage: $0 [--upstream|--downstream] [--idea IDEA_ID] [--once] [--dry-run] [--interactive]"
            echo ""
            echo "Modes:"
            echo "  --upstream     Pre-research: discover what needs researching"
            echo "  --downstream   Post-research: integrate research into product context"
            echo "  (default)      Auto-detect based on idea lifecycle"
            echo ""
            echo "Options:"
            echo "  --idea ID        Process a specific idea"
            echo "  --once           Run once and exit"
            echo "  --dry-run        Show what would be done"
            echo "  --interactive    Pause between phases for review"
            echo "  --max-budget USD Max API cost per call (default: 5.00)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# =============================================================================
# Logging
# =============================================================================

LOG_FILE="${WORK_DIR}/discovery-ralph.log"

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
        read -rp "[INTERACTIVE] Phase '$phase' complete. Press Enter to continue... " </dev/tty
    fi
}

# =============================================================================
# Setup
# =============================================================================

setup() {
    mkdir -p "$WORK_DIR"
    touch "$LOG_FILE"
    log_info "Discovery-Ralph starting..."
    log_info "Mode: $MODE"
    log_info "Work directory: $WORK_DIR"
    log_info "Dry run: $DRY_RUN"
}

# =============================================================================
# Helper: Timeout Command
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
# Idea Selection
# =============================================================================

extract_idea() {
    log_phase "0. EXTRACT - Selecting idea for discovery"

    if [[ -n "$SPECIFIC_IDEA" ]]; then
        log_info "Using specified idea: $SPECIFIC_IDEA"
        echo "$SPECIFIC_IDEA"
        return 0
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would query for ideas"
        echo "DRY_RUN_IDEA"
        return 0
    fi

    local lifecycle_filter
    if [[ "$MODE" == "upstream" ]]; then
        lifecycle_filter="sprout OR seed"
    elif [[ "$MODE" == "downstream" ]]; then
        lifecycle_filter="researched OR completed"
    else
        lifecycle_filter="sprout OR seed OR researched"
    fi

    local idea
    idea=$(claude --print "
Use mcp__idea-pool__list_ideas to see available ideas.

For Discovery-Ralph, look for ideas with lifecycle: ${lifecycle_filter}

Prioritize:
1. Ideas without existing discovery analysis (no d1-inventory.md in work dir)
2. Recently created or updated ideas
3. Ideas that seem to have product/business potential

Return ONLY the idea number (e.g., '29'), nothing else.
If no suitable ideas found, return 'NONE'.
" 2>/dev/null || echo "ERROR")

    idea=$(echo "$idea" | tr -d '[:space:]')

    if [[ "$idea" == "NONE" ]] || [[ "$idea" == "ERROR" ]] || [[ -z "$idea" ]]; then
        log_warn "No suitable ideas found for discovery"
        return 1
    fi

    log_info "Selected idea: $idea"
    echo "$idea"
}

# =============================================================================
# Mode Detection
# =============================================================================

detect_mode() {
    local idea_id="$1"

    if [[ "$MODE" != "auto" ]]; then
        echo "$MODE"
        return 0
    fi

    # Auto-detect based on lifecycle
    local lifecycle
    lifecycle=$(claude --print "
Use mcp__idea-pool__read_idea with identifier '$idea_id'.
Return ONLY the lifecycle state (e.g., 'sprout', 'researched', 'completed').
" 2>/dev/null || echo "unknown")

    lifecycle=$(echo "$lifecycle" | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')

    case "$lifecycle" in
        seed|sprout|backlog)
            echo "upstream"
            ;;
        researched|scoped|implementing|completed)
            echo "downstream"
            ;;
        *)
            echo "upstream"  # Default
            ;;
    esac
}

# =============================================================================
# D1: Inventory - What Exists?
# =============================================================================

run_d1_inventory() {
    local idea_id="$1"
    local work_dir="$2"
    local output_file="$work_dir/d1-inventory.md"

    log_info "D1: Inventory (${D1_INVENTORY_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run inventory"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$D1_INVENTORY_MINUTES")
    local discovery_date
    discovery_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,mcp__idea-pool__list_ideas,mcp__idea-pool__find_related_ideas,mcp__idea-pool__semantic_search,Read,Write,Glob,Grep" \
        -p "You are conducting Phase D1: Inventory for idea ${idea_id}.

## Goal
Audit what currently exists related to this idea - in the codebase, idea pool, and ecosystem.

## Instructions

1. Read the idea: mcp__idea-pool__read_idea with identifier ${idea_id}

2. Search for related work:
   - Use mcp__idea-pool__find_related_ideas to find connected ideas
   - Use mcp__idea-pool__semantic_search with key concepts
   - Use Glob/Grep to find related code/files in the codebase

3. Catalog existing components:
   - What tools/systems already exist that touch this domain?
   - What ideas in the pool are related?
   - What prior work has been done?

4. Write findings to: ${output_file}

   Structure:

   # D1: Inventory
   **Idea**: ${idea_id}
   **Date**: ${discovery_date}
   **Time-box**: ${D1_INVENTORY_MINUTES} minutes

   ## The Idea
   [Brief summary of idea ${idea_id}]

   ## Related Ideas in Pool
   | ID | Title | Lifecycle | Relationship |
   |----|-------|-----------|--------------|
   | ... | ... | ... | builds-on/complements/conflicts |

   ## Existing Systems & Tools
   | Component | Location | Relevance |
   |-----------|----------|-----------|
   | ... | ... | ... |

   ## Prior Work
   [What has already been done in this space]

   ## Current Gaps
   [What's clearly missing that this idea would address]

   ## Ecosystem Context
   [How this fits into the broader system/project]

Be thorough - good discovery starts with knowing what exists." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "D1 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "D1-inventory"
    return 0
}

# =============================================================================
# D2: Persona Discovery - Who Uses This?
# =============================================================================

run_d2_personas() {
    local idea_id="$1"
    local work_dir="$2"
    local output_file="$work_dir/d2-personas.md"
    local d1_file="$work_dir/d1-inventory.md"

    log_info "D2: Persona Discovery (${D2_PERSONA_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run persona discovery"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$D2_PERSONA_MINUTES")
    local discovery_date
    discovery_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write,WebSearch" \
        -p "You are conducting Phase D2: Persona Discovery for idea ${idea_id}.

## Goal
Identify who would use this, their jobs-to-be-done, and their pain points.

## Context
- Read the idea: mcp__idea-pool__read_idea with identifier ${idea_id}
- Read inventory: ${d1_file}

## Instructions

1. Identify 2-4 distinct user personas who would benefit from this idea
2. For each persona, map their:
   - Jobs-to-be-done (JTBD framework)
   - Current pain points
   - Desired outcomes
   - Context of use

3. Write to: ${output_file}

   Structure:

   # D2: Persona Discovery
   **Idea**: ${idea_id}
   **Date**: ${discovery_date}
   **Time-box**: ${D2_PERSONA_MINUTES} minutes

   ## Persona Overview
   | Persona | Role | Primary JTBD | Frequency |
   |---------|------|--------------|-----------|
   | ... | ... | ... | Daily/Weekly/Occasional |

   ## Detailed Personas

   ### Persona 1: [Name - e.g., \"Data-Driven Developer\"]

   **Who they are**:
   [Brief description - role, experience level, context]

   **Jobs-to-be-done**:
   - **Functional**: [What task are they trying to accomplish?]
   - **Emotional**: [How do they want to feel?]
   - **Social**: [How do they want to be perceived?]

   **Current workflow**:
   [How do they accomplish this today?]

   **Pain points**:
   1. [Pain point 1]
   2. [Pain point 2]
   3. [Pain point 3]

   **Desired outcomes**:
   - [Outcome 1]
   - [Outcome 2]

   **Success metrics** (how they'd measure value):
   - [Metric 1]
   - [Metric 2]

   ### Persona 2: [Name]
   [Same structure...]

   ## Cross-Persona Insights

   **Common pain points**:
   - [Shared pain]

   **Conflicting needs**:
   - [Where personas disagree]

   **Priority ranking**:
   1. [Primary persona] - [why they're primary]
   2. [Secondary persona] - [why]

   ## JTBD Summary
   When I am [situation], I want to [motivation], so I can [outcome].

Think like a product manager. Focus on real user needs, not features." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "D2 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "D2-personas"
    return 0
}

# =============================================================================
# D3: Value Mapping - Business Value & Strategic Fit
# =============================================================================

run_d3_value_mapping() {
    local idea_id="$1"
    local work_dir="$2"
    local output_file="$work_dir/d3-value-mapping.md"
    local d1_file="$work_dir/d1-inventory.md"
    local d2_file="$work_dir/d2-personas.md"

    log_info "D3: Value Mapping (${D3_VALUE_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run value mapping"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$D3_VALUE_MINUTES")
    local discovery_date
    discovery_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write" \
        -p "You are conducting Phase D3: Value Mapping for idea ${idea_id}.

## Goal
Assess business value, strategic fit, and ROI potential.

## Context
- Read the idea: mcp__idea-pool__read_idea with identifier ${idea_id}
- Read inventory: ${d1_file}
- Read personas: ${d2_file}

## Instructions

1. Assess the idea against multiple value dimensions
2. Consider strategic fit with existing systems/goals
3. Estimate effort vs. impact

Write to: ${output_file}

Structure:

# D3: Value Mapping
**Idea**: ${idea_id}
**Date**: ${discovery_date}
**Time-box**: ${D3_VALUE_MINUTES} minutes

## Value Dimensions

### User Value
| Dimension | Rating (1-5) | Evidence |
|-----------|--------------|----------|
| Pain reduction | ... | From D2: [specific pain] |
| Time savings | ... | ... |
| Quality improvement | ... | ... |
| New capability | ... | ... |

**User value score**: X/20

### Business Value
| Dimension | Rating (1-5) | Rationale |
|-----------|--------------|-----------|
| Revenue potential | ... | ... |
| Cost reduction | ... | ... |
| Competitive advantage | ... | ... |
| Strategic alignment | ... | ... |

**Business value score**: X/20

### Technical Value
| Dimension | Rating (1-5) | Rationale |
|-----------|--------------|-----------|
| Reusability | ... | ... |
| Technical debt reduction | ... | ... |
| Platform enhancement | ... | ... |
| Learning/capability building | ... | ... |

**Technical value score**: X/20

## Effort vs. Impact Matrix

**Estimated Effort**: [Low/Medium/High]
- Complexity: [description]
- Dependencies: [list]
- Skills required: [list]

**Estimated Impact**: [Low/Medium/High]
- Reach: [how many users/use cases]
- Frequency: [how often used]
- Criticality: [nice-to-have vs must-have]

**Quadrant**: [Quick Win / Major Project / Fill-in / Thankless Task]

## Strategic Fit

**Alignment with existing systems**:
- [System 1]: [how it fits]
- [System 2]: [how it fits]

**Synergies**:
- [Synergy 1]
- [Synergy 2]

**Risks to strategic goals**:
- [Risk 1]

## ROI Assessment

**Investment required**:
- Research: [Low/Med/High]
- Implementation: [Low/Med/High]
- Maintenance: [Low/Med/High]

**Expected returns**:
- Short-term (1-3 months): [description]
- Medium-term (3-12 months): [description]
- Long-term (1+ year): [description]

**ROI verdict**: [Strong / Moderate / Weak / Negative]

## Value Summary

**Total value score**: X/60
**Priority recommendation**: [P0-Critical / P1-High / P2-Medium / P3-Low]
**Confidence**: [High/Medium/Low]

Think like a product strategist. Be honest about value and effort." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "D3 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "D3-value-mapping"
    return 0
}

# =============================================================================
# D4: Gap Analysis - What's Missing?
# =============================================================================

run_d4_gap_analysis() {
    local idea_id="$1"
    local work_dir="$2"
    local output_file="$work_dir/d4-gap-analysis.md"

    log_info "D4: Gap Analysis (${D4_GAP_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run gap analysis"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$D4_GAP_MINUTES")
    local discovery_date
    discovery_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write" \
        -p "You are conducting Phase D4: Gap Analysis for idea ${idea_id}.

## Goal
Identify what's missing to move this idea forward and prioritize opportunities.

## Context
Read all previous discovery phases:
- ${work_dir}/d1-inventory.md
- ${work_dir}/d2-personas.md
- ${work_dir}/d3-value-mapping.md

## Instructions

1. Identify all gaps between current state and desired state
2. Categorize gaps by type
3. Prioritize based on value mapping

Write to: ${output_file}

Structure:

# D4: Gap Analysis
**Idea**: ${idea_id}
**Date**: ${discovery_date}
**Time-box**: ${D4_GAP_MINUTES} minutes

## Gap Categories

### Knowledge Gaps
[What we don't know yet - candidates for research-ralph]
| Gap | Impact | Research Question |
|-----|--------|-------------------|
| ... | High/Med/Low | \"How does X work?\" |

### Technical Gaps
[What doesn't exist technically]
| Gap | Blocks | Solution Approach |
|-----|--------|-------------------|
| ... | [what it blocks] | Build/Buy/Integrate |

### Resource Gaps
[What resources are missing]
| Gap | Type | Mitigation |
|-----|------|------------|
| ... | Skills/Time/Tools/Budget | ... |

### Integration Gaps
[How this connects to existing systems]
| Gap | Systems Involved | Complexity |
|-----|------------------|------------|
| ... | ... | High/Med/Low |

## Priority Matrix

| Gap | Value Impact | Effort to Close | Priority |
|-----|--------------|-----------------|----------|
| ... | High/Med/Low | High/Med/Low | P0/P1/P2/P3 |

## Research Questions Identified
[Questions that need research-ralph investigation]

1. **RQ**: [Question]
   **Why it matters**: [Impact on idea]
   **Suggested approach**: [Empirical/Theoretical/Engineering]

2. **RQ**: [Question]
   ...

## Blockers
[Critical gaps that must be resolved first]

1. [Blocker 1]: [why it's critical]
2. [Blocker 2]: [why it's critical]

## Opportunities
[Gaps that, if closed, would create outsized value]

1. [Opportunity 1]: [potential impact]
2. [Opportunity 2]: [potential impact]

## Recommended Next Steps

### If proceeding to research (upstream):
1. [Step 1]
2. [Step 2]

### If integrating research (downstream):
1. [Step 1]
2. [Step 2]

Be specific about gaps - vague gaps can't be closed." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "D4 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "D4-gap-analysis"
    return 0
}

# =============================================================================
# D5: Integration - Route to Research OR Integrate Research Outputs
# =============================================================================

run_d5_integration_upstream() {
    local idea_id="$1"
    local work_dir="$2"
    local output_file="$work_dir/d5-research-brief.md"

    log_info "D5: Integration (UPSTREAM - Creating Research Brief)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create research brief"
        echo "research"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$D5_INTEGRATION_MINUTES")
    local discovery_date
    discovery_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,mcp__idea-pool__append_to_idea,mcp__idea-pool__capture_seed,Read,Write" \
        -p "You are conducting Phase D5: Integration (UPSTREAM) for idea ${idea_id}.

## Goal
Create a research brief for research-ralph, informed by product discovery.

## Context
Read all discovery phases:
- ${work_dir}/d1-inventory.md
- ${work_dir}/d2-personas.md
- ${work_dir}/d3-value-mapping.md
- ${work_dir}/d4-gap-analysis.md

## Instructions

1. Synthesize discovery findings into a research brief
2. Prioritize research questions based on business value
3. Create research seeds if needed

Write to: ${output_file}

Structure:

# D5: Research Brief
**Idea**: ${idea_id}
**Date**: ${discovery_date}
**Mode**: Upstream (Discovery → Research)

## Discovery Summary

### What We Learned
- **Users**: [Primary persona and their core need]
- **Value**: [Key value proposition]
- **Gaps**: [Critical gaps identified]

### Priority Score
From D3 value mapping: [X/60] - [P0/P1/P2/P3]

## Research Questions (Prioritized by Value)

### High Priority (Must answer before implementation)
1. **RQ**: [Question from D4]
   **Business rationale**: [Why this matters to users/business]
   **Success criteria**: [What a good answer looks like]

### Medium Priority (Would improve implementation)
2. **RQ**: [Question]
   ...

### Low Priority (Nice to know)
3. **RQ**: [Question]
   ...

## Constraints for Research
[From discovery - what research must respect]

- **User constraints**: [From D2]
- **Technical constraints**: [From D1]
- **Business constraints**: [From D3]

## Success Definition
Research is successful if it answers:
1. [Key question 1]
2. [Key question 2]

And enables:
- [User outcome from D2]
- [Business outcome from D3]

## Handoff to Research-Ralph

**Recommended lifecycle transition**: sprout → backlog (ready for research)

**Research-ralph invocation**:
\`\`\`
./research-ralph.sh --idea ${idea_id}
\`\`\`

---

After writing, append a discovery summary to the idea using mcp__idea-pool__append_to_idea.

Output the word 'research' on the final line to indicate handoff to research-ralph." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "D5 did not produce $output_file"
        return 1
    fi

    # Extract recommendation
    local recommendation
    recommendation=$(tail -3 "$output_file" | grep -iE '^(research|implement|park)' | head -1 | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

    pause_if_interactive "D5-research-brief"
    echo "${recommendation:-research}"
}

run_d5_integration_downstream() {
    local idea_id="$1"
    local work_dir="$2"
    local output_file="$work_dir/d5-product-spec.md"

    log_info "D5: Integration (DOWNSTREAM - Creating Product Spec)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create product spec"
        echo "implement"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$D5_INTEGRATION_MINUTES")
    local discovery_date
    discovery_date=$(date +%Y-%m-%d)

    # Find research artifacts if they exist
    local research_dir
    research_dir=$(find "$WORK_DIR" -type d -name "idea-${idea_id}-*" | sort -r | head -1)

    $timeout_cmd claude \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,mcp__idea-pool__append_to_idea,Read,Write,Glob" \
        -p "You are conducting Phase D5: Integration (DOWNSTREAM) for idea ${idea_id}.

## Goal
Integrate research findings with product discovery to create an actionable product spec.

## Context
Read all discovery phases:
- ${work_dir}/d1-inventory.md
- ${work_dir}/d2-personas.md
- ${work_dir}/d3-value-mapping.md
- ${work_dir}/d4-gap-analysis.md

Also look for research artifacts:
- Research directory (if exists): ${research_dir}
- Look for: r6-research-synthesis.md, prd.md

## Instructions

Create a product specification that bridges research findings with user needs.

Write to: ${output_file}

Structure:

# D5: Product Specification
**Idea**: ${idea_id}
**Date**: ${discovery_date}
**Mode**: Downstream (Research → Product)

## Executive Summary
[2-3 sentences: what, for whom, why now]

## User Story
As a [persona from D2],
I want to [capability],
So that [outcome/benefit from D3].

## Research Foundation
[Summary of key research findings that inform this spec]

### What Research Validated
- [Finding 1]
- [Finding 2]

### What Research Changed
- [Original assumption] → [Revised understanding]

## Product Requirements

### Must Have (P0)
- [ ] [Requirement tied to primary persona need]
- [ ] [Requirement tied to core value proposition]

### Should Have (P1)
- [ ] [Requirement]

### Nice to Have (P2)
- [ ] [Requirement]

## User Experience

### Primary Flow
1. User [action]
2. System [response]
3. User [action]
...

### Edge Cases
- [Edge case 1]: [handling]

## Success Metrics
[From D2 persona success metrics + D3 value metrics]

| Metric | Target | Measurement |
|--------|--------|-------------|
| ... | ... | ... |

## Integration Points
[From D1 inventory - how this connects]

| System | Integration | Complexity |
|--------|-------------|------------|
| ... | ... | ... |

## Launch Plan

### Phase 1: MVP
- [Scope]
- [Success criteria]

### Phase 2: Iteration
- [Scope]

## Open Questions
[Questions that can be resolved during implementation]

---

After writing, append product spec summary to idea using mcp__idea-pool__append_to_idea.

Output 'implement' on the final line if ready for implementation, or 'research' if more research needed." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "D5 did not produce $output_file"
        return 1
    fi

    local recommendation
    recommendation=$(tail -3 "$output_file" | grep -iE '^(research|implement|park)' | head -1 | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

    pause_if_interactive "D5-product-spec"
    echo "${recommendation:-implement}"
}

# =============================================================================
# Main Discovery Protocol
# =============================================================================

run_discovery_protocol() {
    local idea_id="$1"
    local work_dir="$2"
    local mode="$3"

    log_phase "DISCOVERY PROTOCOL - Product Context Assessment"
    log_info "Mode: $mode"
    log_info "Total estimated time: ~$((D1_INVENTORY_MINUTES + D2_PERSONA_MINUTES + D3_VALUE_MINUTES + D4_GAP_MINUTES + D5_INTEGRATION_MINUTES)) minutes"

    # D1: Inventory
    if ! run_d1_inventory "$idea_id" "$work_dir"; then
        log_error "D1 failed"
        return 1
    fi

    # D2: Personas
    if ! run_d2_personas "$idea_id" "$work_dir"; then
        log_error "D2 failed"
        return 1
    fi

    # D3: Value Mapping
    if ! run_d3_value_mapping "$idea_id" "$work_dir"; then
        log_error "D3 failed"
        return 1
    fi

    # D4: Gap Analysis
    if ! run_d4_gap_analysis "$idea_id" "$work_dir"; then
        log_error "D4 failed"
        return 1
    fi

    # D5: Integration (mode-dependent)
    local recommendation
    if [[ "$mode" == "upstream" ]]; then
        recommendation=$(run_d5_integration_upstream "$idea_id" "$work_dir")
    else
        recommendation=$(run_d5_integration_downstream "$idea_id" "$work_dir")
    fi

    log_info "Discovery complete. Recommendation: $recommendation"
    echo "$recommendation"
}

# =============================================================================
# Process Idea
# =============================================================================

process_idea() {
    local idea_id="$1"

    # Create work directory
    local work_dir="$WORK_DIR/discovery-$idea_id-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$work_dir"

    log_info "Processing idea: $idea_id"
    log_info "Work directory: $work_dir"

    # Detect mode if auto
    local actual_mode
    actual_mode=$(detect_mode "$idea_id")
    log_info "Detected mode: $actual_mode"

    # Run discovery protocol
    local recommendation
    if ! recommendation=$(run_discovery_protocol "$idea_id" "$work_dir" "$actual_mode"); then
        log_error "Discovery protocol failed"
        return 1
    fi

    # Log completion
    log_info "Discovery complete for idea $idea_id"
    log_info "Recommendation: $recommendation"
    log_info "Artifacts in: $work_dir"

    # Suggest next steps
    case "$recommendation" in
        research)
            log_info "Next: ./research-ralph.sh --idea $idea_id"
            ;;
        implement)
            log_info "Next: Ready for implementation"
            ;;
        park)
            log_info "Next: Human decision required"
            ;;
    esac

    return 0
}

# =============================================================================
# Main Loop
# =============================================================================

main() {
    setup

    while true; do
        local idea_id
        if ! idea_id=$(extract_idea); then
            if [[ "$SINGLE_RUN" == "true" ]]; then
                log_info "No ideas to process. Exiting (--once mode)."
                exit 0
            fi
            log_info "No ideas available. Sleeping for ${SLEEP_INTERVAL}s..."
            sleep "$SLEEP_INTERVAL"
            continue
        fi

        if process_idea "$idea_id"; then
            log_info "Idea $idea_id discovery complete!"
        else
            log_warn "Idea $idea_id discovery stopped"
        fi

        if [[ "$SINGLE_RUN" == "true" ]]; then
            log_info "Single run complete. Exiting."
            exit 0
        fi

        log_info "Continuing to next idea..."
        sleep 5
    done
}

# =============================================================================
# Entry Point
# =============================================================================

main "$@"
