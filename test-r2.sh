#!/bin/bash
# Minimal R2 test to diagnose the subprocess issue

set -x  # Debug mode

WORK_DIR="/Users/sandboxuser/ideasralph/work/idea-34-20260129-071814"
OUTPUT_FILE="$WORK_DIR/r2-test-minimal.md"

touch "$OUTPUT_FILE"

echo "=== Test 1: Without Read tool (like R1) ==="
timeout 60s claude --permission-mode acceptEdits \
    --allowedTools "Write" \
    -p "Write 'Test without Read tool works' to ${OUTPUT_FILE}" 2>&1

echo "Exit code: $?"
echo "File contents:"
cat "$OUTPUT_FILE"
echo ""

echo "=== Test 2: With Read tool ==="
OUTPUT_FILE2="$WORK_DIR/r2-test-with-read.md"
touch "$OUTPUT_FILE2"

timeout 60s claude --permission-mode acceptEdits \
    --allowedTools "Read,Write" \
    -p "Write 'Test with Read tool works' to ${OUTPUT_FILE2}" 2>&1

echo "Exit code: $?"
echo "File contents:"
cat "$OUTPUT_FILE2"
