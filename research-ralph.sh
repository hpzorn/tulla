#!/bin/bash
# research-ralph.sh - Research-First Ralph: Autonomous Idea-to-Implementation Loop
#
# Extends Geoffrey Huntley's Ralph Wiggum loop with:
# - Mandatory research phase before implementation
# - Idea pool integration for continuous multi-task processing
# - PRD-driven implementation
# - Decomposition of large ideas into sub-ideas
# - Dependency tracking and blocking detection
# - Status tracking and completion marking
#
# Lifecycle: backlog → researching → researched → [decomposing] → scoped → implementing → completed
#            With branches to: invalidated, parked, blocked, failed
#
# Usage: ./research-ralph.sh [--once] [--dry-run] [--idea IDEA_ID] [--interactive]
#
# Reference: https://ghuntley.com/ralph/

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="${SCRIPT_DIR}/research-ralph.conf"

# Load config if exists
if [[ -f "$CONFIG_FILE" ]]; then
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
fi

# Defaults (can be overridden in config)
IDEA_POOL_DIR="${IDEA_POOL_DIR:-$HOME/ideas}"
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/work}"
SLEEP_INTERVAL="${SLEEP_INTERVAL:-3600}"
MAX_IMPLEMENTATION_RETRIES="${MAX_IMPLEMENTATION_RETRIES:-3}"
RESEARCH_TIME_BOX_MINUTES="${RESEARCH_TIME_BOX_MINUTES:-30}"
DRY_RUN="${DRY_RUN:-false}"
SINGLE_RUN="${SINGLE_RUN:-false}"
SPECIFIC_IDEA="${SPECIFIC_IDEA:-}"
INTERACTIVE="${INTERACTIVE:-false}"

# Decomposition thresholds
MAX_SUCCESS_CRITERIA="${MAX_SUCCESS_CRITERIA:-5}"
MAX_INDEPENDENT_COMPONENTS="${MAX_INDEPENDENT_COMPONENTS:-3}"

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
        --help|-h)
            echo "Usage: $0 [--once] [--dry-run] [--idea IDEA_ID] [--interactive]"
            echo ""
            echo "Options:"
            echo "  --once        Run once and exit (don't loop)"
            echo "  --dry-run     Show what would be done without executing"
            echo "  --idea ID     Process a specific idea by number or pattern"
            echo "  --interactive Pause for human review between phases"
            echo "  --help        Show this help message"
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

LOG_FILE="${WORK_DIR}/research-ralph.log"

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
log_state() { log "STATE" "$@"; }
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
    log_info "Research-First Ralph starting..."
    log_info "Work directory: $WORK_DIR"
    log_info "Dry run: $DRY_RUN"
    log_info "Single run: $SINGLE_RUN"
    log_info "Interactive: $INTERACTIVE"
}

# =============================================================================
# MCP Tool Wrappers
# =============================================================================

# Set lifecycle state with logging
set_lifecycle() {
    local idea_id="$1"
    local new_state="$2"
    local reason="${3:-}"

    log_state "Transitioning idea $idea_id to '$new_state'" ${reason:+"(reason: $reason)"}

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would set lifecycle: $idea_id → $new_state"
        return 0
    fi

    claude --print "
Use mcp__idea-pool__set_lifecycle to change idea '$idea_id' to state '$new_state'.
${reason:+Reason: $reason}
Return only 'OK' or 'ERROR'.
" 2>/dev/null || echo "ERROR"
}

# =============================================================================
# Phase 1: Extract (Idea Selection)
# =============================================================================

