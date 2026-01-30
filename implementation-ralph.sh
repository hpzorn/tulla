#!/bin/bash
# implementation-ralph.sh - Ontology-Driven Implementation Loop
#
# Reads requirements from ontology-server (NOT from markdown)
# Implements requirements respecting dependencies
# Updates status in ontology-server as work completes
#
# Usage: ./implementation-ralph.sh --prd CONTEXT_NAME [--work-dir DIR]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/hygiene-lib.sh"

# Defaults
PRD_CONTEXT=""
WORK_DIR=""
MAX_BUDGET_USD="${MAX_BUDGET_USD:-5.00}"
MAX_ITERATIONS="${MAX_ITERATIONS:-20}"
CLEAN="${CLEAN:-true}"
CHECK_ONLY="${CHECK_ONLY:-false}"

# =============================================================================
# Argument Parsing
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --prd)
            PRD_CONTEXT="$2"
            shift 2
            ;;
        --work-dir)
            WORK_DIR="$2"
            shift 2
            ;;
        --max-budget)
            MAX_BUDGET_USD="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 --prd CONTEXT_NAME [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --prd CONTEXT     Required: PRD context name in ontology-server (e.g., prd-sample-42)"
            echo "  --work-dir DIR    Working directory for implementation (default: work/impl-CONTEXT-TIMESTAMP)"
            echo "  --max-budget USD  Max API cost per iteration (default: 5.00)"
            echo "  --clean           Reset all statuses to Pending before running (default)"
            echo "  --no-clean        Skip pre-flight hygiene, resume from current state"
            echo "  --check           Audit ontology state without implementing (exits after report)"
            echo "  --help            Show this help"
            exit 0
            ;;
        --clean)
            CLEAN=true
            shift
            ;;
        --no-clean)
            CLEAN=false
            shift
            ;;
        --check)
            CHECK_ONLY=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

if [[ -z "$PRD_CONTEXT" ]]; then
    echo "Error: --prd CONTEXT_NAME is required"
    exit 1
fi

# Set work dir if not specified
if [[ -z "$WORK_DIR" ]]; then
    WORK_DIR="$SCRIPT_DIR/work/impl-$PRD_CONTEXT-$(date +%Y%m%d-%H%M%S)"
fi

mkdir -p "$WORK_DIR/src" "$WORK_DIR/tests"

LOG_FILE="$WORK_DIR/implementation.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

cleanup() {
    local exit_code=$?
    if [[ $exit_code -ne 0 ]]; then
        log "INTERRUPTED: Exit code $exit_code"
        log "To audit ontology state: $0 --prd $PRD_CONTEXT --check"
        log "To re-run with clean state: $0 --prd $PRD_CONTEXT --clean"
    fi
}
trap cleanup EXIT

log "=============================================="
log "Implementation-Ralph starting"
log "PRD Context: $PRD_CONTEXT"
log "Work Directory: $WORK_DIR"
log "=============================================="
log "Clean mode: $CLEAN"
log "Check-only mode: $CHECK_ONLY"

# =============================================================================
# Pre-flight Hygiene (delegates to hygiene-lib.sh)
# =============================================================================

# Wrapper: calls shared run_preflight_hygiene with script-level parameters
_run_preflight_hygiene() {
    run_preflight_hygiene "$PRD_CONTEXT" "$LOG_FILE" 1.00 || exit 1
}

# =============================================================================
# Check Mode (delegates to hygiene-lib.sh)
# =============================================================================

# Wrapper: calls shared run_check_mode with script-level parameters
_run_check_mode() {
    run_check_mode "$PRD_CONTEXT" "$LOG_FILE" 0.50
    exit $?
}

# =============================================================================
# Pre-flight Control Flow Gate
# =============================================================================

if [[ "$CHECK_ONLY" == "true" ]]; then
    _run_check_mode
    # _run_check_mode exits, but just in case:
    exit 0
elif [[ "$CLEAN" == "true" ]]; then
    _run_preflight_hygiene
else
    log "WARNING: --no-clean specified. Skipping pre-flight hygiene."
    log "Stale statuses from previous runs may cause unexpected behavior."
    log "Use --check to audit or re-run with --clean (default) to reset."
fi

# =============================================================================
# Main Implementation Loop
# =============================================================================

iteration=0

