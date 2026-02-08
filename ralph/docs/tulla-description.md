# Tulla: An Ontology-Driven Software Engineering Agent

**Version**: February 2026
**Status**: Self-hosting (bootstrapping its own development since February 1, 2026)

---

## 1. Motivation

### The Problem: Context Loss Across Agent Boundaries

Modern AI-assisted software engineering suffers from a fundamental problem: **semantic context evaporates at every handoff point**. When a human developer moves from understanding a problem to designing a solution to writing code, they carry accumulated context in their head -- who the users are, what trade-offs were considered, why certain approaches were rejected. When AI agents perform these tasks, each invocation starts fresh. The discovery agent's insight about a critical user persona is invisible to the planning agent. The planning agent's architectural decision rationale is invisible to the implementation agent. The result is code that compiles but lacks coherence -- implementations that satisfy individual requirements while violating the architectural intent that motivated them.

This is not a token-window problem. Even with unlimited context, the issue persists: unstructured markdown artifacts are opaque to downstream consumers. A 54KB architecture design document contains the information a code generator needs, but buried in prose that another LLM must re-interpret -- lossy, expensive, and unreliable.

### The Hypothesis: Structured Semantic Persistence

Tulla's core hypothesis is that **decision-critical phase outputs should be persisted as structured RDF triples in a knowledge graph**, not just as markdown files. If each phase declares which of its output fields carry architectural intent (via a simple annotation), and the pipeline automatically extracts and stores those fields as typed triples, then downstream phases can receive precisely the semantic payload they need -- not a document dump, but a structured fact set with provenance.

This transforms the agent pipeline from a sequential document-passing chain into a **knowledge-accumulating system** where each phase enriches a shared semantic graph that all subsequent phases can query.

### The Ambition: From Idea Seed to Traced Commit

Tulla aims to take a raw idea seed -- a paragraph describing what someone wants to build -- and produce fully implemented, tested, committed code with a complete traceability chain:

```
Idea Seed
  -> Discovery (who needs this? what exists? what's the gap?)
    -> Research (what don't we know? what experiments resolve uncertainty?)
      -> Planning (what exactly should be built? in what order? with what architecture?)
        -> Implementation (write the code, verify it, commit it)
```

Every step produces structured artifacts that are both human-readable (markdown) and machine-queryable (RDF triples). Every implementation commit traces back through requirements, ADRs, quality attributes, gap analysis, persona needs, and the original idea. The traceability chain is not documentation -- it is live, queryable metadata in a knowledge graph.

### Why Not Just Use an LLM Directly?

A single LLM invocation can write code. But it cannot:

1. **Accumulate knowledge across phases** -- each call is stateless
2. **Enforce architectural governance** -- no mechanism to ensure code respects prior ADRs
3. **Provide traceability** -- no link from code back to the requirement that motivated it
4. **Validate structural properties** -- no SHACL shapes to catch when a phase output is incomplete
5. **Resume after failure** -- no checkpoints, no idempotent writes, no budget tracking
6. **Learn within a session** -- no lesson extraction from verification failures

Tulla wraps LLM calls in a pipeline that provides all six capabilities through a combination of ontology-driven fact persistence, SHACL validation, and structured phase contracts.

---

## 2. Design Philosophy

### 2.1 Intent Preservation Over Information Dumping

The central design principle is **intent preservation**: not every field in a phase's output matters equally. A discovery phase might produce a 12KB markdown file, but only three fields carry decision-critical information that downstream phases need. Tulla uses `IntentField` annotations to mark exactly which fields should be persisted to the knowledge graph:

```python
class D3Output(BaseModel):
    value_mapping_file: Path                           # artifact locator -- NOT persisted
    quadrant: str = IntentField(description="...")      # decision field -- persisted
    strategic_constraints: str = IntentField(...)       # scope boundary -- persisted
    verdict: str = IntentField(description="...")       # decision field -- persisted
```

The 4-rule heuristic for selecting IntentFields:

1. **Decision Fields** -- verdicts, go/no-go, recommendations
2. **Quantified Assessments** -- meaningful evaluations, not raw counts
3. **User-Facing Commitments** -- needs that must survive into implementation
4. **Scope Boundaries** -- what's in/out, constraints that limit downstream choices

Fields that fail all four rules (artifact paths, intermediate counts, raw text) are not annotated and not persisted.

### 2.2 Hexagonal Architecture

Tulla follows a strict ports-and-adapters architecture. Two abstract ports define the system boundary:

- **`ClaudePort`** -- a single `run(request) -> result` method for LLM invocation
- **`OntologyPort`** -- 13 methods mirroring the ontology-server's capabilities (SPARQL queries, triple management, fact storage, SHACL validation)

Concrete adapters implement these ports:

| Port | Adapter | External System |
|------|---------|----------------|
| ClaudePort | ClaudeCLIAdapter | `claude` CLI binary (subprocess) |
| ClaudePort | CodexCLIAdapter | OpenAI `codex` CLI binary |
| ClaudePort | OpenCodeCLIAdapter | `opencode` CLI binary |
| OntologyPort | OntologyMCPAdapter | Ontology-server HTTP REST API |

