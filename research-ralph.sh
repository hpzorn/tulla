#!/bin/bash
# research-ralph.sh - Research-First Ralph: Autonomous Idea-to-Implementation Loop
#
# Extends Geoffrey Huntley's Ralph Wiggum loop with:
# - PhD-level research protocol (6 phases, ~2.5 hours)
# - Idea pool integration for continuous multi-task processing
# - PRD-driven implementation grounded in research
# - Lifecycle state tracking via idea file annotations
#
# Research Protocol Phases:
#   R1: Prior Art Scan        (15 min) - Novelty check
#   R2: Sub-Aspect Research   (20 min) - Component-level findings
#   R3: RQ Formulation        (15 min) - Define 2-4 research questions
#   R4: Deep Literature Review (30 min) - Comprehensive review per RQ
#   R5: Research Execution    (60 min) - Experiments/proofs/prototypes
#   R6: Synthesis             (15 min) - Conclusions + go/no-go
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
WORK_DIR="${WORK_DIR:-$SCRIPT_DIR/work}"
SLEEP_INTERVAL="${SLEEP_INTERVAL:-3600}"
MAX_IMPLEMENTATION_RETRIES="${MAX_IMPLEMENTATION_RETRIES:-3}"
DRY_RUN="${DRY_RUN:-false}"
SINGLE_RUN="${SINGLE_RUN:-false}"
SPECIFIC_IDEA="${SPECIFIC_IDEA:-}"
INTERACTIVE="${INTERACTIVE:-false}"

# PhD-Level Research Protocol Time Boxes (in minutes)
R1_PRIOR_ART_MINUTES="${R1_PRIOR_ART_MINUTES:-15}"
R2_SUB_ASPECT_MINUTES="${R2_SUB_ASPECT_MINUTES:-20}"
R3_RQ_FORMULATION_MINUTES="${R3_RQ_FORMULATION_MINUTES:-15}"
R4_LITERATURE_REVIEW_MINUTES="${R4_LITERATURE_REVIEW_MINUTES:-30}"
R5_RESEARCH_EXECUTION_MINUTES="${R5_RESEARCH_EXECUTION_MINUTES:-60}"
R6_SYNTHESIS_MINUTES="${R6_SYNTHESIS_MINUTES:-15}"

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
# Lifecycle Management
# =============================================================================

# Valid states: seed, backlog, researching, researched, invalidated, parked,
#               decomposing, scoped, implementing, blocked, completed, failed

set_lifecycle() {
    local idea_id="$1"
    local new_state="$2"
    local reason="${3:-}"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would set lifecycle of idea $idea_id to $new_state"
        return 0
    fi

    log_state "Setting idea $idea_id lifecycle to: $new_state"

    local reason_arg=""
    if [[ -n "$reason" ]]; then
        reason_arg=", reason: $reason"
    fi

    claude --print "Use mcp__idea-pool__set_lifecycle with identifier '$idea_id' and new_state '$new_state'${reason_arg}. Return only 'done' or 'error'." 2>/dev/null || log_warn "Failed to set lifecycle"
}

# =============================================================================
# Phase 1: Extract (Idea Selection)
# =============================================================================

