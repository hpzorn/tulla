# Ralph Workflow: From Idea to Implementation

The Ralph toolchain provides an autonomous, demand-driven approach to turning ideas into working implementations.

## Workflow Diagram

```
┌─────────────────┐
│   Idea Pool     │
│  (idea files)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Discovery-Ralph │  What exists? Who cares? What's the value?
│   (D1-D5)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Planning-Ralph  │  How do we build it using what exists?
│   (P1-P5)       │
└────────┬────────┘
         │
    ┌────┴────┐
    │ Blocked? │
    └────┬────┘
         │
    ┌────┴────┐
   No         Yes
    │          │
    ▼          ▼
┌───────┐  ┌─────────────────┐
│ Build │  │ Research-Ralph  │  What don't we know?
└───────┘  │   (R1-R6)       │
           └────────┬────────┘
                    │
                    ▼
           ┌─────────────────┐
           │ Planning-Ralph  │  (retry with new knowledge)
           │   (P1-P5)       │
           └────────┬────────┘
                    │
                    ▼
               ┌───────┐
               │ Build │
               └───────┘
```

## Tools

### 1. discovery-ralph.sh
**Purpose**: Understand what exists, who cares, and what's valuable

**Phases**:
- D1: Technical Inventory - What tools/skills/libraries exist?
- D2: Personas - Who is the user? What are their pain points?
- D3: Value Mapping - What's the value proposition?
- D4: Gap Analysis - What's missing?
- D5: Research Brief - Questions for research (if needed later)

**Usage**:
```bash
./discovery-ralph.sh --idea 30
./discovery-ralph.sh --idea 30 --upstream   # Before research
./discovery-ralph.sh --idea 30 --downstream # After research
```

**Output**: `work/discovery-30-*/` with D1-D5 markdown files

### 2. planning-ralph.sh
**Purpose**: Create implementation plan using existing capabilities

**Phases**:
- P1: Load Discovery Context - Synthesize D1-D5
- P2: Codebase Analysis - Deep dive into actual implementations
- P3: Architecture Design - How components connect
- P4: Implementation Plan - File-level, task-level detail
- P5: Research Requests - Emit blocking unknowns (if any)

**Usage**:
```bash
./planning-ralph.sh --idea 30
./planning-ralph.sh --idea 30 --interactive  # Pause between phases
```

**Output**: `work/planning-30-*/` with P1-P5 markdown files

**Requires**: Discovery documents from discovery-ralph

### 3. research-ralph.sh
**Purpose**: PhD-level research when truly blocked by unknowns

**Phases**:
- R1: Prior Art Scan - Is this novel?
- R2: Sub-Aspect Research - Break into components
- R3: RQ Formulation - Define research questions
- R4: Literature Review - Deep academic review
- R5: Research Execution - Experiments and proofs
- R6: Synthesis - Conclusions and go/no-go

**Usage**:
```bash
./research-ralph.sh --idea 30
./research-ralph.sh --idea 30 --interactive
```

**Output**: `work/idea-30-*/` with R1-R6 markdown files

**When to use**: Only when planning-ralph emits blocking research requests

### 4. epistemology-ralph.sh
**Purpose**: Generate new ideas through conceptual expansion

**Usage**:
```bash
./epistemology-ralph.sh --idea 26  # Expand from idea 26
```

**Output**: New seed ideas in the idea pool

## Workflow Examples

### Complete Flow (No Research Needed)
```bash
# 1. Start with an idea in the pool
# 2. Discover the landscape
./discovery-ralph.sh --idea 30

# 3. Create implementation plan
./planning-ralph.sh --idea 30
# → Output: "READY TO IMPLEMENT"

# 4. Implement (manually or with research-ralph's implementation phase)
```

### Flow with Research
```bash
# 1. Discover
./discovery-ralph.sh --idea 30

# 2. Plan
./planning-ralph.sh --idea 30
# → Output: "BLOCKED - RESEARCH NEEDED"
# → See p5-research-requests.md for questions

# 3. Research the blocking questions
./research-ralph.sh --idea 30

# 4. Re-plan with new knowledge
./planning-ralph.sh --idea 30
# → Output: "READY TO IMPLEMENT"

# 5. Implement
```

### Idea Expansion Flow
```bash
# 1. Find an interesting idea
# 2. Expand it conceptually
./epistemology-ralph.sh --idea 26
# → Generates 3 new seed ideas

# 3. Crystallize a seed into a full idea
# (Done interactively or programmatically)

# 4. Continue with discovery → planning → implementation
```

## Key Principles

1. **Demand-Driven Research**: Only do research when planning hits an actual unknown
2. **Maximize Reuse**: Planning focuses on using existing tools/skills
3. **Concrete Plans**: P4 produces file-level, task-level specifications
4. **Iterative**: If blocked, research and re-plan

## Directory Structure

```
ideasralph/
├── ideas/                    # Idea pool (markdown files)
│   ├── idea-1.md
│   ├── idea-30.md
│   └── ...
├── work/                     # Working directories
│   ├── discovery-30-manual/  # Discovery output
│   │   ├── D1-inventory.md
│   │   ├── D2-personas.md
│   │   ├── D3-value-mapping.md
│   │   ├── D4-gap-analysis.md
│   │   ├── D5-research-brief.md
│   │   └── DISCOVERY-SUMMARY.md
│   ├── planning-30-*/        # Planning output
│   │   ├── p1-discovery-context.md
│   │   ├── p2-codebase-analysis.md
│   │   ├── p3-architecture-design.md
│   │   ├── p4-implementation-plan.md
│   │   ├── p5-research-requests.md
│   │   └── PLANNING-SUMMARY.md
│   └── idea-30-*/            # Research output (if needed)
│       ├── r1-prior-art-scan.md
│       ├── r2-sub-aspect-research.md
│       └── ...
├── discovery-ralph.sh
├── planning-ralph.sh
├── research-ralph.sh
├── epistemology-ralph.sh
└── RALPH-WORKFLOW.md
```
