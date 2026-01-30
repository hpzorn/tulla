#!/bin/bash
# hygiene-lib.sh - Shared pre-flight hygiene and check functions
#
# Provides reusable functions for ontology state management:
#   run_preflight_hygiene  - Reset all statuses to Pending
#   run_check_mode         - Audit A-box for anomalies
#
# All functions accept explicit parameters rather than relying on globals.

# run_preflight_hygiene PRD_CONTEXT LOG_FILE BUDGET
#   PRD_CONTEXT: ontology-server context name (e.g., prd-36)
#   LOG_FILE:    path to log file for tee output
#   BUDGET:      max budget in USD for the claude subprocess (default: 1.00)
run_preflight_hygiene() {
    local prd_context="$1"
    local log_file="$2"
    local budget="${3:-1.00}"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting pre-flight hygiene reset for context: $prd_context" | tee -a "$log_file"

    local hygiene_result
    hygiene_result=$(timeout 5m claude --permission-mode acceptEdits \
        --max-budget-usd "$budget" \
        --allowedTools "mcp__ontology-server__recall_facts,mcp__ontology-server__forget_by_context,mcp__ontology-server__store_fact" \
        -p "You are a hygiene agent. Your task is to reset all requirement statuses in ontology-server context '${prd_context}' to Pending.

## Steps:
1. Use mcp__ontology-server__recall_facts with context='${prd_context}' to get ALL facts.
2. Use mcp__ontology-server__forget_by_context with context='${prd_context}' to wipe the entire context.
3. Re-store ALL facts using mcp__ontology-server__store_fact, but set every prd:status to 'prd:Pending' (overriding any Complete/InProgress statuses). Preserve all other properties exactly as they were (rdf:type, prd:title, prd:taskId, prd:description, prd:priority, prd:phase, prd:files, prd:action, prd:dependsOn, etc.).
4. On the FINAL line, output exactly: HYGIENE_COMPLETE if all facts were re-stored successfully, or HYGIENE_ERROR if anything failed.

Be thorough — every single fact must be re-stored." 2>&1 | tee -a "$log_file")

    if echo "$hygiene_result" | grep -q "HYGIENE_COMPLETE"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pre-flight hygiene completed successfully" | tee -a "$log_file"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: Pre-flight hygiene failed" | tee -a "$log_file"
        echo "$hygiene_result" | tail -20
        return 1
    fi
}

# run_check_mode PRD_CONTEXT LOG_FILE BUDGET
#   PRD_CONTEXT: ontology-server context name (e.g., prd-36)
#   LOG_FILE:    path to log file for tee output
#   BUDGET:      max budget in USD for the claude subprocess (default: 0.50)
run_check_mode() {
    local prd_context="$1"
    local log_file="$2"
    local budget="${3:-0.50}"

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting A-box audit for context: $prd_context" | tee -a "$log_file"

    local check_result
    check_result=$(timeout 3m claude --permission-mode acceptEdits \
        --max-budget-usd "$budget" \
        --allowedTools "mcp__ontology-server__recall_facts,mcp__ontology-server__get_memory_stats" \
        -p "You are an ontology audit agent. Audit the A-box state of PRD context '${prd_context}'.

## Steps:
1. Use mcp__ontology-server__recall_facts with context='${prd_context}' to get ALL facts.
2. Group facts by requirement subject (e.g., prd:req-*).
3. For each requirement, check for anomalies:
   - ANOMALY: A requirement has ZERO prd:status facts (missing status)
   - ANOMALY: A requirement has MORE THAN ONE prd:status fact (duplicate status)
   - OK: A requirement has exactly one prd:status fact
4. Output a structured status report listing each requirement, its status, and any anomalies.
5. On the FINAL line, output exactly one of:
   - CHECK_HEALTHY — if no anomalies were found
   - CHECK_ANOMALIES: N anomalies found — if N anomalies were detected

Be thorough — check every requirement." 2>&1 | tee -a "$log_file")

    echo "$check_result"

    if echo "$check_result" | grep -q "CHECK_HEALTHY"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] A-box audit passed: no anomalies" | tee -a "$log_file"
        return 0
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] A-box audit found anomalies" | tee -a "$log_file"
        return 1
    fi
}