extract_idea() {
    log_phase "1. EXTRACT - Selecting idea to process"

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

    # List ideas and select one that hasn't been implemented yet
    local idea
    idea=$(claude --print "
Use mcp__idea-pool__list_ideas to see available ideas.
Look for ideas that have lifecycle: backlog in their frontmatter.
Avoid ideas that are already in: researching, implementing, completed, failed, invalidated, or parked.

Return ONLY the idea number (e.g., '13'), nothing else.
If no suitable ideas found, return 'NONE'.
" 2>/dev/null || echo "ERROR")

    idea=$(echo "$idea" | tr -d '[:space:]')

    if [[ "$idea" == "NONE" ]] || [[ "$idea" == "ERROR" ]] || [[ -z "$idea" ]]; then
        log_warn "No suitable ideas found"
        return 1
    fi

    log_info "Selected idea: $idea"
    echo "$idea"
}

# =============================================================================
# Phase 2: PhD-Level Research Protocol
# =============================================================================
#
# R1: Prior Art Scan (15 min)        → novelty check
# R2: Sub-Aspect Research (20 min)   → component-level findings
# R3: RQ Formulation (15 min)        → 2-4 research questions
# R4: Deep Literature Review (30 min)→ comprehensive review per RQ
# R5: Research Execution (60 min)    → experiments/proofs/prototypes
# R6: Synthesis (15 min)             → conclusions + go/no-go
# =============================================================================

# Helper: get timeout command
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

# -----------------------------------------------------------------------------
# R1: Prior Art Scan
# -----------------------------------------------------------------------------
run_r1_prior_art_scan() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local output_file="$idea_work_dir/r1-prior-art-scan.md"

    log_info "R1: Prior Art Scan (${R1_PRIOR_ART_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run prior art scan"
        echo "novel"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$R1_PRIOR_ART_MINUTES")
    local research_date
    research_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --allowedTools "mcp__idea-pool__read_idea,Write,WebSearch" \
        -p "You are conducting Phase R1: Prior Art Scan for idea ${idea_id}.

## Goal
Determine if this idea is NOVEL or a DERIVATIVE of existing work.

## Instructions

1. Read the idea: use mcp__idea-pool__read_idea with identifier ${idea_id}

2. Search for existing implementations:
   - Use WebSearch to find: existing tools, products, libraries, papers
   - Search for the core concept + synonyms
   - Check GitHub, academic databases, product directories

3. Write findings to: ${output_file}

   Structure:

   # R1: Prior Art Scan
   **Idea**: ${idea_id}
   **Date**: ${research_date}
   **Time-box**: ${R1_PRIOR_ART_MINUTES} minutes

   ## Search Queries Used
   - [list actual searches performed]

   ## Existing Implementations Found
   | Name | Type | URL | Similarity | Notes |
   |------|------|-----|------------|-------|
   | ... | tool/paper/product | ... | high/medium/low | ... |

   ## Novelty Assessment

   ### What Already Exists
   [Describe existing solutions]

   ### What Is Novel About This Idea
   [Describe unique aspects, if any]

   ### Verdict
   **[NOVEL / PARTIAL / DERIVATIVE]**

   - NOVEL: No existing solution covers this; proceed
   - PARTIAL: Some aspects exist, some are new; proceed with focus on novel parts
   - DERIVATIVE: This is essentially a copy of [X]; recommend invalidation

4. Output ONLY one word on the final line: novel, partial, or derivative

Be thorough but respect the time-box. Quality over quantity." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "R1 did not produce $output_file"
        return 1
    fi

    # Extract verdict
    local verdict
    verdict=$(tail -5 "$output_file" | grep -iE '^(novel|partial|derivative)' | head -1 | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

    if [[ -z "$verdict" ]]; then
        verdict="novel"  # Default to proceed
    fi

    log_info "R1 verdict: $verdict"
    pause_if_interactive "R1-prior-art"
    echo "$verdict"
}

# -----------------------------------------------------------------------------
# R2: Sub-Aspect Research
# -----------------------------------------------------------------------------
run_r2_sub_aspect_research() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local output_file="$idea_work_dir/r2-sub-aspect-research.md"
    local r1_file="$idea_work_dir/r1-prior-art-scan.md"

    log_info "R2: Sub-Aspect Research (${R2_SUB_ASPECT_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run sub-aspect research"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$R2_SUB_ASPECT_MINUTES")
    local research_date
    research_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write,WebSearch" \
        -p "You are conducting Phase R2: Sub-Aspect Research for idea ${idea_id}.

## Goal
Decompose the idea into components and find existing research on each.

## Context
- Read the idea: mcp__idea-pool__read_idea with identifier ${idea_id}
- Read prior art scan: ${r1_file}

## Instructions

1. Decompose the idea into 3-6 distinct sub-aspects/components
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

3. Write findings to: ${output_file}

   Structure:

   # R2: Sub-Aspect Research
   **Idea**: ${idea_id}
   **Date**: ${research_date}
   **Time-box**: ${R2_SUB_ASPECT_MINUTES} minutes

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

Cite sources properly: Author (Year). Title. Venue/URL." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "R2 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "R2-sub-aspects"
    return 0
}

