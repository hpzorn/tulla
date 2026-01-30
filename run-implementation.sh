#!/bin/bash
# Run implementation phase for idea 34
# Execute from terminal: cd ~/ideasralph && ./run-implementation.sh

set -euo pipefail

WORK_DIR="/Users/sandboxuser/ideasralph/work/idea-34-20260129-071814"
PRD_FILE="$WORK_DIR/prd.md"
LOG_FILE="$WORK_DIR/implementation.log"

cd "$WORK_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting implementation phase" | tee -a "$LOG_FILE"
echo "Work directory: $WORK_DIR" | tee -a "$LOG_FILE"

# Read PRD content
PRD_CONTENT=$(cat "$PRD_FILE")

timeout 60m claude --permission-mode acceptEdits \
    --max-budget-usd "10.00" \
    --allowedTools "Read,Write,Edit,Bash,Glob,Grep" \
    -p "## Implementation Task

You are implementing a PRD. Work in the current directory: ${WORK_DIR}

## CRITICAL: Language Requirement
**ALWAYS use Python** for all code and implementation.
Do NOT use TypeScript, JavaScript, or any other language.
Python 3.11+ is the target runtime.

## PRD Content:
${PRD_CONTENT}

## Instructions

1. Review the PRD and the research artifacts in this directory
2. Implement the solution using PYTHON ONLY - create files, write code, etc.
3. Create a proper Python package structure
4. Include tests for core functionality
5. Check each success criterion from the PRD

## Completion

When ALL success criteria from the PRD are met:
1. Create a file named DONE containing:
   - Summary of what was implemented
   - List of files created/modified
   - How to run/test the implementation
   - Any follow-up tasks for later
2. The presence of DONE file signals completion

If you cannot complete (blocked/stuck):
- Document the issue in a file named BLOCKED with explanation
- We will retry or escalate

<promise>ALL_PRD_ITEMS_COMPLETE</promise>" 2>&1 | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Implementation phase finished" | tee -a "$LOG_FILE"

if [[ -f "$WORK_DIR/DONE" ]]; then
    echo "SUCCESS: DONE file created" | tee -a "$LOG_FILE"
    cat "$WORK_DIR/DONE"
elif [[ -f "$WORK_DIR/BLOCKED" ]]; then
    echo "BLOCKED: See BLOCKED file" | tee -a "$LOG_FILE"
    cat "$WORK_DIR/BLOCKED"
else
    echo "WARNING: Neither DONE nor BLOCKED file created" | tee -a "$LOG_FILE"
fi