extract_idea() {
    log_phase "1. EXTRACT - Selecting next workable idea"

    if [[ "$DRY_RUN" == "true" ]]; then
        if [[ -n "$SPECIFIC_IDEA" ]]; then
            log_info "[DRY RUN] Would process specific idea: $SPECIFIC_IDEA"
            echo "$SPECIFIC_IDEA"
        else
            log_info "[DRY RUN] Would query for workable ideas"
            echo "DRY_RUN_IDEA"
        fi
        return 0
    fi

    local idea
    if [[ -n "$SPECIFIC_IDEA" ]]; then
        idea="$SPECIFIC_IDEA"
        log_info "Using specified idea: $idea"
    else
        # Use the new get_workable_ideas tool
        idea=$(claude --print "
Use mcp__idea-pool__get_workable_ideas to find ideas ready for processing.
These are ideas in 'backlog' state that are not blocked by dependencies.

Return ONLY the identifier (number) of the first/highest priority idea.
If no workable ideas are found, return exactly 'NONE'.
" 2>/dev/null || echo "ERROR")
    fi

    # Clean up the response
    idea=$(echo "$idea" | tr -d '[:space:]')

    if [[ "$idea" == "NONE" ]] || [[ "$idea" == "ERROR" ]] || [[ -z "$idea" ]]; then
        log_warn "No workable ideas found in pool"
        return 1
    fi

    log_info "Selected idea: $idea"
    echo "$idea"
}

# =============================================================================
# Phase 2: Research (Mandatory Academic Groundwork)
# =============================================================================

run_research() {
    local idea_id="$1"
    local idea_work_dir="$2"

    log_phase "2. RESEARCH - Mandatory groundwork for idea $idea_id"

    # Transition to researching state
    set_lifecycle "$idea_id" "researching" "Starting research phase"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would research idea $idea_id"
        echo "proceed"
        return 0
    fi

    log_info "Starting research phase (time-boxed to ${RESEARCH_TIME_BOX_MINUTES} minutes)..."

    # Run research and get outcome
    local outcome
    outcome=$(timeout "${RESEARCH_TIME_BOX_MINUTES}m" claude --print "
You are conducting research for implementing an idea. This is a MANDATORY research phase.

## Instructions

1. First, use mcp__idea-pool__read_idea('$idea_id') to read the full idea content
2. Research the idea thoroughly:
   - Search for prior art (existing implementations, tools, solutions)
   - Look for academic papers or blog posts on the topic
   - Identify theoretical foundations and key concepts
   - Document failure modes and pitfalls to avoid
3. Write your research findings using mcp__idea-pool__append_to_idea('$idea_id', content)
   Add a section like:

   ## Research Notes ($(date +%Y-%m-%d))

   ### Prior Art
   [What already exists]

   ### Theoretical Foundations
   [Key concepts and principles]

   ### Pitfalls to Avoid
   [What has failed or could go wrong]

   ### Key Insights
   [Most important findings]

4. Determine the outcome based on your research:
   - 'proceed' - Novel and feasible, ready to continue
   - 'invalidate' - Already solved elsewhere or fundamentally flawed
   - 'park' - Needs human decision or input before continuing

## Output
Return ONLY one word: proceed, invalidate, or park
" 2>/dev/null || echo "error")

    # Clean up outcome
    outcome=$(echo "$outcome" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

    log_info "Research outcome: $outcome"

    case "$outcome" in
        proceed)
            set_lifecycle "$idea_id" "researched" "Research complete, ready for scoping"
            pause_if_interactive "research"
            return 0
            ;;
        invalidate)
            set_lifecycle "$idea_id" "invalidated" "Research found this is not viable"
            log_warn "Idea $idea_id invalidated during research"
            return 1
            ;;
        park)
            set_lifecycle "$idea_id" "parked" "Needs human input"
            log_warn "Idea $idea_id parked - needs human decision"
            return 1
            ;;
        *)
            log_error "Research phase returned unexpected outcome: $outcome"
            set_lifecycle "$idea_id" "parked" "Research phase error"
            return 1
            ;;
    esac
}

# =============================================================================
# Phase 3: Decomposition Check
# =============================================================================

