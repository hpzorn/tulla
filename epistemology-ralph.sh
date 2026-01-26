#!/bin/bash
# epistemology-ralph.sh - Scientific Protocols for Knowledge Generation
#
# Uses epistemological frameworks to generate new ideas from:
# - Pool analysis (gap detection, combination opportunities)
# - Domain exploration
# - Problem-driven solutions
# - Contradiction synthesis
# - External signals (papers, articles)
#
# Usage: ./epistemology-ralph.sh [MODE] [OPTIONS]
#
# Modes:
#   (no args)           Pool-driven: analyze idea pool for gaps
#   --domain "X"        Domain-focused: explore a specific domain
#   --problem "Q"       Problem-driven: generate solutions to a question
#   --thesis A --antithesis B   Contradiction: synthesize opposing ideas
#   --url URL           Signal-driven: react to external content
#
# Options:
#   --num N             Number of ideas to generate (default: 3)
#   --no-save           Don't save generated ideas to pool (default: save)
#   --dry-run           Show what would be done without executing
#
# Generated ideas are automatically saved to the idea pool with:
#   author: AI
#   source: epi-ralph

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="${SCRIPT_DIR}/work/epistemology-ralph-$(date +%Y%m%d-%H%M%S)"

# Defaults
MODE="pool"
DOMAIN=""
PROBLEM=""
THESIS=""
ANTITHESIS=""
SIGNAL_URL=""
NUM_IDEAS=3
SAVE_TO_POOL=true
DRY_RUN=false

# =============================================================================
# Argument Parsing
# =============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --domain|-d)
            MODE="domain"
            DOMAIN="$2"
            shift 2
            ;;
        --problem|-p)
            MODE="problem"
            PROBLEM="$2"
            shift 2
            ;;
        --thesis|-t)
            THESIS="$2"
            shift 2
            ;;
        --antithesis|-a)
            ANTITHESIS="$2"
            shift 2
            ;;
        --url|-u)
            MODE="signal"
            SIGNAL_URL="$2"
            shift 2
            ;;
        --num|-n)
            NUM_IDEAS="$2"
            shift 2
            ;;
        --no-save)
            SAVE_TO_POOL=false
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [MODE] [OPTIONS]"
            echo ""
            echo "Modes:"
            echo "  (no args)                    Pool-driven analysis"
            echo "  --domain 'X'                 Domain-focused exploration"
            echo "  --problem 'Q'                Problem-driven solutions"
            echo "  --thesis A --antithesis B    Contradiction synthesis"
            echo "  --url URL                    Signal-driven (from paper/article)"
            echo ""
            echo "Options:"
            echo "  --num N      Number of ideas (default: 3)"
            echo "  --no-save    Don't save to idea pool (default: save)"
            echo "  --dry-run    Show what would be done"
            exit 0
            ;;
        *)
            # Positional argument - try to auto-detect mode
            if [[ "$1" == *"?"* ]]; then
                MODE="problem"
                PROBLEM="$1"
            elif [[ "$1" == *" vs "* ]] || [[ "$1" == *" versus "* ]]; then
                MODE="contradiction"
                # Split on "vs"
                THESIS=$(echo "$1" | sed 's/ vs .*//' | sed 's/ versus .*//')
                ANTITHESIS=$(echo "$1" | sed 's/.* vs //' | sed 's/.* versus //')
            elif [[ "$1" == http* ]]; then
                MODE="signal"
                SIGNAL_URL="$1"
            else
                MODE="domain"
                DOMAIN="$1"
            fi
            shift
            ;;
    esac
done

# If thesis and antithesis provided, it's contradiction mode
if [[ -n "$THESIS" ]] && [[ -n "$ANTITHESIS" ]]; then
    MODE="contradiction"
fi

# =============================================================================
# Setup
# =============================================================================

mkdir -p "$WORK_DIR"

log() {
    echo "[$(date '+%H:%M:%S')] $*" >&2
}

log "Epistemology-Ralph starting..."
log "Mode: $MODE"
log "Work directory: $WORK_DIR"

if [[ "$DRY_RUN" == "true" ]]; then
    log "[DRY RUN] Would generate $NUM_IDEAS ideas"
fi

# =============================================================================
# Pool-Driven Mode
# =============================================================================