# -----------------------------------------------------------------------------
# R3: Research Question Formulation
# -----------------------------------------------------------------------------
run_r3_rq_formulation() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local output_file="$idea_work_dir/r3-research-questions.md"
    local r1_file="$idea_work_dir/r1-prior-art-scan.md"
    local r2_file="$idea_work_dir/r2-sub-aspect-research.md"

    log_info "R3: Research Question Formulation (${R3_RQ_FORMULATION_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would formulate research questions"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$R3_RQ_FORMULATION_MINUTES")
    local research_date
    research_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write" \
        -p "You are conducting Phase R3: Research Question Formulation for idea ${idea_id}.

## Goal
Define 2-4 precise, falsifiable research questions that must be answered to realize this idea.

## Context
- Read the idea: mcp__idea-pool__read_idea with identifier ${idea_id}
- Read prior art scan: ${r1_file}
- Read sub-aspect research: ${r2_file}

## Instructions

1. Identify knowledge gaps from R1 and R2 that block implementation
2. Formulate 2-4 research questions (RQs) that address these gaps
3. Each RQ must be:
   - **Specific**: Clear scope, not vague
   - **Falsifiable**: Can be answered yes/no or with measurable data
   - **Actionable**: Answering it directly informs implementation
   - **Scoped**: Answerable within the research time budget

4. Write to: ${output_file}

   Structure:

   # R3: Research Questions
   **Idea**: ${idea_id}
   **Date**: ${research_date}
   **Time-box**: ${R3_RQ_FORMULATION_MINUTES} minutes

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

   ### RQ3: [Question]
   [Same structure...]

   ## RQ Dependencies
   [If any RQ depends on another being answered first, note it here]

   ## Estimated Effort per RQ
   | RQ | Type | Estimated Time | Priority |
   |----|------|----------------|----------|
   | RQ1 | ... | ... | High/Medium/Low |

Good research questions are the foundation of good research. Be precise." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "R3 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "R3-research-questions"
    return 0
}

# -----------------------------------------------------------------------------
# R4: Deep Literature Review
# -----------------------------------------------------------------------------
run_r4_deep_literature_review() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local output_file="$idea_work_dir/r4-literature-review.md"
    local r3_file="$idea_work_dir/r3-research-questions.md"

    log_info "R4: Deep Literature Review (${R4_LITERATURE_REVIEW_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run deep literature review"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$R4_LITERATURE_REVIEW_MINUTES")
    local research_date
    research_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write,WebSearch" \
        -p "You are conducting Phase R4: Deep Literature Review for idea ${idea_id}.

## Goal
Comprehensive literature review focused on answering the research questions from R3.

## Context
- Read the research questions: ${r3_file}

## Instructions

1. For EACH research question, conduct targeted literature search:
   - Academic databases: arXiv, Google Scholar, ACM DL, IEEE Xplore
   - Search for: theoretical foundations, methodologies, empirical results
   - Find contradictory findings and debates in the field

2. Aim for 10+ relevant sources total (not per RQ)

3. Write to: ${output_file}

   Structure:

   # R4: Literature Review
   **Idea**: ${idea_id}
   **Date**: ${research_date}
   **Time-box**: ${R4_LITERATURE_REVIEW_MINUTES} minutes

   ## Literature Review by Research Question

   ### RQ1: [Restate the question]

   #### Theoretical Foundations
   - [Key theory/framework 1]: [explanation, citation]
   - [Key theory/framework 2]: [explanation, citation]

   #### Relevant Empirical Studies
   | Study | Method | Key Finding | Relevance |
   |-------|--------|-------------|-----------|
   | Author (Year) | ... | ... | ... |

   #### Methodologies Used in Related Work
   - [Method 1]: used by [citations], pros/cons
   - [Method 2]: used by [citations], pros/cons

   #### Contradictions and Debates
   - [Topic]: [Author A] argues X, while [Author B] argues Y

   #### Implications for Our Research
   [How this literature informs how we should answer RQ1]

   ### RQ2: [Restate]
   [Same structure...]

   ## Bibliography

   [1] Author, A. (Year). Title. *Venue*, pages. URL/DOI
   [2] Author, B. (Year). Title. *Venue*, pages. URL/DOI
   ...

   ## Summary of Key Insights
   - [Insight 1]
   - [Insight 2]
   ...

   ## Identified Methodological Approaches
   For answering our RQs, the literature suggests:
   - RQ1: [recommended approach based on literature]
   - RQ2: [recommended approach]
   ...