The core pipeline logic -- phases, fact persistence, SHACL validation, checkpoint management -- depends only on the abstract ports. Adapter selection happens at the composition root in the CLI and configuration layer. This means tulla can target different LLM backends without any changes to phase logic.

### 2.3 Fail-Safe Execution

Every component is designed for graceful failure and clean recovery:

- **Atomic checkpoint writes** use `tempfile.mkstemp` + `os.rename` to prevent corrupt checkpoint files on crash
- **Idempotent triple persistence** clears all triples for a subject before writing new ones, making pipeline resume safe
- **SHACL validation with rollback** detects structurally invalid phase outputs and removes their triples before they pollute the knowledge graph
- **Budget tracking** stops execution when the dollar budget is exhausted, preventing runaway costs
- **Per-phase error isolation** wraps every step of the Template Method in its own try/except, producing structured error results rather than propagating exceptions

### 2.4 Cross-Agent Fact Flow

Phases in different pipelines (discovery, research, planning) can read each other's persisted facts via SPARQL. The `prior_phases` parameter tells a pipeline which upstream phase IDs to query:

```python
# Planning pipeline declares it can read discovery and research facts
prior_phases = ["d1", "d2", "d3", "d4", "d5", "r1", "r2", "r3", "r4", "r5", "r6"]
```

Before each phase executes, the pipeline's pre-hook calls `collect_upstream_facts()`, which issues a SPARQL query against the ontology-server's phases graph to fetch all `phase:preserves-*` triples for the current idea. These are injected into the phase's context, and `group_upstream_facts()` transforms them into a typed dict suitable for prompt injection:

```json
{
  "d1": {"key_capabilities": [...], "ecosystem_context": "..."},
  "d3": {"quadrant": "Quick Win", "verdict": "P1-High | Strong ROI"},
  "d5": {"northstar": "...", "mandatory_features": [...]}
}
```

This is how a planning phase can reference a discovery persona's JTBD statement or a research experiment's finding without reading the full markdown file.

---

## 3. Architecture Overview

### 3.1 System Topology

```
                    +-----------------+
                    |   Idea Pool     |
                    | (ontology-srv)  |
                    +--------+--------+
                             |
                    +--------v--------+
                    |   tulla CLI     |
                    | (Click commands)|
                    +--------+--------+
                             |
              +--------------+--------------+
              |              |              |
     +--------v-----+ +-----v------+ +-----v--------+
     |  Discovery   | |  Research  | |   Planning   |
     |  Pipeline    | |  Pipeline  | |   Pipeline   |
     | (D1-D5)      | | (R1-R6)    | |  (P1-P6)     |
     +--------+-----+ +-----+------+ +-----+--------+
              |              |              |
              +--------------+--------------+
                             |
                    +--------v--------+
                    | Implementation  |
                    |     Loop        |
                    | (Find-Impl-    |
                    |  Commit-Verify) |
                    +--------+--------+
                             |
              +--------------+--------------+
              |                             |
     +--------v--------+          +--------v--------+
     |   ClaudePort    |          |  OntologyPort   |
     | (LLM boundary)  |          | (KG boundary)   |
     +--------+--------+          +--------+--------+
              |                             |
     +--------v--------+          +--------v--------+
     | Claude CLI      |          | ontology-server |
     | (subprocess)    |          | (HTTP REST)     |
     +-----------------+          +-----------------+
```

### 3.2 Pipeline Executor

The `Pipeline` class is the central orchestrator. It accepts an ordered list of `(phase_id, Phase)` tuples and executes them sequentially with two hook points:

**Pre-phase hook**: Calls `collect_upstream_facts()` via SPARQL, injecting structured facts from all prior phases into the current phase's context.

**Post-phase hook**: Calls `PhaseFactPersister.persist()` to extract IntentField-annotated values from the phase result, store them as RDF triples, optionally validate against a SHACL shape, and roll back on validation failure.

Additional pipeline capabilities:
- **Checkpoint/resume**: After each phase, the result is saved as `{phase_id}-result.json`. When `--from` is specified, earlier phases are skipped and their checkpoints are loaded to restore the output chain.
- **Budget tracking**: A dollar budget is decremented after each phase. When exhausted, execution halts.
- **Output chaining**: Each phase's parsed output is passed as `prev_output` to the next phase, enabling sequential refinement.

### 3.3 Phase Base Class (Template Method)

Every phase is a subclass of `Phase[T]` that implements a fixed six-step algorithm:

1. **`validate_input(ctx)`** -- optional precondition check
2. **`build_prompt(ctx)`** -- construct the LLM prompt (abstract, subclass-specific)
3. **`get_tools(ctx)`** -- declare available MCP tools (abstract)
4. **`run_claude(ctx, prompt, tools)`** -- invoke the LLM via the injected ClaudePort
5. **`parse_output(ctx, raw)`** -- read the markdown artifact and extract structured data (abstract)
6. **`validate_output(ctx, parsed)`** -- optional postcondition check