check_decomposition() {
    local idea_id="$1"

    log_phase "3. DECOMPOSITION CHECK - Evaluating idea complexity"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would check if idea needs decomposition"
        echo "atomic"
        return 0
    fi

    local result
    result=$(claude --print "
Read idea '$idea_id' with mcp__idea-pool__read_idea and analyze its complexity.

Decomposition criteria:
- More than $MAX_SUCCESS_CRITERIA success criteria needed
- More than $MAX_INDEPENDENT_COMPONENTS independent components
- Multiple distinct deliverables that could be built separately

If decomposition is needed:
1. Use mcp__idea-pool__create_sub_idea for each component:
   - parent_identifier='$idea_id'
   - title='[Component name]'
   - content='## Goal\n[What this sub-idea accomplishes]\n\n## Context\nPart of parent idea $idea_id'
   - auto_number=true

2. Use mcp__idea-pool__add_dependency if sub-ideas have ordering requirements

3. Return 'decomposed'

If the idea is atomic (can be implemented as-is):
- Return 'atomic'

Return ONLY: decomposed or atomic
" 2>/dev/null || echo "atomic")

    result=$(echo "$result" | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
    log_info "Decomposition result: $result"

    if [[ "$result" == "decomposed" ]]; then
        set_lifecycle "$idea_id" "decomposing" "Spawning sub-ideas"
        log_info "Idea decomposed into sub-ideas. Parent will complete when children complete."
        return 1  # Don't continue with this idea, process children instead
    fi

    pause_if_interactive "decomposition"
    return 0  # Continue with atomic idea
}

# =============================================================================
# Phase 4: PRD Creation
# =============================================================================

create_prd() {
    local idea_id="$1"

    log_phase "4. PRD - Creating Product Requirements Document"

    set_lifecycle "$idea_id" "scoped" "Creating PRD"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create PRD for idea $idea_id"
        return 0
    fi

    claude "
Create a PRD for idea '$idea_id'.

## Instructions

1. Read the idea and research notes with mcp__idea-pool__read_idea('$idea_id')

2. Append a PRD section using mcp__idea-pool__append_to_idea('$idea_id', content):

## PRD ($(date +%Y-%m-%d))

### Problem Statement
[Clear description from the idea]

### Research Summary
[Key findings - prior art, foundations, pitfalls]

### Proposed Solution
[High-level approach]

### Success Criteria
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
(Maximum $MAX_SUCCESS_CRITERIA for atomic ideas)

### Non-Goals
[What we're explicitly NOT doing]

### Technical Approach
[Implementation plan - architecture, components, tools]

### Risks & Mitigations
[Potential issues and how to handle them]

### Estimated Complexity
[S/M/L with justification]

Be specific and actionable. The implementation phase will execute this PRD.
" 2>&1 | tee -a "$LOG_FILE"

    log_info "PRD created for idea $idea_id"
    pause_if_interactive "prd"
    return 0
}

# =============================================================================
# Phase 5: Implementation (Classic Ralph)
# =============================================================================

run_implementation() {
    local idea_id="$1"

    log_phase "5. IMPLEMENT - Classic Ralph loop"

    set_lifecycle "$idea_id" "implementing" "Starting implementation"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run implementation loop"
        echo "COMPLETE"
        return 0
    fi

    local retries=0

    while [[ $retries -lt $MAX_IMPLEMENTATION_RETRIES ]]; do
        ((retries++))
        log_info "Implementation attempt $retries/$MAX_IMPLEMENTATION_RETRIES"

        local result
        result=$(claude --print "
Implement the PRD for idea '$idea_id'.

## Instructions

1. Read the idea with mcp__idea-pool__read_idea('$idea_id') to get the PRD and success criteria

2. Implement the solution:
   - Work through the technical approach
   - Create necessary files and code
   - Test your implementation

3. Check each success criterion and mark completed ones

4. Determine outcome:

   If ALL success criteria are met:
   - Update the idea to mark criteria as checked: [x]
   - Return 'COMPLETE'

   If you discover a blocking dependency:
   - Use mcp__idea-pool__create_sub_idea to capture the dependency
   - Use mcp__idea-pool__add_dependency to mark the block
   - Return 'BLOCKED: [description of what's blocking]'

   If stuck after good effort:
   - Return 'STUCK: [what went wrong]'

<promise>ALL_SUCCESS_CRITERIA_MET</promise>

Return ONLY one of:
- COMPLETE
- BLOCKED: [reason]
- STUCK: [reason]
" 2>/dev/null || echo "STUCK: Unknown error")

        log_info "Implementation result: $result"

        case "$result" in
            COMPLETE*)
                set_lifecycle "$idea_id" "completed" "All success criteria met"

                # Check if this completes a parent
                claude --print "
Use mcp__idea-pool__check_parent_completion('$idea_id') to see if completing this idea
allows a parent idea to also be marked complete.
" 2>/dev/null || true

                log_info "Idea $idea_id completed successfully!"
                return 0
                ;;
            BLOCKED*)
                local reason="${result#BLOCKED: }"
                set_lifecycle "$idea_id" "blocked" "$reason"
                log_warn "Idea $idea_id blocked: $reason"
                return 1
                ;;
            STUCK*)
                log_warn "Implementation stuck, retrying..."
                sleep 2
                ;;
            *)
                log_warn "Unexpected result, retrying..."
                sleep 2
                ;;
        esac
    done

    # Max retries exceeded
    set_lifecycle "$idea_id" "failed" "Max retries ($MAX_IMPLEMENTATION_RETRIES) exceeded"
    log_error "Idea $idea_id failed after $MAX_IMPLEMENTATION_RETRIES attempts"
    return 1
}