Quality matters: cite properly, summarize accurately, note limitations." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "R4 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "R4-literature-review"
    return 0
}

# -----------------------------------------------------------------------------
# R5: Research Execution
# -----------------------------------------------------------------------------
run_r5_research_execution() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local output_file="$idea_work_dir/r5-research-findings.md"
    local r3_file="$idea_work_dir/r3-research-questions.md"
    local r4_file="$idea_work_dir/r4-literature-review.md"

    log_info "R5: Research Execution (${R5_RESEARCH_EXECUTION_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would execute research"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$R5_RESEARCH_EXECUTION_MINUTES")
    local research_date
    research_date=$(date +%Y-%m-%d)

    # Create experiments subdirectory
    mkdir -p "$idea_work_dir/experiments"

    $timeout_cmd claude \
        --allowedTools "mcp__idea-pool__read_idea,Read,Write,Edit,Bash,Glob,Grep,WebSearch" \
        -p "You are conducting Phase R5: Research Execution for idea ${idea_id}.

## Goal
Answer the research questions through empirical investigation: experiments, proofs, prototypes, or comparisons.

## Context
- Read research questions: ${r3_file}
- Read literature review: ${r4_file}
- Experiments directory: ${idea_work_dir}/experiments/

## Instructions

For EACH research question, execute the appropriate validation approach:

| RQ Type | Approach |
|---------|----------|
| Empirical | Design experiment → Collect data → Statistical analysis |
| Theoretical | Formal proof or mathematical derivation |
| Engineering | Build minimal prototype → Benchmark → Measure |
| Comparative | Systematic comparison with defined criteria |

For each RQ:
1. **Setup**: Define methodology, tools, data sources, success criteria
2. **Execution**: Run the experiment/proof/prototype
3. **Results**: Raw data, measurements, observations
4. **Evaluation**: Analyze against hypotheses
5. **Discussion**: Interpret, note limitations

Write code/scripts to: ${idea_work_dir}/experiments/
Write findings to: ${output_file}

Structure:

# R5: Research Findings
**Idea**: ${idea_id}
**Date**: ${research_date}
**Time-box**: ${R5_RESEARCH_EXECUTION_MINUTES} minutes

## Research Execution Summary

| RQ | Approach | Result | Confidence |
|----|----------|--------|------------|
| RQ1 | ... | Supported/Refuted/Inconclusive | High/Medium/Low |
| RQ2 | ... | ... | ... |

## Detailed Findings

### RQ1: [Restate question]

#### Methodology
**Approach**: [Empirical/Theoretical/Engineering/Comparative]
**Design**: [Describe the experiment/proof/prototype design]
**Tools Used**: [List tools, libraries, datasets]
**Success Criteria**: [What would constitute support/refutation]

#### Execution
[Describe what you actually did]