while [[ $iteration -lt $MAX_ITERATIONS ]]; do
    ((iteration++))
    log ""
    log "=== Iteration $iteration ==="

    # Ask Claude to:
    # 1. Query requirements from ontology-server
    # 2. Find a ready requirement (Pending with all deps Complete)
    # 3. Implement it
    # 4. Update status to Complete

    result=$(timeout 10m claude --permission-mode acceptEdits \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__ontology-server__recall_facts,mcp__ontology-server__store_fact,mcp__ontology-server__forget_fact,Read,Write,Edit,Bash,Glob" \
        -p "You are Implementation-Ralph, an ontology-driven implementation agent.

## Your Task
Implement ONE requirement from the PRD stored in ontology-server context '${PRD_CONTEXT}'.

## CRITICAL RULES
1. You must ONLY read requirements from ontology-server using recall_facts
2. You must NOT look at any markdown files - all info comes from the ontology
3. For NEW files, use Python 3.11+ unless the requirement specifies otherwise
4. For EXISTING files, use the file's own language (bash for .sh, markdown for .md, etc.)
5. After implementing, update the requirement status to Complete

## Step 1: Load Requirements
Use mcp__ontology-server__recall_facts with context='${PRD_CONTEXT}' to get all requirements.

## Step 2: Find Ready Requirement
A requirement is READY if:
- Its prd:status is 'prd:Pending'
- All requirements it prd:dependsOn have prd:status = 'prd:Complete'
- If no dependsOn, it's ready

Select the first ready requirement by priority (P0 before P1 before P2).

## Step 3: Implement
- Read the prd:description for EXACTLY what to do — it contains precise instructions
- Read the prd:files for which file(s) to create or modify
- Read the prd:action if present:
  - 'modify': You MUST Read the existing file first, then Edit it in place using the file's native language (bash for .sh, markdown for .md, Typst for .typ, YAML for .yaml). The prd:description contains exact insertion points and code to add. Do NOT rewrite the file in Python.
  - 'create': Write a new file to ${WORK_DIR}/[filepath]. Use Python 3.11+ unless prd:description specifies another language.
- If prd:action is absent, infer from prd:description: if it says 'Modify [file]' or 'Replace [section]' or 'Add [thing] to [file]', treat as modify. If it says 'Create [file]', treat as create.
- For modifications to files OUTSIDE ${WORK_DIR}: edit the actual file at its real path
- NEVER create a Python module as a substitute for modifying an existing non-Python file
- Use best practices: docstrings/comments, type hints, error handling

## Step 4: Mark Complete (MUST forget before storing)
Update the requirement status using strict forget-then-store ordering:

Step 4a: Use mcp__ontology-server__recall_facts with subject=[requirement id] and predicate='prd:status' and context='${PRD_CONTEXT}' to find the fact_id of the current Pending status.

Step 4b: Use mcp__ontology-server__forget_fact with the fact_id from Step 4a to REMOVE the old Pending status. If forget fails, do NOT proceed to Step 4c — report an error instead.

Step 4c: Only after forget succeeds, use mcp__ontology-server__store_fact to SET the new status:
- subject: [requirement id, e.g., 'prd:req-42-1']
- predicate: 'prd:status'
- object: 'prd:Complete'
- context: '${PRD_CONTEXT}'

CRITICAL: You MUST forget before storing, never store before forgetting. If forget fails, do NOT store.

## Step 5: Report
Output one of these on the FINAL line:
- 'IMPLEMENTED: [req-id]' if you implemented a requirement
- 'ALL_COMPLETE' if all requirements have status Complete
- 'BLOCKED' if no ready requirements found (circular dep or error)

Be precise and implement exactly what the requirement describes." 2>&1 | tee -a "$LOG_FILE")

    # Check result
    if echo "$result" | grep -q "ALL_COMPLETE"; then
        log ""
        log "=============================================="
        log "ALL REQUIREMENTS COMPLETE!"
        log "=============================================="
        break
    elif echo "$result" | grep -q "BLOCKED"; then
        log ""
        log "ERROR: Implementation blocked - check dependencies"
        exit 1
    elif echo "$result" | grep -q "IMPLEMENTED:"; then
        req_id=$(echo "$result" | grep "IMPLEMENTED:" | tail -1 | sed 's/.*IMPLEMENTED: *//')
        log "Completed: $req_id"
    else
        log "WARNING: Unclear result, continuing..."
    fi

    # Brief pause between iterations
    sleep 2
done

if [[ $iteration -ge $MAX_ITERATIONS ]]; then
    log "ERROR: Max iterations ($MAX_ITERATIONS) reached"
    exit 1
fi

log ""
log "Implementation complete. Files in: $WORK_DIR"
ls -la "$WORK_DIR/src/" "$WORK_DIR/tests/" 2>/dev/null || true