Each step has its own error handler. A file-write constraint is automatically appended to every prompt: `"You MUST only create or modify files inside the work directory: {path}"`.

The `Phase[T]` and `PhaseResult[T]` classes are generic over the output type, providing type-safe access to parsed results.

---

## 4. Fact Persistence Layer

### 4.1 IntentField Annotation

`IntentField` is a factory function wrapping `pydantic.Field` that injects `{"preserves_intent": True}` into the field's JSON schema metadata:

```python
def IntentField(*, default=..., description="", **kwargs):
    return Field(default=default, description=description,
                 json_schema_extra={"preserves_intent": True, **kwargs})
```

The companion function `extract_intent_fields(obj)` introspects any Pydantic model's `model_fields` and returns `{field_name: value}` for every field carrying this marker. No registration step is needed -- simply annotating a field is sufficient.

### 4.2 PhaseFactPersister

The `persist()` method follows an 8-step protocol:

1. **Extract intent fields** from the phase result via `extract_intent_fields()`
2. **Compute subject URI**: `http://impl-ralph.io/phase#{idea_id}-{phase_id}`
3. **Idempotent cleanup**: `remove_triples_by_subject(subject)` -- safe for resume
4. **Store rdf:type**: `<subject> rdf:type phase:PhaseOutput`
5. **Store intent fields**: `<subject> phase:preserves-{field_name} "value"` for each non-None field
6. **Store metadata**: `phase:producedBy`, `phase:forRequirement`
7. **Store trace link**: `<subject> trace:tracesTo <predecessor>` (if predecessor exists)
8. **Optional SHACL validation**: If a shape is registered for this phase, validate and roll back on failure

### 4.3 Upstream Fact Collection

`collect_upstream_facts()` issues a SPARQL query against the ontology-server's named graph (`http://semantic-tool-use.org/graphs/phases`) to fetch all triples for the current idea from prior phases. The `group_upstream_facts()` function transforms the flat SPO triples into a nested dict with automatic type coercion (int, float, bool, JSON parsing).

### 4.4 SHACL Shape Registry

Each phase can have a corresponding SHACL NodeShape in `phase-ontology.ttl`. The shape uses a SPARQL-based target to select instances by their `phase:producedBy` value and declares `sh:minCount 1` constraints on required IntentFields. The `PHASE_SHAPES` dict maps phase IDs to shape URIs:

```python
PHASE_SHAPES = {
    "d1": "http://impl-ralph.io/phase#D1OutputShape",
    "d2": "http://impl-ralph.io/phase#D2OutputShape",
    # ... 13 shapes total
}
```

When a shape is registered and validation fails, all triples for that phase are rolled back, and the pipeline stops with a structured error.

---

## 5. Discovery Pipeline (D1-D5)

The discovery pipeline answers the question: **"What should we build, for whom, and why?"** Five sequential phases progressively narrow from broad inventory to a focused research brief or product specification.

### 5.1 D1: Tool & MCP Inventory

**Purpose**: Audit what currently exists related to an idea.

The LLM reads the idea from the ontology, searches for related work via SPARQL and codebase grep, and produces a structured inventory with sections: Related Ideas (table), Existing Systems & Tools (table), Prior Work, Current Gaps, and Ecosystem Context.

