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
NO_VERIFY="${NO_VERIFY:-false}"
MAX_RETRIES="${MAX_RETRIES:-2}"

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
            echo "  --no-verify       Skip verification step (implementer marks Complete directly)"
            echo "  --max-retries N   Max retry attempts per requirement on verification failure (default: 2)"
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
        --no-verify)
            NO_VERIFY=true
            shift
            ;;
        --max-retries)
            MAX_RETRIES="$2"
            shift 2
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
        if [[ -n "${REQ_ID:-}" ]]; then
            log "Last requirement in progress: $REQ_ID"
            log "Check git log and ontology state before resuming."
        fi
        log "To audit ontology state: $0 --prd $PRD_CONTEXT --check"
        log "To re-run with clean state: $0 --prd $PRD_CONTEXT --clean"
        log "To resume from current state: $0 --prd $PRD_CONTEXT --no-clean"
    fi
}
trap cleanup EXIT

# Crash Recovery Notes:
# - If the script crashes between implement and verify, the git commit exists
#   but ontology still shows Pending. Re-running with --no-clean resumes safely:
#   the implementer may re-implement (creating a new commit) and the verifier runs.
# - If the script crashes after verify but before status update, re-running with
#   --no-clean may re-verify (harmless). Use --check to audit state.
# - Use 'git log --grep="impl("' to see all implementation commits.
# - Use --check to audit ontology state at any time.

log "=============================================="
log "Implementation-Ralph starting"
log "PRD Context: $PRD_CONTEXT"
log "Work Directory: $WORK_DIR"
log "=============================================="
log "Clean mode: $CLEAN"
log "Check-only mode: $CHECK_ONLY"
log "No-verify mode: $NO_VERIFY"
log "Max retries: $MAX_RETRIES"

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
# Helper Functions (Implementer/Verifier Pattern)
# =============================================================================

