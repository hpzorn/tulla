#!/bin/bash
# research-ralph.sh - Research-First Ralph: Autonomous Idea-to-Implementation Loop
#
# Extends Geoffrey Huntley's Ralph Wiggum loop with:
# - Mandatory research phase before implementation
# - Idea pool integration for continuous multi-task processing
# - PRD-driven implementation
# - Status tracking and completion marking
#
# Usage: ./research-ralph.sh [--once] [--dry-run] [--idea IDEA_ID]
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
MAX_IMPLEMENTATION_LOOPS="${MAX_IMPLEMENTATION_LOOPS:-10}"
RESEARCH_TIME_BOX_MINUTES="${RESEARCH_TIME_BOX_MINUTES:-30}"
DRY_RUN="${DRY_RUN:-false}"
SINGLE_RUN="${SINGLE_RUN:-false}"
SPECIFIC_IDEA="${SPECIFIC_IDEA:-}"

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
        --help|-h)
            echo "Usage: $0 [--once] [--dry-run] [--idea IDEA_ID]"
            echo ""
            echo "Options:"
            echo "  --once      Run once and exit (don't loop)"
            echo "  --dry-run   Show what would be done without executing"
            echo "  --idea ID   Process a specific idea by number or pattern"
            echo "  --help      Show this help message"
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
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() { log "INFO" "$@"; }
log_warn() { log "WARN" "$@"; }
log_error() { log "ERROR" "$@"; }
log_phase() {
    echo ""
    echo "============================================================"
    log "PHASE" "$@"
    echo "============================================================"
}

# =============================================================================
# Setup
# =============================================================================

setup() {
    mkdir -p "$WORK_DIR"
    touch "$LOG_FILE"
    log_info "Research-First Ralph starting..."
    log_info "Work directory: $WORK_DIR"
    log_info "Idea pool directory: $IDEA_POOL_DIR"
    log_info "Dry run: $DRY_RUN"
    log_info "Single run: $SINGLE_RUN"
}

# =============================================================================
# Phase 1: Extract (Idea Selection)
# =============================================================================

