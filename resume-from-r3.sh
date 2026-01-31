#!/bin/bash
# Resume research-ralph from R3, reusing existing R1/R2 outputs
#
# Usage: ./resume-from-r3.sh

set -euo pipefail

IDEA_ID="34"
WORK_DIR="/Users/sandboxuser/ideasralph/work/idea-34-20260129-071814"
LOG_FILE="$WORK_DIR/resume.log"
MAX_BUDGET_USD="5.00"

# Time boxes (minutes)
R3_MINUTES=15
R4_MINUTES=30
R5_MINUTES=60
R6_MINUTES=15

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# Verify R1 and R2 exist
if [[ ! -s "$WORK_DIR/r1-prior-art-scan.md" ]]; then
    echo "ERROR: R1 output missing: $WORK_DIR/r1-prior-art-scan.md"
    exit 1
fi

if [[ ! -s "$WORK_DIR/r2-sub-aspect-research.md" ]]; then
    echo "ERROR: R2 output missing: $WORK_DIR/r2-sub-aspect-research.md"
    exit 1
fi

log "Resuming from R3 for idea $IDEA_ID"
log "Work directory: $WORK_DIR"

# =============================================================================
# R3: Research Question Formulation
# =============================================================================
run_r3() {
    local output_file="$WORK_DIR/r3-research-questions.md"
    local r1_file="$WORK_DIR/r1-prior-art-scan.md"
    local r2_file="$WORK_DIR/r2-sub-aspect-research.md"

    log "R3: Research Question Formulation (${R3_MINUTES} min)"
    touch "$output_file"

    timeout ${R3_MINUTES}m claude --permission-mode acceptEdits \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write" \
        -p "You are conducting Phase R3: Research Question Formulation for idea ${IDEA_ID}.

## Goal
Define 2-4 precise, falsifiable research questions that must be answered to realize this idea.

## Instructions

1. First, read the required context:
   - Use mcp__idea-pool__read_idea with identifier ${IDEA_ID} to read the idea
   - Use the Read tool to read the prior art scan: ${r1_file}
   - Use the Read tool to read the sub-aspect research: ${r2_file}

2. Identify knowledge gaps from R1 and R2 that block implementation
3. Formulate 2-4 research questions (RQs) that address these gaps
4. Each RQ must be:
   - **Specific**: Clear scope, not vague
   - **Falsifiable**: Can be answered yes/no or with measurable data
   - **Actionable**: Answering it directly informs implementation
   - **Scoped**: Answerable within the research time budget

5. Write to: ${output_file}

   Structure:

   # R3: Research Questions
   **Idea**: ${IDEA_ID}
   **Date**: $(date +%Y-%m-%d)
   **Time-box**: ${R3_MINUTES} minutes

   ## Knowledge Gaps Identified

   From R1 (Prior Art):
   - [Gap 1]
   - [Gap 2]

   From R2 (Sub-Aspects):
   - [Gap 3]
   - [Gap 4]

   ## Research Questions

   ### RQ1: [Question in interrogative form]
   **Type**: [Empirical / Theoretical / Engineering / Comparative]
   **Why it matters**: [How answering this unblocks implementation]
   **Hypothesis**: [Your expected answer, to be validated]
   **Validation approach**: [How you will answer this - experiment, proof, prototype, comparison]
   **Success criteria**: [What constitutes a satisfactory answer]

   ### RQ2: [Question]
   [Same structure...]

   ## RQ Dependencies
   [If any RQ depends on another being answered first, note it here]

   ## Estimated Effort per RQ
   | RQ | Type | Estimated Time | Priority |
   |----|------|----------------|----------|
   | RQ1 | ... | ... | High/Medium/Low |

Good research questions are the foundation of good research. Be precise." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -s "$output_file" ]]; then
        log "ERROR: R3 did not produce output"
        return 1
    fi
    log "R3 complete: $output_file"
}