# find_ready_requirement()
#   Spawns a read-only Claude subprocess to query ontology and find the next
#   READY requirement (Pending with all deps Complete).
#   Outputs structured KEY: value lines to stdout.
#   Returns 0 if found, 1 if ALL_COMPLETE or BLOCKED.
find_ready_requirement() {
    local finder_result
    finder_result=$(timeout 5m claude --permission-mode acceptEdits \
        --max-budget-usd 1.00 \
        --allowedTools "mcp__ontology-server__recall_facts" \
        -p "You are a requirement finder agent. Query the ontology to find the next READY requirement.

## Steps:
1. Use mcp__ontology-server__recall_facts with context='${PRD_CONTEXT}' to get all facts.
2. Identify all requirements (rdf:type = prd:Requirement).
3. A requirement is READY if:
   - Its prd:status is 'prd:Pending'
   - All requirements it prd:dependsOn have prd:status = 'prd:Complete'
   - If no dependsOn, it's ready
4. Select the first READY requirement by priority (P0 before P1 before P2), then by taskId.
5. Output structured data on separate lines:
   REQ_ID: [requirement subject, e.g., prd:req-idea-40-3-1]
   TASK_ID: [taskId value]
   TITLE: [title]
   DESCRIPTION: [full description]
   FILES: [files value]
   ACTION: [action value or 'infer']
   PRIORITY: [priority]
   PHASE: [phase]
   VERIFICATION: [verification criteria]
6. On the FINAL line, output exactly one of:
   - FOUND_READY if a ready requirement was found
   - ALL_COMPLETE if all requirements have status prd:Complete
   - BLOCKED if no ready requirements exist (all pending have unmet deps)

Be precise and thorough." 2>&1)

    echo "$finder_result" | tee -a "$LOG_FILE"

    if echo "$finder_result" | grep -q "FOUND_READY"; then
        # Extract key fields into global variables for the caller
        REQ_ID=$(echo "$finder_result" | grep "^REQ_ID:" | head -1 | sed 's/^REQ_ID: *//')
        REQ_TASK_ID=$(echo "$finder_result" | grep "^TASK_ID:" | head -1 | sed 's/^TASK_ID: *//')
        REQ_TITLE=$(echo "$finder_result" | grep "^TITLE:" | head -1 | sed 's/^TITLE: *//')
        REQ_ACTION=$(echo "$finder_result" | grep "^ACTION:" | head -1 | sed 's/^ACTION: *//')
        REQ_FILES=$(echo "$finder_result" | grep "^FILES:" | head -1 | sed 's/^FILES: *//')
        return 0
    elif echo "$finder_result" | grep -q "ALL_COMPLETE"; then
        return 2
    else
        return 1
    fi
}

# run_implementer REQ_ID [PREVIOUS_FAILURE_REASON]
#   Spawns an implementer Claude subprocess to implement the requirement.
#   Does NOT mark the requirement Complete (that's a separate step).
#   If PREVIOUS_FAILURE_REASON is provided, includes it in the prompt so the
#   implementer can address the specific issues found by the verifier.
#   Outputs IMPLEMENTED: [req-id] on success.
#   Returns 0 on success, 1 on failure.
run_implementer() {
    local req_id="$1"
    local previous_failure="${2:-}"
    log "--- Phase 2: Implementing $req_id ---"

    # Build retry feedback block if this is a retry after verification failure
    local retry_feedback_block=""
    if [[ -n "$previous_failure" ]]; then
        retry_feedback_block="
## PREVIOUS ATTEMPT FAILED VERIFICATION

Your previous implementation was rejected by the verifier. You MUST address the
specific issues listed below. Do NOT just repeat the same implementation — fix
the problems identified.

**Verification failure reason:**
${previous_failure}

Read the failure reason carefully. Common issues include:
- Missing tests that the prd:verification field requires
- Files created in the wrong location
- Missing acceptance criteria
Address ALL issues before outputting IMPLEMENTED.
"
        log "Including verification feedback from previous attempt"
    fi

    local impl_result
    impl_result=$(timeout 10m claude --permission-mode acceptEdits \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__ontology-server__recall_facts,Read,Write,Edit,Bash,Glob" \
        -p "You are Implementation-Ralph, an ontology-driven implementation agent.

## Your Task
Implement ONE specific requirement from the PRD stored in ontology-server context '${PRD_CONTEXT}'.
The requirement to implement is: ${req_id}
${retry_feedback_block}
## CRITICAL RULES
1. You must ONLY read requirements from ontology-server using recall_facts
2. You must NOT look at any markdown files - all info comes from the ontology
3. For NEW files, use Python 3.11+ unless the requirement specifies otherwise
4. For EXISTING files, use the file's own language (bash for .sh, markdown for .md, etc.)
5. Do NOT update the requirement status - just implement the code changes
6. Read the prd:verification field — you must ensure your implementation SATISFIES the verification criteria (e.g., if it says 'Unit test for X', you must create that test)

## Steps:
1. Use mcp__ontology-server__recall_facts with subject='${req_id}' and context='${PRD_CONTEXT}' to get all properties of this requirement.
2. Read the prd:description for EXACTLY what to do.
3. Read the prd:files for which file(s) to create or modify.
4. Read the prd:action:
   - 'modify': Read the existing file first, then Edit it in place using the file's native language.
   - 'create': Write a new file to ${WORK_DIR}/[filepath]. Use Python 3.11+ unless specified otherwise.
   - If absent, infer from description.
5. Read the prd:verification field and ensure your implementation will PASS those checks.
6. For modifications to files OUTSIDE ${WORK_DIR}: edit the actual file at its real path.
7. NEVER create a Python module as a substitute for modifying an existing non-Python file.

## Output
On the FINAL line, output exactly:
- IMPLEMENTED: ${req_id} — if you successfully implemented the requirement
- IMPLEMENT_FAIL: ${req_id} [reason] — if implementation failed

Be precise and implement exactly what the requirement describes." 2>&1)

    echo "$impl_result" | tee -a "$LOG_FILE"

    if echo "$impl_result" | grep -q "IMPLEMENTED:"; then
        return 0
    else
        return 1
    fi
}

# git_commit_requirement REQ_ID TITLE
#   Stages all changes and creates a git commit with structured message.
#   Prints commit SHA on success.
#   Returns 0 on success, 1 if nothing to commit.
git_commit_requirement() {
    local req_id="$1"
    local title="$2"

    # NOTE: This function is called inside $(), so only the commit SHA
    # should go to stdout. All log messages go directly to the log file
    # (and stderr for visibility) to avoid polluting the captured output.

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] --- Phase 3: Committing $req_id ---" >> "$LOG_FILE"

    # Stage all changes
    if ! git add -A 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: git add failed" | tee -a "$LOG_FILE" >&2
        return 1
    fi

    # Check if there are staged changes
    if git diff --cached --quiet 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: No changes to commit for $req_id" | tee -a "$LOG_FILE" >&2
        return 1
    fi

    # Create commit with structured message
    local commit_msg="impl(${req_id}): ${title}"
    local commit_result
    if commit_result=$(git commit -m "$commit_msg" 2>&1); then
        local commit_sha
        commit_sha=$(git rev-parse --short HEAD)
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Committed: $commit_sha - $commit_msg" | tee -a "$LOG_FILE" >&2
        # Only the SHA goes to stdout (captured by caller)
        echo "$commit_sha"
        return 0
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: git commit failed: $commit_result" | tee -a "$LOG_FILE" >&2
        return 1
    fi
}

# run_verifier REQ_ID
#   Spawns a fresh-context Claude subprocess to verify the implementation.
#   Read-only tools only — verifier cannot modify files.
#   Outputs VERIFY_PASS: [req-id] or VERIFY_FAIL: [req-id] [reason].
#   Returns 0 on PASS, 1 on FAIL.
run_verifier() {
    local req_id="$1"
    local schema_context_file="$SCRIPT_DIR/prompts/isaqb-schema-context.md"
    log "--- Phase 4: Verifying $req_id ---"

    if [[ "$NO_VERIFY" == "true" ]]; then
        log "SKIPPED (--no-verify mode)"
        echo "VERIFY_PASS: $req_id (skipped)"
        return 0
    fi

    # Load iSAQB schema context if available
    local schema_context_block=""
    if [[ -f "$schema_context_file" ]]; then
        schema_context_block=$(cat "$schema_context_file")
        log "Loaded iSAQB schema context for verification from $schema_context_file"
    else
        log "WARNING: iSAQB schema context not found at $schema_context_file — proceeding without"
    fi

    local verify_result
    verify_result=$(timeout 5m claude --permission-mode acceptEdits \
        --max-budget-usd 2.00 \
        --allowedTools "mcp__ontology-server__recall_facts,mcp__ontology-server__query_ontology,mcp__ontology-server__sparql_query,Read,Glob,Bash" \
        -p "You are a verification agent. Verify that requirement ${req_id} from PRD context '${PRD_CONTEXT}' has been correctly implemented.

## iSAQB Architecture Schema

${schema_context_block}

## Steps:
1. Use mcp__ontology-server__recall_facts with subject='${req_id}' and context='${PRD_CONTEXT}' to get the requirement details.
2. Read the prd:verification field — it describes how to verify.
3. Read the prd:files field to know which files to check.
4. Read the prd:description to understand what was supposed to be implemented.
5. Perform the verification checks described in prd:verification.
   - Use Read to inspect files.
   - Use Bash ONLY for read-only commands (grep, bash -n, etc.) — NEVER modify files.
6. Perform iSAQB-aware verification:
   - If the implementation involves architecture decisions, verify they reference
     isaqb:ArchitectureDecision properties (context, options, rationale, consequences).
   - If the implementation involves quality attributes, verify they align with
     isaqb:QualityAttribute and isaqb:QualityScenario structures.
   - If the implementation involves design patterns or architectural patterns, verify
     they reference isaqb:ArchitecturalPattern or isaqb:DesignPattern correctly.
   - Use mcp__ontology-server__query_ontology or mcp__ontology-server__sparql_query
     to cross-check referenced iSAQB concepts exist in the ontology.
7. On the FINAL line, output exactly one of:
   - VERIFY_PASS: ${req_id} — if the implementation matches the requirement
   - VERIFY_FAIL: ${req_id} [specific reason for failure]

Be strict — the implementation must match the requirement exactly.
Use the iSAQB schema to validate architectural consistency where applicable." 2>&1)

    echo "$verify_result" | tee -a "$LOG_FILE"

    if echo "$verify_result" | grep -q "VERIFY_PASS:"; then
        return 0
    else
        return 1
    fi
}

# update_requirement_status REQ_ID NEW_STATUS [VERDICT]
#   Spawns a minimal Claude subprocess to update the ontology status
#   using strict forget-then-store protocol.
#   NEW_STATUS: 'prd:Complete' or 'prd:Blocked'
#   VERDICT: optional verification verdict string
#   Returns 0 on success, 1 on failure.
update_requirement_status() {
    local req_id="$1"
    local new_status="$2"
    local verdict="${3:-}"
    log "--- Phase 5: Updating status of $req_id to $new_status ---"

    local verdict_instruction=""
    if [[ -n "$verdict" ]]; then
        verdict_instruction="
Also store the verification verdict:
- subject: '${req_id}'
- predicate: 'prd:verificationVerdict'
- object: '${verdict}'
- context: '${PRD_CONTEXT}'"
    fi

    local status_result
    status_result=$(timeout 3m claude --permission-mode acceptEdits \
        --max-budget-usd 1.00 \
        --allowedTools "mcp__ontology-server__recall_facts,mcp__ontology-server__store_fact,mcp__ontology-server__forget_fact" \
        -p "You are a status update agent. Update the status of requirement ${req_id} in ontology-server.

## Steps (strict forget-then-store ordering):
1. Use mcp__ontology-server__recall_facts with subject='${req_id}' and predicate='prd:status' and context='${PRD_CONTEXT}' to find the fact_id of the current status.
2. Use mcp__ontology-server__forget_fact with that fact_id to REMOVE the old status. If forget fails, do NOT proceed — output STATUS_ERROR.
3. Only after forget succeeds, use mcp__ontology-server__store_fact to set:
   - subject: '${req_id}'
   - predicate: 'prd:status'
   - object: '${new_status}'
   - context: '${PRD_CONTEXT}'
${verdict_instruction}

CRITICAL: You MUST forget before storing. Never store before forgetting.

On the FINAL line, output exactly:
- STATUS_UPDATED: ${req_id} — if the update succeeded
- STATUS_ERROR: ${req_id} [reason] — if the update failed" 2>&1)

    echo "$status_result" | tee -a "$LOG_FILE"

    if echo "$status_result" | grep -q "STATUS_UPDATED:"; then
        return 0
    else
        return 1
    fi
}

# revert_failed_implementation COMMIT_SHA
#   Reverts the given commit non-interactively to clean up a failed implementation.
#   Returns 0 on success, 1 on failure.
revert_failed_implementation() {
    local commit_sha="$1"
    log "Reverting failed implementation commit: $commit_sha"

    if git revert --no-edit "$commit_sha" 2>&1 | tee -a "$LOG_FILE"; then
        log "Successfully reverted $commit_sha"
        return 0
    else
        log "ERROR: Failed to revert $commit_sha — manual cleanup may be needed"
        # Abort the revert if it's stuck
        git revert --abort 2>/dev/null || true
        return 1
    fi
}

# =============================================================================
# Main Implementation Loop (Five-Phase Pattern)
# =============================================================================
#
# Each iteration:
#   Phase 1 (Find):    find_ready_requirement -> next READY requirement
#   Phase 2 (Implement): run_implementer with retry loop up to MAX_RETRIES
#   Phase 3 (Commit):  git_commit_requirement -> per-requirement commit
#   Phase 4 (Verify):  run_verifier (skipped if --no-verify or no criteria)
#   Phase 5 (Status):  update_requirement_status -> Complete or Blocked
#
# On VERIFY_FAIL: revert commit, retry implementation. After max retries, mark Blocked.

iteration=0

while [[ $iteration -lt $MAX_ITERATIONS ]]; do
    ((iteration++))
    log ""
    log "=============================================="
    log "=== Iteration $iteration of $MAX_ITERATIONS ==="
    log "=============================================="

    # Phase 1: Find the next ready requirement
    log "--- Phase 1: Finding next ready requirement ---"
    REQ_ID=""
    REQ_TASK_ID=""
    REQ_TITLE=""
    REQ_ACTION=""
    REQ_FILES=""

    find_ready_requirement
    find_status=$?

    if [[ $find_status -eq 2 ]]; then
        log ""
        log "=============================================="
        log "ALL REQUIREMENTS COMPLETE!"
        log "=============================================="
        break
    elif [[ $find_status -ne 0 ]]; then
        log ""
        log "ERROR: Implementation blocked - no ready requirements found"
        log "Check dependencies or use --check to audit ontology state."
        exit 1
    fi

    log "Found ready requirement: $REQ_ID ($REQ_TASK_ID) - $REQ_TITLE"

    # Phase 2-4: Implement, Commit, Verify (with retry loop)
    retry=0
    impl_succeeded=false
    last_verify_failure=""

    while [[ $retry -lt $MAX_RETRIES ]]; do
        ((retry++))
        log ""
        log "--- Attempt $retry of $MAX_RETRIES for $REQ_ID ---"

        # Phase 2: Implement (pass previous failure reason if retrying)
        if ! run_implementer "$REQ_ID" "$last_verify_failure"; then
            log "ERROR: Implementation failed for $REQ_ID (attempt $retry)"
            if [[ $retry -lt $MAX_RETRIES ]]; then
                log "Retrying implementation..."
                sleep 2
                continue
            else
                log "ERROR: Max retries exhausted for $REQ_ID"
                break
            fi
        fi

        # Phase 3: Commit
        commit_sha=""
        commit_sha=$(git_commit_requirement "$REQ_ID" "$REQ_TITLE") || true

        if [[ -z "$commit_sha" ]]; then
            log "WARNING: No commit created for $REQ_ID (no changes detected)"
            # Proceed anyway — implementation may have been idempotent
        fi

        # Phase 4: Verify
        verify_verdict=""
        if run_verifier "$REQ_ID"; then
            verify_verdict="PASS"
            impl_succeeded=true
            log "VERIFY_PASS: $REQ_ID"
            break
        else
            # Extract the specific failure reason from the verifier output
            # (the log file was just appended to by run_verifier via tee)
            last_verify_failure=$(grep "VERIFY_FAIL:" "$LOG_FILE" | tail -1 | sed "s/.*VERIFY_FAIL: [^ ]* *//" || echo "verification failed")
            verify_verdict="FAIL: $last_verify_failure"
            log "VERIFY_FAIL: $REQ_ID (attempt $retry)"
            log "Failure reason captured for retry feedback: $last_verify_failure"

            # Revert the failed implementation commit if one was created
            if [[ -n "$commit_sha" ]]; then
                revert_failed_implementation "$commit_sha" || true
            fi

            if [[ $retry -lt $MAX_RETRIES ]]; then
                log "Retrying after verification failure — feedback will be passed to implementer..."
                sleep 2
            else
                log "ERROR: Max retries exhausted for $REQ_ID after verification failure"
            fi
        fi
    done

    # Phase 5: Update requirement status
    if [[ "$impl_succeeded" == "true" ]]; then
        log "--- Phase 5: Marking $REQ_ID as Complete ---"
        if ! update_requirement_status "$REQ_ID" "prd:Complete" "$verify_verdict"; then
            log "ERROR: Failed to update status for $REQ_ID"
            log "Implementation was successful but ontology update failed."
            log "Use --check to audit state. Manual intervention may be needed."
        fi
        log "Completed: $REQ_ID"
    else
        log "--- Phase 5: Marking $REQ_ID as Blocked ---"
        if ! update_requirement_status "$REQ_ID" "prd:Blocked" "$verify_verdict"; then
            log "ERROR: Failed to update status for $REQ_ID"
        fi
        log "BLOCKED: $REQ_ID after $MAX_RETRIES failed attempts"
    fi

    # Brief pause between iterations
    sleep 2
done

if [[ $iteration -ge $MAX_ITERATIONS ]]; then
    log ""
    log "ERROR: Max iterations ($MAX_ITERATIONS) reached"
    exit 1
fi

log ""
log "Implementation complete. Files in: $WORK_DIR"
ls -la "$WORK_DIR/src/" "$WORK_DIR/tests/" 2>/dev/null || true