run_pool_mode() {
    log "Analyzing idea pool for gaps and combination opportunities..."

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would analyze pool and find gaps"
        return 0
    fi

    claude \
        --allowedTools "mcp__idea-pool__list_ideas,mcp__idea-pool__read_idea,mcp__idea-pool__find_related_ideas,mcp__idea-pool__semantic_search,mcp__idea-pool__capture_seed,Write" \
        -p "You are Epistemology-Ralph, a system for generating novel ideas through systematic analysis.

## Task: Pool-Driven Idea Generation

Analyze the idea pool to find opportunities for new ideas.

## Instructions

1. First, use mcp__idea-pool__list_ideas to see all ideas in the pool

2. Analyze the pool for:
   - **Gaps**: What topics are missing? What would bridge disconnected clusters?
   - **Combinations**: Which pairs of ideas could be combined into something new?
   - **Inversions**: What assumptions do multiple ideas share that could be inverted?

3. Generate ${NUM_IDEAS} novel idea candidates using these protocols:
   - Gap Analysis: Fill missing connections
   - Conceptual Combination: Merge ideas from different domains
   - Assumption Inversion: Challenge shared assumptions

4. For each generated idea, write to ${WORK_DIR}/ideas.md:

   # Generated Ideas

   ## Idea 1: [Title]
   **Protocol**: [Gap Analysis / Combination / Inversion]
   **Source Ideas**: [which existing ideas inspired this]
   **Description**: [2-3 sentences describing the idea]
   **Novelty**: [why this is different from existing ideas]

   ## Idea 2: ...

5. At the end, output a one-line summary of what you generated.

$(if [[ "$SAVE_TO_POOL" == "true" ]]; then
    echo "6. Use mcp__idea-pool__capture_seed to save each idea to the pool with metadata:
   - author: AI
   - source: epi-ralph
   - mode: pool
   - protocol: [the protocol used for this idea]"
fi)

Be creative but grounded. Each idea should be actionable and distinct from existing pool content." 2>&1 | tee "${WORK_DIR}/generation.log"
}

# =============================================================================
# Domain-Focused Mode
# =============================================================================

run_domain_mode() {
    log "Exploring domain: $DOMAIN"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would explore domain '$DOMAIN'"
        return 0
    fi

    claude \
        --allowedTools "mcp__idea-pool__list_ideas,mcp__idea-pool__semantic_search,mcp__idea-pool__capture_seed,WebSearch,Write" \
        -p "You are Epistemology-Ralph, a system for generating novel ideas through systematic analysis.

## Task: Domain-Focused Idea Generation

Explore the domain: **${DOMAIN}**

## Instructions

1. Use mcp__idea-pool__semantic_search to find ideas related to '${DOMAIN}'

2. Use WebSearch to find recent developments in this domain:
   - What are the current trends?
   - What problems remain unsolved?
   - What breakthroughs have happened recently?

3. Generate ${NUM_IDEAS} novel ideas that advance this domain:
   - Apply Gap Analysis to find unexplored areas
   - Consider Analogical Transfer from other fields
   - Look for Assumption Inversions in current approaches

4. Write to ${WORK_DIR}/ideas.md:

   # Domain Exploration: ${DOMAIN}

   ## Current State
   [Brief summary of what exists in this domain]

   ## Idea 1: [Title]
   **Protocol**: [which epistemological protocol]
   **Description**: [2-3 sentences]
   **Research Basis**: [what research/trends support this]

   ## Idea 2: ...

5. Output a one-line summary.

$(if [[ "$SAVE_TO_POOL" == "true" ]]; then
    echo "6. Use mcp__idea-pool__capture_seed to save each idea with metadata:
   - author: AI
   - source: epi-ralph
   - mode: domain
   - domain: ${DOMAIN}
   - protocol: [the protocol used for this idea]"
fi)

Focus on ideas that are novel yet grounded in research." 2>&1 | tee "${WORK_DIR}/generation.log"
}

# =============================================================================
# Problem-Driven Mode
# =============================================================================

run_problem_mode() {
    log "Solving problem: $PROBLEM"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would solve problem '$PROBLEM'"
        return 0
    fi

    claude \
        --allowedTools "mcp__idea-pool__list_ideas,mcp__idea-pool__semantic_search,mcp__idea-pool__capture_seed,WebSearch,Write" \
        -p "You are Epistemology-Ralph, a system for generating novel ideas through systematic analysis.

## Task: Problem-Driven Idea Generation

Solve this problem: **${PROBLEM}**

## Instructions

1. Parse the problem into sub-components

2. Search for related ideas: mcp__idea-pool__semantic_search with the problem keywords

3. Search for prior solutions: WebSearch for how others have approached this

4. Generate ${NUM_IDEAS} solution ideas using:
   - **Direct approach**: Straightforward solution
   - **Analogical transfer**: Solution from a different domain
   - **Assumption inversion**: Challenge the problem's premises
   - **Decomposition**: Break into smaller solvable parts

5. Write to ${WORK_DIR}/ideas.md:

   # Problem: ${PROBLEM}

   ## Problem Analysis
   [Decomposition into sub-problems]

   ## Prior Art
   [What solutions already exist]

   ## Solution 1: [Title]
   **Approach**: [Direct / Analogical / Inversion / Decomposition]
   **Description**: [how this solves the problem]
   **Trade-offs**: [pros and cons]

   ## Solution 2: ...

6. Output a one-line summary.

$(if [[ "$SAVE_TO_POOL" == "true" ]]; then
    echo "7. Use mcp__idea-pool__capture_seed to save each idea with metadata:
   - author: AI
   - source: epi-ralph
   - mode: problem
   - problem: ${PROBLEM}
   - protocol: [the approach used for this solution]"
fi)

Focus on actionable solutions." 2>&1 | tee "${WORK_DIR}/generation.log"
}

# =============================================================================
# Contradiction-Driven Mode
# =============================================================================