# =============================================================================
# R4: Deep Literature Review
# =============================================================================
run_r4() {
    local output_file="$WORK_DIR/r4-literature-review.md"
    local r3_file="$WORK_DIR/r3-research-questions.md"

    log "R4: Deep Literature Review (${R4_MINUTES} min)"
    touch "$output_file"

    timeout ${R4_MINUTES}m claude --permission-mode acceptEdits \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write,WebSearch" \
        -p "You are conducting Phase R4: Deep Literature Review for idea ${IDEA_ID}.

## Goal
Comprehensive literature review focused on answering the research questions from R3.

## Instructions

1. First, read the research questions using the Read tool: ${r3_file}

2. For EACH research question, conduct targeted literature search:
   - Academic databases: arXiv, Google Scholar, ACM DL, IEEE Xplore
   - Search for: theoretical foundations, methodologies, empirical results
   - Find contradictory findings and debates in the field

3. Aim for 10+ relevant sources total (not per RQ)

4. Write to: ${output_file}

   Structure:

   # R4: Literature Review
   **Idea**: ${IDEA_ID}
   **Date**: $(date +%Y-%m-%d)
   **Time-box**: ${R4_MINUTES} minutes

   ## Literature Review by Research Question

   ### RQ1: [Restate the question]

   #### Theoretical Foundations
   - [Key theory/framework 1]: [explanation, citation]

   #### Relevant Empirical Studies
   | Study | Method | Key Finding | Relevance |
   |-------|--------|-------------|-----------|
   | Author (Year) | ... | ... | ... |

   #### Methodologies Used in Related Work
   - [Method 1]: used by [citations], pros/cons

   #### Contradictions and Debates
   - [Topic]: [Author A] argues X, while [Author B] argues Y

   #### Implications for Our Research
   [How this literature informs how we should answer RQ1]

   ### RQ2: [Restate]
   [Same structure...]

   ## Bibliography
   [1] Author, A. (Year). Title. *Venue*, pages. URL/DOI

   ## Summary of Key Insights
   - [Insight 1]

   ## Identified Methodological Approaches
   For answering our RQs, the literature suggests:
   - RQ1: [recommended approach]

Quality matters: cite properly, summarize accurately, note limitations." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -s "$output_file" ]]; then
        log "ERROR: R4 did not produce output"
        return 1
    fi
    log "R4 complete: $output_file"
}

# =============================================================================
# R5: Research Execution
# =============================================================================
run_r5() {
    local output_file="$WORK_DIR/r5-research-findings.md"
    local r3_file="$WORK_DIR/r3-research-questions.md"
    local r4_file="$WORK_DIR/r4-literature-review.md"

    log "R5: Research Execution (${R5_MINUTES} min)"
    touch "$output_file"
    mkdir -p "$WORK_DIR/experiments"

    timeout ${R5_MINUTES}m claude --permission-mode acceptEdits \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "mcp__idea-pool__read_idea,mcp__nano-banana__generate,mcp__nano-banana__get_budget,mcp__nano-banana__get_models,Read,Write,Edit,Bash,Glob,Grep,WebSearch" \
        -p "You are conducting Phase R5: Research Execution for idea ${IDEA_ID}.

## Goal
Answer the research questions through empirical investigation: experiments, proofs, prototypes, or comparisons.

## CRITICAL: Language Requirement
**ALWAYS use Python** for all code, experiments, prototypes, and scripts.
Do NOT use TypeScript, JavaScript, or any other language.
Python 3.11+ is the target runtime.

## Instructions

1. First, read the required context files:
   - Use the Read tool to read research questions: ${r3_file}
   - Use the Read tool to read literature review: ${r4_file}
   - Experiments directory for your code: ${WORK_DIR}/experiments/

2. For EACH research question, execute the appropriate validation approach:

| RQ Type | Approach |
|---------|----------|
| Empirical | Design experiment → Collect data → Statistical analysis |
| Theoretical | Formal proof or mathematical derivation |
| Engineering | Build minimal prototype → Benchmark → Measure |
| Comparative | Systematic comparison with defined criteria |

3. For each RQ:
   - **Setup**: Define methodology, tools, data sources, success criteria
   - **Execution**: Run the experiment/proof/prototype
   - **Results**: Raw data, measurements, observations
   - **Evaluation**: Analyze against hypotheses
   - **Discussion**: Interpret, note limitations

4. Write code/scripts to: ${WORK_DIR}/experiments/
5. Write findings to: ${output_file}

Structure:

# R5: Research Findings
**Idea**: ${IDEA_ID}
**Date**: $(date +%Y-%m-%d)
**Time-box**: ${R5_MINUTES} minutes

## Research Execution Summary

| RQ | Approach | Result | Confidence |
|----|----------|--------|------------|
| RQ1 | ... | Supported/Refuted/Inconclusive | High/Medium/Low |

## Detailed Findings

### RQ1: [Restate question]

#### Methodology
**Approach**: [Empirical/Theoretical/Engineering/Comparative]
**Design**: [Describe the experiment/proof/prototype design]

#### Execution
[Describe what you actually did]

#### Raw Results
[Present data, measurements, proof steps, benchmark numbers]

#### Analysis
**Hypothesis**: [restate from R3]
**Finding**: [Supported / Refuted / Partially Supported / Inconclusive]
**Evidence**: [Summarize the key evidence]

#### Discussion
**Interpretation**: [What does this mean for the idea?]
**Limitations**: [Threats to validity, scope limitations]

## Artifacts Produced
| File | Description |
|------|-------------|
| experiments/... | ... |

This is the core of the research. Be rigorous, honest about limitations, and let data drive conclusions." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -s "$output_file" ]]; then
        log "ERROR: R5 did not produce output"
        return 1
    fi
    log "R5 complete: $output_file"
}