extract_idea() {
    log_phase "1. EXTRACT - Selecting next workable idea"

    local idea_query
    if [[ -n "$SPECIFIC_IDEA" ]]; then
        idea_query="Return the idea matching '$SPECIFIC_IDEA'"
    else
        idea_query="Find the next workable idea with lifecycle=sprout or lifecycle=growing that has a concrete problem statement"
    fi

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would query idea pool: $idea_query"
        echo "DRY_RUN_IDEA"
        return 0
    fi

    local idea
    idea=$(claude --print "
Use the idea-pool MCP tools to $idea_query.

Selection criteria:
- lifecycle: sprout or growing (ready for implementation)
- Has a concrete problem statement
- Prioritize by: novelty, simplicity (start with simpler ideas), recency

Return ONLY the idea identifier (number), nothing else. If no workable ideas found, return 'NONE'.
" 2>/dev/null || echo "ERROR")

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

    local research_file="$idea_work_dir/research-notes.md"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would research idea $idea_id"
        log_info "[DRY RUN] Would create $research_file"
        touch "$research_file"
        echo "# Research Notes (DRY RUN)" > "$research_file"
        return 0
    fi

    log_info "Starting research phase (time-boxed to ${RESEARCH_TIME_BOX_MINUTES} minutes)..."
    log_info "Output: $research_file"

    # Read the full idea content first
    local idea_content
    idea_content=$(claude --print "
Use mcp__idea-pool__read_idea to read idea '$idea_id' and return its full content.
" 2>/dev/null || echo "")

    if [[ -z "$idea_content" ]]; then
        log_error "Failed to read idea content"
        return 1
    fi

    # Save idea content for reference
    echo "$idea_content" > "$idea_work_dir/idea-source.md"

    # Run research
    timeout "${RESEARCH_TIME_BOX_MINUTES}m" claude "
You are conducting research for implementing an idea. This is a MANDATORY research phase.
You must NOT proceed to implementation - only research.

## The Idea
$idea_content

## Your Task
Research this idea thoroughly and create research notes. Focus on:

1. **Literature Review**: Search for academic papers, blog posts, and documentation related to this topic
2. **Prior Art**: What existing implementations, tools, or solutions already exist?
3. **Theoretical Foundations**: What concepts, patterns, or principles underpin this idea?
4. **Failure Modes**: What approaches have been tried and failed? What are common pitfalls?
5. **Key Insights**: What are the most important things to know before implementing?

## Output
Write your findings to: $research_file

Structure your notes with clear sections. Include links/references where possible.
Be thorough but concise. This research will inform the PRD and implementation.

IMPORTANT: Do NOT write any implementation code. Research only.
" 2>&1 | tee -a "$LOG_FILE" || {
        log_warn "Research phase timed out or failed"
    }

    if [[ ! -f "$research_file" ]]; then
        log_error "Research phase did not produce research-notes.md"
        return 1
    fi

    local research_size
    research_size=$(wc -c < "$research_file")
    if [[ "$research_size" -lt 100 ]]; then
        log_error "Research notes too short (${research_size} bytes) - research may have failed"
        return 1
    fi

    log_info "Research complete: $research_file (${research_size} bytes)"
    return 0
}

# =============================================================================
# Phase 3: PRD Creation
# =============================================================================

create_prd() {
    local idea_id="$1"
    local idea_work_dir="$2"

    log_phase "3. PRD - Creating Product Requirements Document"

    local prd_file="$idea_work_dir/prd.md"
    local research_file="$idea_work_dir/research-notes.md"
    local idea_file="$idea_work_dir/idea-source.md"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create PRD at $prd_file"
        cp "$SCRIPT_DIR/templates/prd-template.md" "$prd_file" 2>/dev/null || \
            echo "# PRD (DRY RUN)" > "$prd_file"
        return 0
    fi

    if [[ ! -f "$research_file" ]]; then
        log_error "Research notes not found - cannot create PRD"
        return 1
    fi

    log_info "Creating PRD based on idea and research..."

    local idea_content research_content
    idea_content=$(cat "$idea_file")
    research_content=$(cat "$research_file")

    claude "
You are creating a PRD (Product Requirements Document) for implementation.

## The Idea
$idea_content

## Research Notes
$research_content

## Your Task
Create a comprehensive PRD at: $prd_file

Use this structure:
\`\`\`markdown
# PRD: [Title]

## Problem Statement
[Clear description of the problem being solved]

## Research Summary
[Key findings from the research phase - prior art, theoretical foundations, pitfalls to avoid]

## Proposed Solution
[High-level description of the solution]

## Success Criteria
[Measurable criteria for when this is 'done']
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] ...

## Non-Goals
[What this implementation will NOT do]

## Technical Approach
[Detailed technical plan - architecture, components, algorithms, tools]

## Risks & Mitigations
[Potential issues and how to address them]

## Estimated Complexity
[S/M/L with brief justification]
\`\`\`

Be specific and actionable. The implementation phase will use this PRD directly.
" 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$prd_file" ]]; then
        log_error "PRD creation failed - file not created"
        return 1
    fi

    log_info "PRD created: $prd_file"
    return 0
}

# =============================================================================
# Phase 4: Implementation (Classic Ralph)
# =============================================================================

run_implementation() {
    local idea_id="$1"
    local idea_work_dir="$2"

    log_phase "4. IMPLEMENT - Classic Ralph loop"

    local prd_file="$idea_work_dir/prd.md"
    local done_file="$idea_work_dir/DONE"
    local loop_count=0

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run implementation loop with PRD"
        touch "$done_file"
        return 0
    fi

    if [[ ! -f "$prd_file" ]]; then
        log_error "PRD not found - cannot implement"
        return 1
    fi

    local prd_content
    prd_content=$(cat "$prd_file")

    log_info "Starting implementation loop (max $MAX_IMPLEMENTATION_LOOPS iterations)..."

    cd "$idea_work_dir"

    while [[ $loop_count -lt $MAX_IMPLEMENTATION_LOOPS ]]; do
        ((loop_count++))
        log_info "Implementation loop iteration $loop_count/$MAX_IMPLEMENTATION_LOOPS"

        claude "
## Implementation Task

You are implementing the following PRD. Work in the current directory: $idea_work_dir

$prd_content

## Instructions

1. Review the PRD and any existing implementation progress
2. Implement the next piece of functionality
3. Test your implementation
4. Update progress

## Completion

When ALL success criteria from the PRD are met:
1. Create a file named 'DONE' with a summary of what was implemented
2. List any follow-up tasks or improvements for later

<promise>ALL_PRD_ITEMS_COMPLETE</promise>
" 2>&1 | tee -a "$LOG_FILE"

        if [[ -f "$done_file" ]]; then
            log_info "Implementation complete! DONE file created."
            break
        fi

        log_info "DONE file not found, continuing loop..."
        sleep 2
    done

    cd "$SCRIPT_DIR"

    if [[ ! -f "$done_file" ]]; then
        log_warn "Implementation loop exhausted without completion"
        echo "Implementation incomplete after $MAX_IMPLEMENTATION_LOOPS iterations" > "$idea_work_dir/INCOMPLETE"
        return 1
    fi

    return 0
}

# =============================================================================
# Phase 5: Mark Complete
# =============================================================================

mark_complete() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local status="$3"  # implemented, tried, failed

    log_phase "5. COMPLETE - Updating idea status to '$status'"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would update idea $idea_id status to $status"
        return 0
    fi

    # Create completion record
    local completion_file="$idea_work_dir/completion-record.md"
    cat > "$completion_file" << EOF
# Completion Record

- **Idea**: $idea_id
- **Status**: $status
- **Completed**: $(date -Iseconds)
- **Work Directory**: $idea_work_dir

## Files Produced
$(ls -la "$idea_work_dir" 2>/dev/null || echo "Unable to list files")

## Summary
$(cat "$idea_work_dir/DONE" 2>/dev/null || echo "No DONE file found")
EOF

    log_info "Completion record saved: $completion_file"

    # Update idea in pool (if update_idea tool is available)
    claude --print "
If the mcp__idea-pool__update_idea tool is available, update idea '$idea_id':
- Set lifecycle to '$status'
- Add a note about implementation at $idea_work_dir
- Record completion date: $(date -Iseconds)

If the tool is not available, just acknowledge that the status update was skipped.
" 2>/dev/null || log_warn "Could not update idea pool status"

    log_info "Idea $idea_id marked as $status"
}

# =============================================================================
# Main Loop
# =============================================================================

process_idea() {
    local idea_id="$1"

    # Create work directory for this idea
    local idea_work_dir="$WORK_DIR/idea-$idea_id-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$idea_work_dir"

    log_info "Work directory: $idea_work_dir"

    # Phase 2: Research
    if ! run_research "$idea_id" "$idea_work_dir"; then
        log_error "Research phase failed"
        mark_complete "$idea_id" "$idea_work_dir" "tried"
        return 1
    fi

    # Phase 3: PRD
    if ! create_prd "$idea_id" "$idea_work_dir"; then
        log_error "PRD creation failed"
        mark_complete "$idea_id" "$idea_work_dir" "tried"
        return 1
    fi

    # Phase 4: Implementation
    if ! run_implementation "$idea_id" "$idea_work_dir"; then
        log_error "Implementation incomplete"
        mark_complete "$idea_id" "$idea_work_dir" "tried"
        return 1
    fi

    # Phase 5: Mark complete
    mark_complete "$idea_id" "$idea_work_dir" "implemented"

    log_info "Successfully implemented idea $idea_id"
    return 0
}

main() {
    setup

    while true; do
        # Phase 1: Extract
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

        # Process the idea through all phases
        if process_idea "$idea_id"; then
            log_info "Idea $idea_id completed successfully!"
        else
            log_warn "Idea $idea_id processing failed or incomplete"
        fi

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