run_contradiction_mode() {
    log "Synthesizing contradiction: $THESIS vs $ANTITHESIS"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would synthesize '$THESIS' vs '$ANTITHESIS'"
        return 0
    fi

    claude \
        --allowedTools "mcp__idea-pool__list_ideas,mcp__idea-pool__read_idea,mcp__idea-pool__capture_seed,Write" \
        -p "You are Epistemology-Ralph, a system for generating novel ideas through systematic analysis.

## Task: Dialectical Synthesis

Resolve the contradiction between:
- **Thesis**: ${THESIS}
- **Antithesis**: ${ANTITHESIS}

## Instructions

1. If the thesis/antithesis are idea numbers, use mcp__idea-pool__read_idea to read them

2. Analyze the contradiction:
   - What is the core tension?
   - Are they truly contradictory or just different perspectives?
   - What does each side get right?

3. Apply Hegelian dialectical synthesis:
   - Find the valid kernel in each position
   - Identify what must be preserved from each
   - Synthesize a higher-order resolution

4. Generate ${NUM_IDEAS} synthesis ideas:

   Write to ${WORK_DIR}/ideas.md:

   # Dialectical Synthesis

   ## Thesis: ${THESIS}
   [Core claims and strengths]

   ## Antithesis: ${ANTITHESIS}
   [Core claims and strengths]

   ## Core Contradiction
   [What is the fundamental tension]

   ## Synthesis 1: [Title]
   **Resolution Type**: [Transcendence / Integration / Reframing]
   **From Thesis**: [what is preserved]
   **From Antithesis**: [what is preserved]
   **Novel Contribution**: [what emerges that neither had]
   **Description**: [2-3 sentences]

   ## Synthesis 2: ...

5. Output a one-line summary.

$(if [[ "$SAVE_TO_POOL" == "true" ]]; then
    echo "6. Use mcp__idea-pool__capture_seed to save each synthesis with metadata:
   - author: AI
   - source: epi-ralph
   - mode: contradiction
   - thesis: ${THESIS}
   - antithesis: ${ANTITHESIS}
   - protocol: dialectical-synthesis"
fi)

Warning: Avoid 'agreeable synthesis' that just says 'do both' - true synthesis transcends the opposition." 2>&1 | tee "${WORK_DIR}/generation.log"
}

# =============================================================================
# Signal-Driven Mode
# =============================================================================

run_signal_mode() {
    log "Processing signal from: $SIGNAL_URL"

    if [[ "$DRY_RUN" == "true" ]]; then
        log "[DRY RUN] Would process signal from '$SIGNAL_URL'"
        return 0
    fi

    claude \
        --allowedTools "mcp__idea-pool__list_ideas,mcp__idea-pool__semantic_search,mcp__idea-pool__capture_seed,WebFetch,Write" \
        -p "You are Epistemology-Ralph, a system for generating novel ideas through systematic analysis.

## Task: Signal-Driven Idea Generation

React to external signal: **${SIGNAL_URL}**

## Instructions

1. Use WebFetch to retrieve and understand the content at the URL

2. Extract key claims, findings, or innovations from the content

3. Use mcp__idea-pool__semantic_search to find related ideas in our pool

4. Apply dialectical synthesis:
   - What does this new information challenge in our existing ideas?
   - What opportunities does it create?
   - How can we integrate this new knowledge?

5. Generate ${NUM_IDEAS} ideas that incorporate this signal:

   Write to ${WORK_DIR}/ideas.md:

   # Signal Analysis: ${SIGNAL_URL}

   ## Signal Summary
   [Key findings/claims from the source]

   ## Relevance to Pool
   [How this relates to existing ideas]

   ## Idea 1: [Title]
   **Integration Type**: [Extension / Challenge / Application / Combination]
   **From Signal**: [what new knowledge is incorporated]
   **From Pool**: [what existing ideas are combined with]
   **Description**: [2-3 sentences]

   ## Idea 2: ...

6. Output a one-line summary.

$(if [[ "$SAVE_TO_POOL" == "true" ]]; then
    echo "7. Use mcp__idea-pool__capture_seed to save each idea with metadata:
   - author: AI
   - source: epi-ralph
   - mode: signal
   - signal_url: ${SIGNAL_URL}
   - protocol: [the integration type used]"
fi)

Focus on ideas that genuinely integrate the new signal with existing knowledge." 2>&1 | tee "${WORK_DIR}/generation.log"
}

# =============================================================================
# Main
# =============================================================================

case "$MODE" in
    pool)
        run_pool_mode
        ;;
    domain)
        run_domain_mode
        ;;
    problem)
        run_problem_mode
        ;;
    contradiction)
        run_contradiction_mode
        ;;
    signal)
        run_signal_mode
        ;;
    *)
        log "Unknown mode: $MODE"
        exit 1
        ;;
esac

log "Generation complete. Results in: $WORK_DIR"

# Show results if ideas.md was created
if [[ -f "${WORK_DIR}/ideas.md" ]]; then
    echo ""
    echo "============================================================"
    echo "Generated Ideas:"
    echo "============================================================"
    cat "${WORK_DIR}/ideas.md"
fi