**Code/Artifacts**:
- \`experiments/rq1-[name].py\` - [description]
- \`experiments/rq1-data.json\` - [description]

#### Raw Results
[Present data, measurements, proof steps, benchmark numbers]

\`\`\`
[Include actual output, data, or proof]
\`\`\`

#### Analysis
**Hypothesis**: [restate from R3]
**Finding**: [Supported / Refuted / Partially Supported / Inconclusive]
**Evidence**: [Summarize the key evidence]
**Statistical Significance**: [if applicable: p-value, confidence interval]

#### Discussion
**Interpretation**: [What does this mean for the idea?]
**Limitations**: [Threats to validity, scope limitations]
**Implications**: [How this affects implementation approach]

### RQ2: [Restate]
[Same structure...]

## Cross-RQ Analysis
[Are there interactions between findings? Do answers to one RQ affect others?]

## Artifacts Produced
| File | Description |
|------|-------------|
| experiments/... | ... |

This is the core of the research. Be rigorous, honest about limitations, and let data drive conclusions." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "R5 did not produce $output_file"
        return 1
    fi

    pause_if_interactive "R5-research-execution"
    return 0
}

# -----------------------------------------------------------------------------
# R6: Synthesis & Conclusion
# -----------------------------------------------------------------------------
run_r6_synthesis() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local output_file="$idea_work_dir/r6-research-synthesis.md"

    log_info "R6: Synthesis & Conclusion (${R6_SYNTHESIS_MINUTES} min time-box)"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would synthesize research"
        echo "proceed"
        return 0
    fi

    local timeout_cmd
    timeout_cmd=$(get_timeout_cmd "$R6_SYNTHESIS_MINUTES")
    local research_date
    research_date=$(date +%Y-%m-%d)

    $timeout_cmd claude \
        --allowedTools "Read,Write" \
        -p "You are conducting Phase R6: Synthesis & Conclusion for idea ${idea_id}.

## Goal
Consolidate all research findings into actionable conclusions and a go/no-go decision.

## Context - Read all previous phases:
- ${idea_work_dir}/r1-prior-art-scan.md
- ${idea_work_dir}/r2-sub-aspect-research.md
- ${idea_work_dir}/r3-research-questions.md
- ${idea_work_dir}/r4-literature-review.md
- ${idea_work_dir}/r5-research-findings.md

## Instructions

Synthesize all research into a final report with clear conclusions.

Write to: ${output_file}

Structure:

# R6: Research Synthesis
**Idea**: ${idea_id}
**Date**: ${research_date}
**Research Duration**: ~${R1_PRIOR_ART_MINUTES}+${R2_SUB_ASPECT_MINUTES}+${R3_RQ_FORMULATION_MINUTES}+${R4_LITERATURE_REVIEW_MINUTES}+${R5_RESEARCH_EXECUTION_MINUTES}+${R6_SYNTHESIS_MINUTES} minutes

## Executive Summary
[2-3 paragraph summary of the entire research effort and conclusions]

## Research Questions: Answers

| RQ | Question | Answer | Confidence | Implication |
|----|----------|--------|------------|-------------|
| RQ1 | ... | ... | High/Med/Low | ... |
| RQ2 | ... | ... | ... | ... |

## Key Findings

### Finding 1: [Title]
**Evidence**: [From which phase/RQ]
**Implication for Implementation**: [How this affects what we build]

### Finding 2: [Title]
...

## Revised Understanding
[How has our understanding of the idea changed through research?]

**Original Idea**: [Brief restatement]
**Refined Understanding**: [What we now know]
**Pivots Needed**: [Any significant changes to the original concept]

## Implementation Recommendations

Based on this research:

### Recommended Approach
[Describe the approach that research supports]

### Approaches to Avoid
[What research suggests will NOT work]

### Open Questions for Implementation
[Questions that remain but can be resolved during implementation]

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ... | High/Med/Low | High/Med/Low | ... |

## Confidence Assessment
**Overall Confidence**: [High / Medium / Low]
**Justification**: [Why this confidence level]

## Go/No-Go Decision

**Recommendation**: [PROCEED / INVALIDATE / PARK]

**Rationale**:
[Clear explanation of why this recommendation]

**If PROCEED**:
- The idea is feasible because: [reasons]
- Key success factors: [list]
- First implementation priority: [what to build first]

**If INVALIDATE**:
- The idea should be abandoned because: [reasons]
- The fundamental flaw is: [description]
- Alternative directions: [if any]

**If PARK**:
- Human decision needed on: [specific question]
- Options to consider: [list options]

## References
[Consolidated bibliography from all phases]

---

Final output: State ONLY one word on the last line: proceed, invalidate, or park" 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$output_file" ]]; then
        log_error "R6 did not produce $output_file"
        return 1
    fi

    # Extract final decision
    local decision
    decision=$(tail -5 "$output_file" | grep -iE '^(proceed|invalidate|park)' | head -1 | tr '[:upper:]' '[:lower:]' | tr -d '[:space:]')

    if [[ -z "$decision" ]]; then
        decision="proceed"
    fi

    log_info "R6 decision: $decision"
    pause_if_interactive "R6-synthesis"
    echo "$decision"
}

# -----------------------------------------------------------------------------
# Main Research Protocol Orchestrator
# -----------------------------------------------------------------------------
run_research_protocol() {
    local idea_id="$1"
    local idea_work_dir="$2"

    log_phase "2. RESEARCH PROTOCOL - PhD-Level Investigation"
    log_info "Total estimated time: ~$((R1_PRIOR_ART_MINUTES + R2_SUB_ASPECT_MINUTES + R3_RQ_FORMULATION_MINUTES + R4_LITERATURE_REVIEW_MINUTES + R5_RESEARCH_EXECUTION_MINUTES + R6_SYNTHESIS_MINUTES)) minutes"

    # R1: Prior Art Scan
    local r1_verdict
    r1_verdict=$(run_r1_prior_art_scan "$idea_id" "$idea_work_dir")

    if [[ "$r1_verdict" == "derivative" ]]; then
        log_warn "R1 found idea is derivative of existing work"
        set_lifecycle "$idea_id" "invalidated" "Prior art scan found idea is derivative"
        return 1
    fi

    # R2: Sub-Aspect Research
    if ! run_r2_sub_aspect_research "$idea_id" "$idea_work_dir"; then
        log_error "R2 failed"
        return 1
    fi

    # R3: Research Question Formulation
    if ! run_r3_rq_formulation "$idea_id" "$idea_work_dir"; then
        log_error "R3 failed"
        return 1
    fi

    # R4: Deep Literature Review
    if ! run_r4_deep_literature_review "$idea_id" "$idea_work_dir"; then
        log_error "R4 failed"
        return 1
    fi

    # R5: Research Execution
    if ! run_r5_research_execution "$idea_id" "$idea_work_dir"; then
        log_error "R5 failed"
        return 1
    fi

    # R6: Synthesis & Conclusion
    local final_decision
    final_decision=$(run_r6_synthesis "$idea_id" "$idea_work_dir")

    case "$final_decision" in
        proceed)
            log_info "Research protocol complete: PROCEED to implementation"
            # Append synthesis to idea
            claude --print "
Use mcp__idea-pool__append_to_idea to append to idea '$idea_id':

---
## Research Protocol Complete ($(date +%Y-%m-%d))

Research artifacts in: $idea_work_dir

**Decision**: PROCEED

See r6-research-synthesis.md for full conclusions.
---
" 2>/dev/null || true
            return 0
            ;;
        invalidate)
            log_warn "Research protocol concluded: INVALIDATE"
            set_lifecycle "$idea_id" "invalidated" "Research protocol concluded idea is not viable"
            return 1
            ;;
        park)
            log_warn "Research protocol concluded: PARK for human decision"
            set_lifecycle "$idea_id" "parked" "Research protocol requires human decision"
            return 1
            ;;
        *)
            log_warn "Unknown decision: $final_decision, defaulting to proceed"
            return 0
            ;;
    esac
}

# =============================================================================
# Phase 3: PRD Creation
# =============================================================================

create_prd() {
    local idea_id="$1"
    local idea_work_dir="$2"

    log_phase "3. PRD - Creating Product Requirements Document"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create PRD for idea $idea_id"
        return 0
    fi

    local prd_file="$idea_work_dir/prd.md"

    claude \
        --allowedTools "mcp__idea-pool__read_idea,mcp__idea-pool__append_to_idea,Read,Write" \
        -p "Create a PRD (Product Requirements Document) for idea ${idea_id}.

## Context

You have access to PhD-level research conducted in 6 phases. Read ALL of these:

1. **Prior Art Scan**: ${idea_work_dir}/r1-prior-art-scan.md
2. **Sub-Aspect Research**: ${idea_work_dir}/r2-sub-aspect-research.md
3. **Research Questions**: ${idea_work_dir}/r3-research-questions.md
4. **Literature Review**: ${idea_work_dir}/r4-literature-review.md
5. **Research Findings**: ${idea_work_dir}/r5-research-findings.md
6. **Research Synthesis**: ${idea_work_dir}/r6-research-synthesis.md

Also read the original idea: mcp__idea-pool__read_idea with identifier ${idea_id}

## Instructions

Create a comprehensive PRD grounded in the research findings. Write to: ${prd_file}

Structure:

# PRD: [Title from idea]

## Executive Summary
[2-3 sentences: what we are building and why]

## Problem Statement
[Clear description of the problem, grounded in research findings]

## Research Foundation

### Key Research Findings
[Summarize the most important findings from R5/R6 that inform this PRD]

### Research Questions Answered
| RQ | Answer | Confidence | Impact on Design |
|----|--------|------------|------------------|
| RQ1 | ... | ... | ... |

### Prior Art Considered
[What existing solutions were found, why we are still proceeding]

## Proposed Solution

### High-Level Approach
[Describe the solution, citing research that supports this approach]

### Architecture
[System components, data flow, key abstractions]

### Key Design Decisions
| Decision | Rationale | Research Support |
|----------|-----------|------------------|
| ... | ... | From RQ#/finding |

## Success Criteria
- [ ] Criterion 1 [specific, measurable, tied to research]
- [ ] Criterion 2
- [ ] Criterion 3
- [ ] Criterion 4
- [ ] Criterion 5
(Max 5 criteria, each must be testable)

## Non-Goals
[What we are explicitly NOT doing in this implementation]
- Not doing X because research showed Y
- Deferring Z to future work

## Technical Approach

### Implementation Plan
1. [Phase 1]: [description]
2. [Phase 2]: [description]
...

### Technology Choices
| Component | Choice | Rationale |
|-----------|--------|-----------|
| ... | ... | ... |

### Key Algorithms/Methods
[Describe any specific algorithms, referencing literature review]

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation | Research Basis |
|------|------------|--------|------------|----------------|
| ... | H/M/L | H/M/L | ... | From RQ#/lit review |

## Open Questions
[Questions that could not be fully resolved in research, to be addressed during implementation]

## Estimated Complexity
**[S/M/L]**: [Justification based on research findings]

## References
[Key papers/sources from the literature review that inform this PRD]

---

After writing the PRD, append a summary to the idea using mcp__idea-pool__append_to_idea.

The PRD must be actionable and grounded in research. Avoid speculation not supported by findings." 2>&1 | tee -a "$LOG_FILE"

    if [[ ! -f "$prd_file" ]]; then
        log_error "PRD creation failed - $prd_file not created"
        return 1
    fi

    log_info "PRD created: $prd_file"
    pause_if_interactive "prd"
    return 0
}

# =============================================================================
# Phase 4: Implementation (Classic Ralph)
# =============================================================================

run_implementation() {
    local idea_id="$1"
    local idea_work_dir="$2"

    log_phase "4. IMPLEMENT - Classic Ralph loop"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would run implementation loop"
        return 0
    fi

    local prd_file="$idea_work_dir/prd.md"
    local done_file="$idea_work_dir/DONE"

    if [[ ! -f "$prd_file" ]]; then
        log_error "PRD not found at $prd_file"
        return 1
    fi

    local retries=0
    local prd_content
    prd_content=$(cat "$prd_file")

    cd "$idea_work_dir"

    while [[ $retries -lt $MAX_IMPLEMENTATION_RETRIES ]]; do
        ((retries++))
        log_info "Implementation attempt $retries/$MAX_IMPLEMENTATION_RETRIES"

        claude \
            --allowedTools "Read,Write,Edit,Bash,Glob,Grep" \
            -p "## Implementation Task

You are implementing a PRD. Work in the current directory: ${idea_work_dir}

## PRD Content:
${prd_content}

## Instructions

1. Review the PRD and any existing implementation progress
2. Implement the solution - create files, write code, etc.
3. Test your implementation
4. Check each success criterion

## Completion

When ALL success criteria from the PRD are met:
1. Create a file named DONE containing:
   - Summary of what was implemented
   - List of files created/modified
   - Any follow-up tasks for later
2. The presence of DONE file signals completion

If you cannot complete (blocked/stuck):
- Document the issue in a file named BLOCKED with explanation
- We will retry or escalate

<promise>ALL_PRD_ITEMS_COMPLETE</promise>" 2>&1 | tee -a "$LOG_FILE"

        if [[ -f "$done_file" ]]; then
            log_info "Implementation complete! DONE file created."
            cd "$SCRIPT_DIR"
            return 0
        fi

        if [[ -f "$idea_work_dir/BLOCKED" ]]; then
            log_warn "Implementation blocked: $(cat "$idea_work_dir/BLOCKED")"
            cd "$SCRIPT_DIR"
            return 1
        fi

        log_info "DONE file not found, continuing loop..."
        sleep 2
    done

    cd "$SCRIPT_DIR"
    log_error "Implementation failed after $MAX_IMPLEMENTATION_RETRIES attempts"
    return 1
}

# =============================================================================
# Phase 5: Mark Complete
# =============================================================================

mark_complete() {
    local idea_id="$1"
    local idea_work_dir="$2"
    local status="$3"

    log_phase "5. COMPLETE - Recording status: $status"

    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would mark idea $idea_id as $status"
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
$(cat "$idea_work_dir/DONE" 2>/dev/null || echo "No DONE file")
EOF

    # Append completion status to the idea
    claude --print "
Use mcp__idea-pool__append_to_idea to append to idea '$idea_id':

---
## Implementation Status ($(date +%Y-%m-%d))

**Status**: $status
**Work Directory**: $idea_work_dir

$(cat "$idea_work_dir/DONE" 2>/dev/null || echo "See work directory for details")
---
" 2>/dev/null || log_warn "Could not update idea with completion status"

    log_info "Completion recorded: $status"
}

# =============================================================================
# Main Processing
# =============================================================================

process_idea() {
    local idea_id="$1"

    # Create work directory for this idea run
    local idea_work_dir="$WORK_DIR/idea-$idea_id-$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$idea_work_dir"

    log_info "Processing idea: $idea_id"
    log_info "Work directory: $idea_work_dir"

    # Transition: backlog -> researching
    set_lifecycle "$idea_id" "researching" "Starting research phase"

    # Phase 2: PhD-Level Research Protocol (mandatory)
    # Note: run_research_protocol sets lifecycle to invalidated/parked if needed
    if ! run_research_protocol "$idea_id" "$idea_work_dir"; then
        log_warn "Idea $idea_id stopped at research phase"
        mark_complete "$idea_id" "$idea_work_dir" "research-stopped"
        return 1
    fi

    # Transition: researching -> researched
    set_lifecycle "$idea_id" "researched" "Research complete"

    # Phase 3: PRD
    if ! create_prd "$idea_id" "$idea_work_dir"; then
        log_error "PRD creation failed for idea $idea_id"
        set_lifecycle "$idea_id" "failed" "PRD creation failed"
        mark_complete "$idea_id" "$idea_work_dir" "prd-failed"
        return 1
    fi

    # Transition: researched -> scoped
    set_lifecycle "$idea_id" "scoped" "PRD created"

    # Transition: scoped -> implementing
    set_lifecycle "$idea_id" "implementing" "Starting implementation"

    # Phase 4: Implementation
    if ! run_implementation "$idea_id" "$idea_work_dir"; then
        log_warn "Implementation did not complete for idea $idea_id"
        set_lifecycle "$idea_id" "blocked" "Implementation incomplete"
        mark_complete "$idea_id" "$idea_work_dir" "implementation-incomplete"
        return 1
    fi

    # Transition: implementing -> completed
    set_lifecycle "$idea_id" "completed" "All success criteria met"

    # Phase 5: Mark complete
    mark_complete "$idea_id" "$idea_work_dir" "completed"

    log_info "Successfully completed idea $idea_id"
    return 0
}

# =============================================================================
# Main Loop
# =============================================================================

main() {
    setup

    while true; do
        # Phase 1: Extract next idea
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
            log_info "Idea $idea_id processing complete!"
        else
            log_warn "Idea $idea_id processing stopped"
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