# =============================================================================
# R6: Synthesis & Conclusion
# =============================================================================
run_r6() {
    local output_file="$WORK_DIR/r6-research-synthesis.md"

    log "R6: Synthesis & Conclusion (${R6_MINUTES} min)"
    touch "$output_file"

    timeout ${R6_MINUTES}m claude --permission-mode acceptEdits \
        --max-budget-usd "$MAX_BUDGET_USD" \
        --allowedTools "Read,Write" \
        -p "You are conducting Phase R6: Synthesis & Conclusion for idea ${IDEA_ID}.

## Goal
Consolidate all research findings into actionable conclusions and a go/no-go decision.

## Instructions

1. First, use the Read tool to read ALL previous phase outputs:
   - ${WORK_DIR}/r1-prior-art-scan.md
   - ${WORK_DIR}/r2-sub-aspect-research.md
   - ${WORK_DIR}/r3-research-questions.md
   - ${WORK_DIR}/r4-literature-review.md
   - ${WORK_DIR}/r5-research-findings.md

2. Synthesize all research into a final report with clear conclusions.

3. Write to: ${output_file}

Structure:

# R6: Research Synthesis
**Idea**: ${IDEA_ID}
**Date**: $(date +%Y-%m-%d)

## Executive Summary
[2-3 paragraph summary of the entire research effort and conclusions]

## Research Questions: Answers

| RQ | Question | Answer | Confidence | Implication |
|----|----------|--------|------------|-------------|
| RQ1 | ... | ... | High/Med/Low | ... |

## Key Findings

### Finding 1: [Title]
**Evidence**: [From which phase/RQ]
**Implication for Implementation**: [How this affects what we build]

## Revised Understanding
[How has our understanding of the idea changed through research?]

## Implementation Recommendations

### Recommended Approach
[Describe the approach that research supports]

### Approaches to Avoid
[What research suggests will NOT work]

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ... | H/M/L | H/M/L | ... |

## Go/No-Go Decision

**Recommendation**: [PROCEED / INVALIDATE / PARK]

**Rationale**:
[Clear explanation of why this recommendation]

---

Final output: State ONLY one word on the last line: proceed, invalidate, or park" 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -s "$output_file" ]]; then
        log "ERROR: R6 did not produce output"
        return 1
    fi
    log "R6 complete: $output_file"

    # Extract decision
    local decision
    decision=$(tail -5 "$output_file" | grep -iE '^(proceed|invalidate|park)' | head -1 | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')
    echo "$decision"
}

# =============================================================================
# Main
# =============================================================================

log "=========================================="
log "Starting R3-R6 research phases"
log "=========================================="

run_r3 || { log "R3 failed"; exit 1; }
log "Pausing 5s before R4..."
sleep 5

run_r4 || { log "R4 failed"; exit 1; }
log "Pausing 5s before R5..."
sleep 5

run_r5 || { log "R5 failed"; exit 1; }
log "Pausing 5s before R6..."
sleep 5

decision=$(run_r6) || { log "R6 failed"; exit 1; }

log "=========================================="
log "Research complete! Decision: $decision"
log "=========================================="
log "Outputs in: $WORK_DIR"
ls -la "$WORK_DIR"/*.md