# =============================================================================
# Main Processing
# =============================================================================

process_idea() {
    local idea_id="$1"

    log_info "Processing idea: $idea_id"

    # Phase 2: Research (mandatory)
    if ! run_research "$idea_id" "$WORK_DIR"; then
        log_warn "Idea $idea_id stopped at research phase"
        return 1
    fi

    # Phase 3: Decomposition check
    if ! check_decomposition "$idea_id"; then
        log_info "Idea $idea_id decomposed - children added to backlog"
        return 0  # Success - children will be processed separately
    fi

    # Phase 4: PRD
    if ! create_prd "$idea_id"; then
        log_error "PRD creation failed for idea $idea_id"
        return 1
    fi

    # Phase 5: Implementation
    if ! run_implementation "$idea_id"; then
        log_warn "Implementation did not complete for idea $idea_id"
        return 1
    fi

    log_info "Successfully completed idea $idea_id"
    return 0
}

# =============================================================================
# Status Dashboard
# =============================================================================

show_status() {
    log_info "Fetching Ralph status dashboard..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would show status"
        return 0
    fi

    claude --print "
Use mcp__idea-pool__get_ralph_status() to get the current workflow status.
Display a summary of ideas in each lifecycle state.
" 2>/dev/null || log_warn "Could not fetch status"
}

# =============================================================================
# Main Loop
# =============================================================================

main() {
    setup
    show_status

    while true; do
        # Phase 1: Extract next workable idea
        local idea_id
        if ! idea_id=$(extract_idea); then
            if [[ "$SINGLE_RUN" == "true" ]]; then
                log_info "No ideas to process. Exiting (--once mode)."
                exit 0
            fi
            log_info "No workable ideas. Sleeping for ${SLEEP_INTERVAL}s..."
            sleep "$SLEEP_INTERVAL"
            continue
        fi

        # Process the idea through all phases
        if process_idea "$idea_id"; then
            log_info "Idea $idea_id processing complete!"
        else
            log_warn "Idea $idea_id processing stopped"
        fi

        # Show updated status
        show_status

        # Exit if single run mode
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