**IntentFields**: `key_capabilities` (JSON list of reusable components), `ecosystem_context` (how the idea fits the broader system), `reuse_opportunities` (what's already built).

### 5.2 D2: Persona Discovery

**Purpose**: Identify 2-4 user personas with Jobs-to-be-Done analysis.

Reads D1's inventory and upstream facts. Produces persona profiles with functional/emotional/social JTBD, pain points, desired outcomes. Synthesizes a cross-persona JTBD statement: "When I [situation], I want [motivation], so I can [outcome]."

**IntentFields**: `personas` (JSON list), `non_negotiable_needs` (cross-persona must-haves), `primary_persona_jtbd` (synthesized statement).

### 5.3 D3: Value Mapping

**Purpose**: Assess business value, strategic fit, and ROI across three dimensions (user, business, technical), each scored 1-5 on four sub-dimensions (total out of 60).

Produces an effort-impact quadrant classification (Quick Win / Major Project / Fill-in / Thankless Task), strategic fit analysis, and ROI assessment.

**IntentFields**: `quadrant` (classification), `strategic_constraints` (JSON list), `verdict` (compact statement: "P1-High | Strong ROI | High confidence").

### 5.4 D4: Gap Analysis

**Purpose**: Identify gaps between current and desired state across five categories: Knowledge, Technical, Quality-Attribute, Resource, and Integration gaps. Prioritize into P0-P3 with a priority matrix.

Optionally incorporates iSAQB architecture schema context for quality attribute gap assessment via SPARQL queries against the ontology.

**IntentFields**: `blockers` (critical path narrative), `root_blocker` (the single highest-priority blocking gap), `recommended_next_steps`.

### 5.5 D5: Integration & Handoff

**Purpose**: Synthesize all prior findings into a handoff artifact. Operates in two modes:

- **Upstream mode** (pre-research): Produces a research brief with prioritized research questions, mandatory features list, and constraints. The mandatory features list is explicitly declared a contract: "This list is the contract that planning must preserve."
- **Downstream mode** (post-research): Produces a product specification with MoSCoW requirements, success metrics, and integration points.

The final line of output is a routing keyword (`research`, `implement`, or `park`) that determines the next pipeline.

**IntentFields**: `mode`, `recommendation`, `northstar` (compact idea definition, max 2000 chars), `mandatory_features` (JSON list), `key_constraints` (JSON list).

### 5.6 Upstream Fact Flow

```
D1 (no upstream) -> persists 3 facts
D2 (reads D1)    -> persists 3 facts
D3 (reads D1+D2) -> persists 3 facts
D4 (reads D1-D3) -> persists 3 facts
D5 (reads D1-D4) -> persists 5 facts
```

Each phase's `build_prompt()` renders upstream facts as an indented JSON block, giving the LLM structured access to all prior decisions without re-reading full markdown files.

---

## 6. Research Pipeline (R1-R6)

The research pipeline answers the question: **"What don't we know, and how do we find out?"** Six phases progressively move from question refinement through source identification, investigation, literature review, experimentation, and synthesis.

### 6.1 Three Routing Modes

Research operates in three modes, selected by input availability:

**Groundwork mode** (no prior discovery or planning): Starts from a raw idea seed. R1 performs a prior-art triage -- decomposes the idea into 3-5 capabilities, assesses each for novelty (Novel / Partial / Derivative / Commoditized), and only generates research questions for Novel or Partial capabilities. If all capabilities are Derivative/Commoditized, R1 raises `EarlyTermination`, writes a minimal R6 file, and skips R2-R6 entirely.

**Discovery-fed mode** (discovery output available): R1 refines the D5 research brief's prioritized questions into precise, answerable questions while respecting D5's priority ordering.

**Spike mode** (planning output available): Targeted research answering specific blocked questions from planning P5. After the spike completes, the user re-runs `tulla run planning --from p5` to resume with spike results as upstream facts.

### 6.2 R1: Research Question Refinement

Transforms research inputs (raw idea, D5 brief, or P5 requests) into precise, answerable research questions with methodology notes and acceptance criteria. In groundwork mode, includes a novelty assessment that can trigger early termination.

**IntentFields**: `questions_refined` (count), `research_questions` (JSON list of `{id, question, methodology, acceptance_criteria}`).

### 6.3 R2: Source Identification

For each research question, identifies relevant documentation, APIs, repositories, papers, and existing codebase patterns. Produces a source map table and identifies source gaps (questions where sources are scarce, suggesting experimentation will be needed).

**Timeout**: 45 minutes (the longest of the non-experiment phases).

**IntentFields**: `sources_identified` (count), `source_map` (JSON), `source_gaps`.

### 6.4 R3: Investigation

Actually investigates each research question using identified sources. Reads sources, gathers evidence, notes contradictions, and assesses confidence. Categorizes each question as Answered / Partially Answered / Unanswered.

**IntentFields**: `research_questions` (count investigated), `rq_answers` (JSON with status/confidence/answer), `remaining_unknowns`.

### 6.5 R4: Literature Review

Conducts a structured, deeper review comparing approaches across sources, identifying best practices and anti-patterns, noting trade-offs, and producing actionable recommendations per question. Includes cross-cutting theme analysis.

**IntentFields**: `papers_reviewed` (count), `rqs_addressed` (count), `key_findings` (JSON with recommendations).

### 6.6 R5: Experiments & Prototyping

The most distinctive research phase. R5 actually **writes and executes code** to answer questions that literature cannot resolve. It operates with `acceptEdits` permission mode and has access to `Bash`, `Edit`, and `Write` tools -- effectively acting as a full coding agent within the research work directory.

Each experiment follows a structured protocol:
1. **Hypothesis**: What we expect to find
2. **Setup**: Code written and executed
3. **Result**: PASS/FAIL with retry on failure (up to configurable `max_retries`)
4. **Finding**: What was learned, including unexpected discoveries
5. **Artefacts**: Files created for provenance tracking

**Timeout**: 120 minutes (6x the standard 20 minutes).

**IntentFields**: `experiments_run`, `experiments_passed`, `experiment_results` (JSON), `impl_implications`.

### 6.7 R6: Research Synthesis

Synthesizes all prior findings into a coherent final report with a recommendation: `"proceed"`, `"revise plan"`, or `"more research needed"`. Produces per-question synthesized answers with confidence levels and a risk/mitigation table.

**IntentFields**: `findings_count`, `recommendation`, `synthesised_answers` (JSON), `risks` (JSON).

---

## 7. Planning Pipeline (P1-P6)

The planning pipeline answers the question: **"What exactly should be built, in what order, with what architecture?"** Six phases progressively move from context consolidation through codebase analysis, architecture design, implementation planning, research gating, and RDF export.

### 7.1 P1: Discovery Context Load

Consolidates all upstream discovery and research documents into a single planning context document. Produces an authoritative Feature Scope table that subsequent phases must cover completely -- no additions, no omissions.

### 7.2 P2: Codebase Analysis

Deep analysis of internal implementations -- understanding HOW existing tools work, not just what they do. Explores skill definitions, MCP server architectures, integration patterns, and extension points.

### 7.3 P3: Architecture Design

The heaviest planning phase (typically $2-3, producing 50KB+ of output). Designs architecture using the iSAQB quality attribute vocabulary with:

- Quality Goals and Tradeoffs tables
- Design Principles with categories
- Feature Coverage Matrix (every P1 feature mapped to building blocks)
- ADRs in arc42/Nygard format with Status, Context, Decision, Consequences (+/-/~ prefixes)
- Quality Scenarios, Risk Assessment, and Unknowns Requiring Research

After writing the design document, P3 stores key architecture decisions as structured triples in the ontology A-box: quality goals as facts, design principles as facts, and full ADR instances as `isaqb:ArchitectureDecision` entities with type, label, context, status, consequences, and scope.

**Project ADR governance** (idea 69): When a project ID is configured, P3 queries the ontology for project-level ADRs via `collect_project_decisions()` and injects a governance section into the prompt. This instructs the LLM to respect project ADRs, generate only feature-delta ADRs, and produce explicit `isaqb:supersedes` links when overriding project decisions.

**IntentFields**: `architecture_decisions` (JSON), `quality_goals` (JSON).

### 7.4 P4: Implementation Plan

Creates a detailed, executable implementation plan with file-level specificity. Tasks are organized into priority phases (P0 Critical Path, P1 Important, P2 Nice to Have). Each task specifies files, action (Create/Modify/Extend), a description of WHAT (not HOW), dependencies, and verification criteria.

**Granularity gate** (advisory): `parse_output()` computes words-per-file (WPF) metrics for each task. Tasks with too many files and too few descriptive words are flagged as coarse. This gate is advisory (logs warnings to stderr) but does not block the pipeline.

### 7.5 P5: Research Requests (Gate Phase)

A gate decision: determines if implementation can proceed or if research is needed first. Examines P4 for blocked tasks and P4b (persona walkthrough) for blocking gaps. The final line is exactly `ready` or `blocked`.

If blocked, produces structured Research Requests (RR1, RR2, ...) with the blocking task, specific question, rationale, suggested approach, and acceptable answer format. This is the input for a research spike.

### 7.6 P6: Export PRD to RDF

The bridge between planning and implementation. Converts P4's implementation plan into RDF Turtle format, where each task becomes a `prd:Requirement` instance with properties:

- `prd:taskId`, `prd:title`, `prd:description`, `prd:status` (Pending)
- `prd:priority` (P0/P1/P2), `prd:phase`, `prd:files`, `prd:action`
- `prd:verification`, `prd:relatedADR`, `prd:qualityFocus`
- `prd:filesCount`, `prd:descriptionWordCount`, `prd:wordsPerFile` (granularity metrics)
- `prd:dependsOn` (dependency links between requirements)

After generating the Turtle file, P6 performs **A-box hydration**: parses the Turtle with rdflib, clears any previous facts for the `prd-idea-{N}` context (idempotent), and stores every triple as a fact in the ontology.

**Granularity gate** (blocking): Unlike P4's advisory gate, P6's gate is blocking. Requirements that are too coarse trigger a retry with structured feedback using the CRITIC framework (Concrete metrics, Referenced file grouping, Instructive split instructions, Targeted per-requirement). The retry rebuilds the prompt with the feedback appended.

---

## 8. Implementation Loop

The implementation phase uses a fundamentally different architecture from the linear pipelines. Instead of a sequential `Pipeline`, it uses a custom `ImplementationLoop` that iterates through requirements one at a time.

### 8.1 Loop Architecture

```
Find next ready requirement
  |
  +-> (none available?) -> ALL_COMPLETE -> exit
  |
  +-> Mark as IN_PROGRESS
  |
  +-> Implement (Claude with acceptEdits)
  |     |
  |     +-> Commit (git add + commit)
  |     |
  |     +-> Verify (Claude, read-only)
  |           |
  |           +-> PASS -> extract lesson -> mark COMPLETE -> loop
  |           |
  |           +-> FAIL -> retry with feedback (up to max_retries)
  |                        |
  |                        +-> all retries exhausted -> mark BLOCKED -> loop
  |
  +-> Budget guard (stop if exhausted)
```

### 8.2 FindPhase (No LLM)

Queries the ontology for the next actionable requirement. Recalls all `prd:Requirement` instances, checks their `prd:status` and `prd:dependsOn` links, and selects the first pending requirement whose dependencies are all complete. If `prd:qualityFocus` is set, resolves it through three chained SPARQL queries to find relevant architectural patterns, design principles, and design patterns from the iSAQB ontology.

### 8.3 ImplementPhase

Invokes Claude with `acceptEdits` permission mode and full tool access (`Read`, `Write`, `Edit`, `Glob`, `Grep`, `Bash`). The prompt includes:

- Requirement details (ID, title, description, files, action, verification criteria)
- Architecture context (quality focus, relevant ADRs, design principles, project ADRs)
- Pattern annotations (if resolved patterns exist -- format specification, checklist, examples)
- Lessons from previous requirements ("Avoid repeating these mistakes")
- Previous attempt feedback (if this is a retry)

Output must end with `IMPLEMENTED: {req_id}` or `IMPLEMENT_FAIL: {req_id} [reason]`.

### 8.4 CommitPhase (No LLM)

Creates a git commit for the implemented changes via subprocess. Stages specified files, checks for staged changes, and commits with the message format `impl({req_id}): {title}`.

### 8.5 VerifyPhase

Invokes Claude in read-only mode (`bypassPermissions`, no `Write` or `Edit` tools) to verify that the implementation satisfies the requirement. Checks:

1. Implementation matches the requirement description
2. Verification criteria are satisfied (may run tests via Bash)
3. Architecture compliance (relevant ADRs respected)
4. Pattern annotation quality (coverage, density, novelty checks)

Output must end with `VERIFY_PASS` or `VERIFY_FAIL: [specific issues]`.

### 8.6 Lesson Extraction

After each verification, `extract_lesson()` produces a lesson string when something went wrong:
- Passed after retries: `"{req_id}: Fixed after N retries. Issue: {verdict}"`
- Failed: `"{req_id}: Failed. Issue: {verdict}"`

Lessons are stored as `lesson:text` facts in the ontology and passed to subsequent implementation calls, enabling in-session learning.

### 8.7 Budget and Retry Systems

**Budget**: A dollar budget (default $30 for implementation) is decremented after every Claude invocation. When exhausted, the loop stops with `BUDGET_EXHAUSTED`. The remaining budget is passed to each Claude call, so the LLM also respects it.

**Retries**: Up to `max_retries` (default 2) additional attempts per requirement, meaning 3 total. Each retry receives the verification failure feedback and the instruction "Fix the issues described above." If all retries exhaust, the requirement is marked `BLOCKED`.

---

## 9. Ontology Integration

### 9.1 Namespace Architecture

Tulla operates in a multi-ontology namespace:

| Prefix | URI | Purpose |
|--------|-----|---------|
| `phase:` | `http://impl-ralph.io/phase#` | Phase output entities and properties |
| `trace:` | `http://impl-ralph.io/trace#` | Traceability links between phases |
| `prd:` | `http://impl-ralph.io/prd#` | PRD entities (Project, Requirement) |
| `isaqb:` | `http://impl-ralph.io/isaqb#` | iSAQB architecture vocabulary |
| `arch:` | `http://impl-ralph.io/arch#` | Architecture decisions and governance |

### 9.2 Triple Structure

Phase facts follow a regular structure:

```turtle
phase:73-d3 a phase:PhaseOutput ;
    phase:producedBy "d3" ;
    phase:forRequirement "73" ;
    phase:preserves-quadrant "Quick Win" ;
    phase:preserves-verdict "P1-High | Strong ROI | High confidence" ;
    phase:preserves-strategic_constraints "[...]" ;
    trace:tracesTo phase:73-d2 .
```

Architecture decisions follow the iSAQB vocabulary:

```turtle
arch:adr-69-1 a isaqb:ArchitectureDecision ;
    rdfs:label "ADR-69-1: Use ARCH_NS for project-scoped URI construction" ;
    isaqb:context "..." ;
    isaqb:decisionStatus isaqb:StatusProposed ;
    isaqb:consequences "..." ;
    isaqb:scope "project" ;
    isaqb:addresses isaqb:Maintainability .
```

### 9.3 SHACL Validation

13 SHACL NodeShapes are defined in `phase-ontology.ttl`, one per phase. Each shape uses a SPARQL-based target to select instances by their `phase:producedBy` value and declares `sh:minCount 1` constraints on required IntentFields. Validation is performed by pyshacl with `advanced=True` for SPARQL constraint support.

The `ADRScopeCoherenceShape` (from idea 69) demonstrates cross-entity SHACL validation: it uses a SPARQL constraint to detect idea-scope ADRs that address the same quality attribute as a project-scope ADR without an explicit `isaqb:refinesDecision` or `isaqb:supersedes` link.

### 9.4 The Ontology Server

Tulla communicates with the ontology-server via HTTP REST (despite the "MCP" adapter name). The server provides two separate stores:

- **T-Box** (OntologyStore, rdflib): Schema classes, SHACL shapes, ontology definitions. Queried via MCP tools.
- **A-Box** (KnowledgeGraphStore, Oxigraph): Instance triples, phase facts, project entities, ADR instances. Queried via HTTP REST endpoints.

This dual-store architecture creates a known gap: SHACL validation requires both shapes (from T-Box) and instance data (from A-Box) to be available to pyshacl simultaneously. A URI compaction bug in the `/validate` endpoint currently prevents this from working reliably, which is why the `shape_registry` is disabled in the research pipeline.

---

## 10. Configuration

Tulla uses layered configuration via `pydantic-settings`:

**Precedence** (highest to lowest): CLI flags > environment variables (`TULLA_` prefix) > YAML file > built-in defaults.

**Agent-specific configuration**: Each pipeline agent (discovery, planning, research, implementation, lightweight) has its own `AgentConfig` with:

| Setting | Discovery | Research | Planning | Implementation |
|---------|-----------|----------|----------|----------------|
| Budget (USD) | $5.00 | $8.00 | $5.00 | $30.00 |
| Timeout (min) | 15 | 30 | 15 | 60 |
| Permission mode | bypass | bypass | bypass | acceptEdits |
| Max retries | 2 | 2 | 2 | 2 |

**Global settings**: `project_id` (default "ralph"), `ontology_server_url` (default localhost:8100), `llm_backend` (claude/codex/opencode), work/ideas directory paths.

---

## 11. CLI Interface

The `tulla` CLI provides four commands:

**`tulla run <agent> --idea N`**: Execute a pipeline. Agents: `discovery`, `research`, `planning`, `implementation`, `lightweight`, `epistemology`. Supports `--from` for resume from a specific phase, `--mode` for agent-specific modes, `--dry-run` for plan preview, `--work-dir` override, and `--verbose` for debug logging.

**`tulla project-init [--project-id ID] [--claude-md PATH]`**: Bootstrap a project from a CLAUDE.md file. Creates a `prd:Project` entity and extracts ADRs using LLM analysis of governance prose.

**`tulla promote-adr [ADR_ID]`**: Promote an idea-scope ADR to project scope. Supports interactive selection if no ID is given.

**`tulla status --idea N`**: Display PRD requirement completion status. Returns exit code 2 if work remains.

Exit codes follow the Unix convention: 0 (success), 1 (failure), 2 (incomplete), 124 (timeout, matching the `timeout` command).

---

## 12. First Results: Bootstrapping Tulla with Tulla

### 12.1 The Bootstrap Chain

Tulla has been self-hosting since February 1, 2026, producing **166 implementation commits** across **10 ideas** in 7 days. Each idea uses tulla to plan and implement the next improvement to tulla:

```
Idea 54: Python Rewrite (THE FOUNDATION -- 33 commits)
  |
  +-> Idea 63: Status Command (19 commits) -- first full-pipeline test
  +-> Idea 64: PRD Granularity Enforcement (20 commits)
  +-> Idea 65: Pattern-Aware Code Annotations (12 commits)
  +-> Idea 67: Phase Contracts / IntentField (21 commits) -- infrastructure keystone
        |
        +-> Idea 73: Close the A-Box Gap (22 commits)
        +-> Idea 53: Lightweight Pipeline (24 commits)
        +-> Idea 58: Research Modes (15 commits)
              |
              +-> Idea 69: Project-Level Architecture (28 requirements)
```

### 12.2 Aggregate Statistics

| Metric | Value |
|--------|-------|
| Total ideas processed | 10+ |
| Total implementation commits | 166 |
| Total work directories created | 75 |
| Ideas with full D->R->P->I pipeline | 7 |
| Average PRD requirements per idea | 16.4 |
| Typical discovery cost | $0.35 - $3.56 |
| Typical planning cost | $0.44 - $6.14 |
| Most expensive single phase | P3 Architecture Design: $2.64 |
| Tests passing | 1,542 |

### 12.3 Cost Profile (Idea 58, Full Pipeline)

| Phase | Cost | Duration | Notes |
|-------|------|----------|-------|
| D1 Inventory | $1.40 | 4.3 min | Deep codebase scan |
| D2 Personas | $0.28 | 1.4 min | |
| D3 Value Mapping | $0.25 | 1.1 min | |
| D4 Gap Analysis | $1.21 | 3.4 min | Detailed technical gaps |
| D5 Research Brief | $0.42 | 1.7 min | |
| P1 Context Load | $0.42 | 1.4 min | |
| P2 Codebase Analysis | $1.27 | 3.7 min | |
| P3 Architecture Design | $2.64 | 9.8 min | Heaviest phase -- 54KB output |
| P4 Implementation Plan | $0.79 | 3.5 min | |
| P5 Research Requests | $0.20 | 0.4 min | |
| P6 PRD Export | $0.82 | 2.9 min | Generates Turtle RDF |
| **Discovery Total** | **$3.56** | **~12 min** | |
| **Planning Total** | **$6.14** | **~22 min** | |

Implementation costs are typically $15-25 depending on requirement count and complexity. Idea 69 (28 requirements) cost $25.06 for implementation alone.

### 12.4 Idea 69: A Detailed Case Study

Idea 69 ("Project-Level Architecture: Hierarchical ADRs and Product-Scoped Governance") demonstrates the full pipeline at maturity:

**Discovery** ($2.81, 5 phases): Identified the need for project-scoped ADR governance above individual idea ADRs. D3 value mapping scored 49/60 (P1-High). D5 produced a research brief with 7 prioritized research questions.

**Research** (~$8, 6 phases, 4 experiments):
- R1 refined 7 research questions from the D5 brief
- R5 ran 4 experiments, all passing:
  - Exp 1: ARCH_NS namespace formalization (7/7 tests)
  - Exp 2: pyshacl SPARQL constraint execution for ADR scope coherence (discovered that `sh:severity` must be on the NodeShape, not the SPARQL constraint node)
  - Exp 3: P3 delta-prompt compliance (LLM correctly avoided regenerating project ADRs in both aligned and override scenarios)
  - Exp 4: CLAUDE.md ADR extraction quality (6 ADRs extracted, 100% SHACL valid, 0 hallucinations)
- R6 verdict: "Proceed to implementation. All 7 RQs answered at high confidence."

**Planning** ($7.71, 6 phases, 472 A-box triples): P3 produced a 28-requirement implementation plan with ADR governance, scope annotations, migration functions, and CLI commands. P6 exported all requirements as Turtle RDF with dependency links and quality attribute annotations.

**Implementation** ($25.06, 28 requirements): All 28 requirements implemented and verified on the first attempt. Zero retries needed. The implementation spanned:
- 6 foundation requirements (namespace, config, ontology classes, SPARQL collection, pipeline wiring)
- 3 P3 ADR generation requirements (project ADR section, prompt wiring, scope annotation)
- 2 conflict detection requirements (ADRScopeCoherenceShape, migration function)
- 3 project-init requirements (workflow module, CLI commands)
- 4 implementation loop requirements (project_id support, ADR loading, CLI wiring, P6 export)
- 10 test requirements (unit, integration, SHACL validation)

Test suite after completion: 1,542 tests passing (31 new tests from idea 69).

### 12.5 What Worked Well

1. **Structured output quality**: D5 research briefs consistently produce well-prioritized research questions with business rationale, mandatory feature lists, and constraints that downstream phases can consume directly.

2. **PRD granularity**: P6 exports produce atomic, single-file requirements with dependency graphs, ADR links, and quality attribute annotations. The WPF metric ensures each requirement has enough descriptive content.

3. **Commit traceability**: The `impl(prd:req-N-M-K)` commit message format creates a perfect audit trail. Any commit can be traced back through requirements, ADRs, architecture decisions, gap analysis, personas, and the original idea.

4. **Research experiments**: R5 produces real, executable Python experiments that validate design decisions before implementation. This has caught issues (like the pyshacl `sh:severity` placement bug) that would otherwise surface during implementation.

5. **Self-improvement loop**: Each idea improves tulla itself. Idea 67 built fact persistence, idea 73 closed the adoption gap, idea 64 added granularity enforcement, idea 58 completed research modes. Each makes subsequent runs more reliable.

6. **Cost efficiency**: A full discovery-to-implementation run costs $35-45, producing 15-28 verified requirements with architecture governance. The planning phase alone (D+P) runs in ~35 minutes for ~$10.

### 12.6 Known Limitations

1. **A-Box/SHACL validation gap**: The ontology server's `/validate` endpoint has a URI compaction bug that prevents SHACL validation of A-Box instances. This forced disabling `shape_registry` in the research pipeline. The fix is identified (replace substring check with SPARQL ASK) but not yet deployed.

2. **Commit phase path bug**: The implementation loop constructs doubled file paths (`ralph/ralph/src/...`) for git staging, causing all commits to be skipped. Implementation still passes verification, but changes are uncommitted. This is a string-concatenation bug in the commit phase's path construction.

3. **Claude CLI hanging**: Research phases R2 and R5 occasionally produce complete output files but the Claude CLI process hangs afterward (possibly doing additional codebase exploration beyond the output). Workaround: manually construct checkpoints from completed output files.

4. **No SPARQL UPDATE exposure**: The ontology server's Oxigraph store supports `DELETE WHERE` but this capability is not exposed via HTTP API or MCP tools. `promote_adr()` falls back to individual `add_triple`/`remove_triple` calls.

5. **Iteration overhead in early ideas**: Work directory counts show significant iteration -- idea 64 had 15 work directories (8 for implementation). The pipeline has become more reliable over time (recent ideas typically need only 1 run per pipeline stage).

---

## 13. Summary

Tulla is an ontology-driven software engineering agent that transforms idea seeds into verified, committed code through a four-stage pipeline (Discovery, Research, Planning, Implementation). Its distinguishing features are:

- **IntentField annotations** that automatically extract and persist decision-critical phase outputs as RDF triples
- **Cross-agent fact flow** via SPARQL queries against a shared knowledge graph
- **SHACL validation** of phase outputs against structural shape constraints
- **Traceability** from commit to requirement to ADR to quality attribute to persona need to original idea
- **Architecture governance** through project-level ADR injection and iSAQB quality attribute vocabulary
- **Self-improvement** through bootstrapping -- tulla builds its own features

The system has been self-hosting for 7 days, producing 166 implementation commits across 10 ideas, with 1,542 passing tests. The total cost of the bootstrapping effort is approximately $350-400, producing a complete pipeline framework that transforms paragraph-length idea descriptions into fully implemented, architecturally governed, traceability-annotated code.
