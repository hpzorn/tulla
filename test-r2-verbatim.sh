#!/bin/bash
# Verbatim R2 command for debugging

WORK_DIR="/Users/sandboxuser/ideasralph/work/idea-34-20260129-071814"
OUTPUT_FILE="$WORK_DIR/r2-sub-aspect-research-test.md"
R1_FILE="$WORK_DIR/r1-prior-art-scan.md"

# Pre-create output file
touch "$OUTPUT_FILE"

echo "Starting R2 at $(date '+%H:%M:%S')"
echo "Output file: $OUTPUT_FILE"
echo "R1 file: $R1_FILE"
echo ""

timeout 20m claude --permission-mode acceptEdits \
    --max-budget-usd "5.00" \
    --allowedTools "mcp__idea-pool__read_idea,Read,Write,WebSearch" \
    -p "You are conducting Phase R2: Sub-Aspect Research for idea 34.

## Goal
Decompose the idea into components and find existing research on each.

## Instructions

1. First, read the required context:
   - Use mcp__idea-pool__read_idea with identifier 34 to read the idea
   - Use the Read tool to read the prior art scan: ${R1_FILE}

2. Decompose the idea into 3-6 distinct sub-aspects/components
   Example: An idea about 'AI code review' might decompose into:
   - Static analysis techniques
   - LLM prompt engineering for code
   - Developer workflow integration
   - Diff understanding algorithms

2. For each sub-aspect, search for:
   - Academic papers (arXiv, Google Scholar)
   - Industry blog posts and case studies
   - Open source implementations
   - Known limitations and challenges

3. Write findings to: ${OUTPUT_FILE}

   Structure:

   # R2: Sub-Aspect Research
   **Idea**: 34
   **Date**: $(date +%Y-%m-%d)
   **Time-box**: 20 minutes

   ## Idea Decomposition

   The idea breaks down into these components:
   1. [Component A]
   2. [Component B]
   ...

   ## Sub-Aspect Analysis

   ### Component A: [Name]
   **Existing Research**:
   - [Paper/Article 1]: [key finding]
   - [Paper/Article 2]: [key finding]

   **State of the Art**: [What is currently possible]
   **Open Challenges**: [What remains unsolved]
   **Relevance to Idea**: [How this informs our approach]

   ### Component B: [Name]
   [Same structure...]

   ## Knowledge Gaps
   [What aspects have NO existing research - these become research questions]

   ## Key Papers to Read in Depth
   1. [Citation] - reason for importance
   2. [Citation] - reason for importance
   ...

Cite sources properly: Author (Year). Title. Venue/URL."

echo ""
echo "Exit code: $?"
echo "Finished at $(date '+%H:%M:%S')"
echo ""
echo "=== Output file contents ==="
cat "$OUTPUT_FILE"
