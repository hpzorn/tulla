# The Neuro-Symbolic Ralph Workflow

## A Knowledge-Graph-Grounded Autonomous System for Idea-to-Implementation

---

## 1. Introduction

Modern AI coding assistants operate in a single session: read code, generate code, move on. They carry no persistent architectural knowledge, enforce no design constraints, and forget everything between conversations. The result is **architecture by accident** — code that works but drifts from its intended design with every session.

The **ideasralph** project takes a fundamentally different approach. It combines the generative power of large language models (the *neural* component) with formal ontologies, knowledge graphs, and SHACL validation (the *symbolic* component) to create an autonomous workflow that doesn't just write code — it reasons about architecture, enforces design constraints, and maintains traceable knowledge across its entire lifecycle.

This document describes the system in full: its architecture, its five specialized agents, its three-ontology stack, its implemented capabilities, and its roadmap for future development.

### 1.1 The Core Thesis

> **Neural generation without symbolic grounding produces plausible but unverifiable output. Symbolic reasoning without neural generation produces correct but rigid systems. The combination — neuro-symbolic AI — produces output that is both generative and verifiable.**

In concrete terms:

- An LLM can generate an architecture design, but it cannot check whether that design satisfies ISO 25010 quality attributes without a formal quality model.
- An ontology can represent architectural patterns and their tradeoffs, but it cannot generate new designs from natural-language requirements.
- Combined: the LLM generates designs while querying the ontology for patterns, validates decisions against SHACL shapes, and records its work as machine-readable RDF facts that persist across sessions.

### 1.2 Lineage

The system extends Geoffrey Huntley's **Ralph Wiggum Loop** — a technique where an LLM agent repeatedly reads requirements and implements them in a loop until done. ideasralph extends this with:

- **Discovery** — understanding what exists before building
- **Planning** — ontology-grounded architecture design
- **Research** — PhD-level investigation of unknowns
- **Epistemology** — systematic idea generation
- **Persistent knowledge** — a triplestore that survives across sessions

The name "Ralph" is retained as homage to the original technique, but the system has evolved far beyond the simple loop it started as.

---

## 2. System Architecture

### 2.1 The Three Layers

The system is organized into three layers:

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Layer                              │
│  discovery-ralph │ planning-ralph │ research-ralph           │
│  implementation-ralph │ epistemology-ralph                    │
├─────────────────────────────────────────────────────────────┤
│                   Semantic Layer                             │
│  Ontology Server (T-Box)  │  Knowledge Graph (A-Box)        │
│  iSAQB Ontology │ PRD Ontology │ Code Ontology              │
│  SHACL Validator │ SPARQL Engine │ Wikidata Federation       │
├─────────────────────────────────────────────────────────────┤
│                  Infrastructure Layer                        │
│  Oxigraph Triplestore │ MCP Protocol │ Claude CLI            │
│  Visual Tools (12 servers) │ LaunchD Service Management     │
└─────────────────────────────────────────────────────────────┘
```

**Agent Layer**: Five bash scripts, each spawning Claude subprocesses with specific tool permissions and time-boxed phases. Agents are stateless — all persistent state lives in the semantic layer.

**Semantic Layer**: The Ontology Server exposes both T-Box (schema/terminological knowledge) and A-Box (assertional/instance knowledge) through MCP tools. Agents query ontologies via SPARQL and store facts in the knowledge graph.

**Infrastructure Layer**: Oxigraph provides the RDF triplestore with RocksDB persistence. The MCP (Model Context Protocol) provides the tool interface between Claude and the servers. Twelve visual tool servers handle rendering.

### 2.2 The MCP Tool Ecosystem

All agent-to-knowledge communication happens through MCP tools. The ontology server alone exposes 50+ tools organized by function:

| Category | Tool Count | Examples |
|----------|-----------|----------|
| Ontology Management (T-Box) | 13 | `list_ontologies`, `query_ontology`, `add_triple`, `validate_instance` |
| Idea Management | 12 | `create_idea`, `get_idea`, `update_idea`, `query_ideas` |
| Seed Capture | 4 | `capture_seed`, `list_seeds`, `crystallize_seed` |
| Lifecycle Management | 6 | `set_lifecycle`, `get_workable_ideas`, `get_ralph_status` |
| Dependency Tracking | 4 | `add_dependency`, `remove_dependency`, `get_idea_dependencies` |
| Agent Memory (A-Box) | 5 | `store_fact`, `recall_facts`, `forget_fact`, `recall_recent_facts` |
| Wikidata Federation | 4 | `lookup_wikidata`, `query_wikidata`, `search_wikidata_cache` |
| Cross-Graph Queries | 8 | `sparql_query`, `get_graph_stats`, `export_idea_markdown` |

Additionally, twelve visual tool servers provide rendering capabilities:

| Server | Tools | Output |
|--------|-------|--------|
| growth-chart | `render_chart` | Bar, line, area, gauge, pie, bullet charts |
| kpi-cards | `render_kpi` | KPI metric card sets |
| process-flow | `render_flow`, `render_timeline_vao`, `render_state_diagram` | Process diagrams, timelines, state machines |
| compose-scene | `render_scene`, `render_container_diagram` | Icon scenes, architecture diagrams |
| isotype | `render_isotype`, `render_waffle`, `render_beeswarm` | Statistical visualizations |
| quadrant-grid | `render_quadrant_grid` | 2x2 strategic matrices |
| service-matrix | `render_service_matrix` | Multi-column capability matrices |
| compose-map | `render_map` | Geographic maps with markers |
| distributions | `render_ridgeline` | Ridgeline/joy plots |
| nano-banana | `generate` | AI image generation (Gemini/Replicate) |
| analog-clock | `render_clock` | Analog clock visualizations |
| calendar-view | `render_calendar` | Calendar views with annotations |

### 2.3 Knowledge Graph Architecture

The knowledge graph uses a named-graph architecture within Oxigraph:

```
Default Graph          → Ideas (SKOS:Concept instances)
                         67 ideas, lifecycle metadata, relationships

Memory Graph           → Agent Facts (subject-predicate-object triples)
  <.../graphs/memory>    599 facts across 5 PRD contexts
                         Used by implementation-ralph for requirements

Wikidata Graph         → Cached Wikidata entities
  <.../graphs/wikidata>  Federation with wikidata.org SPARQL endpoint
```

**Current Scale**: 5,266 RDF triples, 599 stored facts, 67 ideas managed.

---

## 3. The Three-Ontology Stack

The symbolic backbone of the system consists of three complementary ontologies, totaling approximately 200KB of formal knowledge.

### 3.1 iSAQB Ontology — Architectural Knowledge

**Namespace**: `http://impl-ralph.io/isaqb#`
**Size**: 1,824 lines, 1,318 triples
**Purpose**: Encodes the iSAQB (International Software Architecture Qualification Board) body of knowledge as queryable RDF.

This is the largest and most complex ontology in the system. It provides the architectural vocabulary that Planning-Ralph uses to design solutions.

#### Quality Attributes (ISO 25010:2023)

The ontology encodes the complete ISO 25010:2023 quality model with 8 top-level attributes and 23 sub-attributes:

- **Functional Suitability** — Completeness, Correctness, Appropriateness
- **Performance Efficiency** — Time Behaviour, Resource Utilization, Capacity
- **Compatibility** — Co-Existence, Interoperability
- **Interaction Capability** — Learnability, Operability, User Error Protection, Accessibility, UI Aesthetics
- **Reliability** — Availability, Fault Tolerance, Recoverability, Maturity
- **Security** — Confidentiality, Integrity, Non-Repudiation, Accountability, Authenticity
- **Maintainability** — Modularity, Reusability, Analysability, Modifiability, Testability
- **Flexibility** — Adaptability, Installability, Replaceability

Critically, the ontology also encodes **tradeoff relationships** between quality attributes via `isaqb:conflictsWith` and `isaqb:supportedBy`. For example:

```turtle
isaqb:PerformanceEfficiency isaqb:conflictsWith isaqb:Maintainability .
isaqb:PerformanceEfficiency isaqb:conflictsWith isaqb:Security .
isaqb:Maintainability isaqb:supportedBy isaqb:Flexibility .
```

This allows agents to automatically identify tradeoffs when selecting quality goals — something no LLM can do reliably from training data alone.

#### Design Principles (23 total)

Organized into five categories:

- **Abstraction**: Abstraction
- **Modularization**: Information Hiding, Encapsulation, Separation of Concerns, Loose Coupling, High Cohesion, OCP, DIP, SRP, ISP, Acyclic Dependencies, Common Closure, Common Reuse
- **Conceptual Integrity**: Conceptual Integrity, Least Surprise, Liskov Substitution
- **Complexity Reduction**: KISS, YAGNI, DRY
- **Robustness**: Expect Errors, Postel's Law

#### Architectural Patterns (11)

Each pattern is linked to the quality attributes it addresses and the principles it embodies:

| Pattern | Addresses | Challenges | Embodies |
|---------|-----------|-----------|----------|
| Layered Architecture | Maintainability, Testability | Performance | SoC, Loose Coupling |
| Pipes and Filters | Reusability, Modifiability | — | SoC, SRP |
| Microservices | Flexibility, Modularity | Reliability, Performance | SoC, High Cohesion |
| Ports and Adapters | Testability, Maintainability, Flexibility | — | DIP, SoC, Info Hiding |
| CQRS | Performance, Modularity | Analysability | SoC, SRP |
| Event Sourcing | Recoverability, Non-Repudiation | Capacity, Operability | — |
| MVC | Maintainability, Testability | — | SoC |
| Plugin | Flexibility, Modifiability | — | OCP, DIP |
| Blackboard | Modifiability, Reusability | — | — |
| Broker | Interoperability | Performance | — |
| SOA | Interoperability, Reusability | Performance | — |

An agent can query: *"Which patterns address Testability?"* and receive `LayeredArchitecture`, `PortsAndAdapters`, `MVC` — grounded in formal relationships, not LLM hallucination.

#### Additional Encoded Knowledge

- **12 Design Patterns** (Adapter, Facade, Proxy, Observer, Strategy, Template Method, Visitor, Interpreter, Combinator, Factory, Gateway, Bridge) with principle links
- **4 Architectural Views** (Context, Building Block, Runtime, Deployment) per ISO/IEC/IEEE 42010
- **15 Cross-Cutting Concerns** (Persistence, Security, Logging, Caching, i18n, etc.)
- **8 Stakeholder Roles** (Product Owner, Developer, Architect, Tester, Operator, etc.)
- **12 arc42 Template Sections** for documentation structure
- **5 Evaluation Methods** (ATAM, DCAR, SAAM, LASR, Architecture Conformance Check)
- **Risk and Technical Debt** classes with severity and remediation properties
- **Constraint Types** (Technical, Organizational, Regulatory, Convention)
- **Coupling Types** (Use, Message, Composition, Creation, Inheritance, Temporal, Data, DataType)

#### SHACL Validation Shapes

The ontology includes five SHACL shapes with a two-tier severity model:

| Shape | Tier 1 (Violation) | Tier 2 (Warning) |
|-------|--------------------|-------------------|
| ADRShapeStrict | Must have: label, context, rationale, consequences, status | Should have: ≥2 options, ≥1 quality attribute |
| QualityScenarioShapeStrict | Must have: stimulus, response, response measure | Should refine 1 quality attribute, specify environment |
| RiskShapeStrict | Must have: label, severity | Should have: mitigation, likelihood |
| QualityGoalShapeStrict | Must reference ≥1 quality attribute | — |
| RequirementQualityShape | — | Should link to ≥1 quality attribute |

### 3.2 PRD Ontology — Requirements Specification

**Namespace**: `http://impl-ralph.io/prd#`
**Size**: 301 lines
**Purpose**: Models implementation requirements as machine-readable RDF for consumption by implementation-ralph.

The PRD ontology is the bridge between planning and implementation. Planning-Ralph's P6 phase exports requirements as instances of `prd:Requirement`, and Implementation-Ralph reads them back via `recall_facts()`.

**Core Classes**:

- `prd:Requirement` — A single implementable task with title, description, status, priority, phase, files, action, verification criteria, and dependency links.
- `prd:AcceptanceCriteria` — Specific success conditions attached to requirements.

**Status Lifecycle**: `Pending → InProgress → Complete` (or `→ Blocked`)

**Priority Levels**: `P0` (Critical Path), `P1` (Important), `P2` (Nice to Have)

**Key Property — `prd:action`**: Specifies whether to `create` a new file or `modify` an existing one. For modifications, `prd:description` includes exact insertion points and code in the file's **native language** (bash for `.sh`, markdown for `.md`, Typst for `.typ`). Implementation-Ralph must never rewrite a file in a different language.

**Cross-Ontology Links**:

```turtle
prd:Requirement isaqb:addressesQuality isaqb:QualityAttribute .
prd:Requirement isaqb:justifiedBy isaqb:ArchitectureDecision .
prd:Requirement isaqb:verifiedByScenario isaqb:QualityScenario .
```

This creates traceability from requirements through architecture decisions to quality attributes.

### 3.3 Code Ontology — Implementation Traceability

**Namespace**: `http://impl-ralph.io/code#`
**Size**: 159 lines
**Purpose**: Maps code artifacts to requirements and architectural patterns for traceability.

Designed for 71% complexity reduction vs. a full code ontology while covering 100% of trace scenarios.

**Component Types**: File, Module, Class, Function, Variable, Test

**Structural Relationships**: `contains`, `imports`, `calls`, `extends`, `tests`

**Cross-Ontology Links**:

```turtle
code:Function trace:implements prd:Requirement .
code:Test trace:verifies prd:Requirement .
code:Class isaqb:realizesPattern isaqb:ArchitecturalPattern .
code:Module isaqb:appliesPrinciple isaqb:DesignPrinciple .
```

This completes the traceability chain: **Quality Attribute → Architecture Decision → Requirement → Code → Test**.

---

## 4. The Five Ralph Agents

### 4.1 Discovery-Ralph (D1–D5)

**Purpose**: Understand what exists, who needs it, and why it matters — before any code is written.

**Duration**: ~90 minutes across 5 phases

Discovery-Ralph operates in two modes:

- **Upstream** (pre-research): Produces a research brief for Research-Ralph
- **Downstream** (post-research): Integrates research findings into a product specification

The mode is auto-detected from the idea's lifecycle state.

#### Phase Breakdown

**D1 — Technical Inventory** (15 min): Audits existing tools, skills, libraries, and prior work related to the idea. Searches the idea pool for related ideas, scans the codebase for relevant implementations. Output: tables of existing capabilities with relevance ratings.

**D2 — Persona Discovery** (20 min): Identifies 2–4 user personas using the Jobs-to-be-Done framework. Maps pain points, desired outcomes, and context of use for each persona. This grounds the idea in actual user needs rather than abstract technical goals.

**D3 — Value Mapping** (20 min): Assesses user value (pain reduction, time savings, quality improvement), business value (revenue, cost reduction, competitive advantage), and technical value (reusability, debt reduction, platform enhancement). Rates each dimension 1–5 and produces an effort/impact matrix.

**D4 — Gap Analysis** (15 min): Identifies what's missing. Categories: knowledge gaps (candidates for research), technical gaps (what doesn't exist), quality-attribute gaps (queried from iSAQB ontology via SPARQL), resource gaps, and integration gaps. This is the first phase that uses the symbolic layer — querying `isaqb:QualityAttribute` and `isaqb:ArchitecturalPattern` for architectural risk assessment.

**D5 — Integration** (20 min): In upstream mode, produces a research brief with prioritized research questions. In downstream mode, integrates research findings with discovery to produce an actionable product specification with user stories, requirements, UX flow, and launch plan.

### 4.2 Planning-Ralph (P1–P6)

**Purpose**: Create actionable, architecture-conformant implementation plans using existing capabilities.

**Duration**: ~90 minutes across 6 phases

This is where the neuro-symbolic integration is most visible. Planning-Ralph doesn't just generate a plan — it queries ontologies, validates against SHACL shapes, and exports machine-readable requirements.

#### Phase Breakdown

**P1 — Discovery Context Load** (5 min): Synthesizes discovery documents (D1–D5) and optional downstream research findings (R3–R6) into a unified planning context. If research exists, it confirms that previously-blocking questions have been answered.

**P2 — Codebase Analysis** (20 min): Deep analysis of actual implementations — skill definitions, MCP server architectures, integration patterns, reusable components. The goal is to understand how things work today so the plan maximizes reuse over new code.

**P3 — Architecture Design** (15 min): The symbolic core. This phase:

1. Loads the iSAQB schema context (a ~2,000 token prompt extracted from the ontology)
2. Selects the top 3–5 quality goals from ISO 25010:2023
3. Queries `isaqb:conflictsWith` to identify tradeoffs between selected goals
4. Selects architectural patterns that `isaqb:addresses` the desired quality attributes
5. Documents architecture decisions (ADRs) with options, rationale, and consequences
6. Writes testable quality scenarios (stimulus → environment → response → measure)
7. Maps cross-cutting concerns to the design
8. Assesses risks and links them to mitigations

The agent generates SPARQL queries on the fly:

```sparql
SELECT ?pattern ?label WHERE {
  ?pattern isaqb:addresses isaqb:Maintainability .
  ?pattern rdfs:label ?label .
}
```

This grounds architecture design in formal knowledge rather than relying solely on LLM training data.

**P4 — Implementation Plan** (20 min): Creates file-level, task-level specifications organized into priority phases (P0-Critical, P1-Important, P2-Nice to Have). Each task specifies files to create or modify, actions, pseudocode, dependencies, and verification steps.

**P5 — Research Requests** (5 min): Checks whether the plan can proceed or has blocking unknowns. Outputs either `ready` (proceed to P6) or `blocked` (route to Research-Ralph). If blocked, emits structured research requests with the blocking task, specific question, rationale, and suggested approach.

**P6 — RDF Export** (10 min): Converts the implementation plan into RDF requirements and stores them as facts in the knowledge graph. Each task becomes a `prd:Requirement` instance with all properties. Uses `store_fact()` (A-Box) — not `add_triple()` (T-Box). This is the handoff point to Implementation-Ralph.

### 4.3 Research-Ralph (R1–R6)

**Purpose**: PhD-level research protocol for resolving unknowns that block planning or implementation.

**Duration**: ~2.5 hours across 6 phases

Research-Ralph is invoked when Planning-Ralph encounters questions it cannot answer from existing knowledge. It follows a rigorous protocol modeled on academic research methodology.

#### Phase Breakdown

**R1 — Prior Art Scan** (15 min): Determines whether the idea is NOVEL, PARTIAL, or DERIVATIVE. Searches for existing tools, academic papers, GitHub repositories. If `derivative` — the idea already exists in satisfactory form — the idea is invalidated and the pipeline stops.

**R2 — Sub-Aspect Research** (20 min): Decomposes the idea into 3–6 distinct sub-aspects and researches each independently. For each: existing research, state of the art, open challenges, and relevance to the idea.

**R3 — Research Question Formulation** (15 min): Defines 2–4 precise, falsifiable research questions. Each RQ has a type (Empirical, Theoretical, Engineering, Comparative), hypothesis, validation approach, and success criteria. RQs must be specific, falsifiable, actionable, and scoped.

**R4 — Deep Literature Review** (30 min): Comprehensive review per RQ. Searches academic databases (arXiv, Google Scholar, ACM DL, IEEE Xplore). For each RQ: theoretical foundations, relevant empirical studies, methodologies, contradictions, and implications. Aims for 10+ sources total with proper citations.

**R5 — Research Execution** (60 min): The empirical phase. For each RQ, executes the appropriate approach: experiments with data collection and statistical analysis, formal proofs, minimal prototypes with benchmarks, or systematic comparisons. All code is Python 3.11+ and stored in an `experiments/` subdirectory with a README per experiment. This phase can use the `nano-banana` MCP tool for AI image generation if the research involves visual artifacts.

**R6 — Synthesis** (15 min): Consolidates findings into a go/no-go decision:

- **PROCEED**: Feasible, key success factors identified, recommendations for implementation
- **INVALIDATE**: Fundamental flaw discovered, abandon idea, alternatives offered
- **PARK**: Human decision needed, options listed with tradeoffs

The synthesis is appended to the idea in the knowledge graph, creating a persistent research record.

### 4.4 Implementation-Ralph

**Purpose**: Ontology-driven requirement execution with dependency-aware ordering and independent verification.

**Duration**: Variable (20 iterations max, ~10 min per requirement)

This is the agent that turns plans into code. Its key innovation: **all work is driven by RDF facts in the knowledge graph, not markdown files**. This creates machine-readable, dependency-aware implementation.

#### Five-Phase Loop (per requirement)

**Phase 1 — Find Next Ready Requirement**: Queries all `prd:Requirement` facts in the PRD context. A requirement is READY if its status is `Pending` and all requirements it `dependsOn` have status `Complete`. Selects by priority (P0 → P1 → P2), then by taskId. Returns `FOUND_READY`, `ALL_COMPLETE`, or `BLOCKED`.

**Phase 2 — Implement**: Reads the requirement's description, files, and action from the knowledge graph. For `create` actions, writes new files (Python 3.11+ for new code). For `modify` actions, reads and edits existing files **in their native language** — bash for `.sh`, markdown for `.md`, Typst for `.typ`. This is a hard constraint enforced by the system prompt.

**Phase 3 — Git Commit**: Creates a structured commit: `impl({req-id}): {title}`. One commit per requirement provides fine-grained traceability in git history.

**Phase 4 — Verify**: An independent verification step using a fresh Claude subprocess with read-only tools. Checks acceptance criteria, runs verification steps, and cross-checks against iSAQB concepts (architecture decisions, quality attributes, design patterns). Returns `VERIFY_PASS` or `VERIFY_FAIL`.

**Phase 5 — Update Status**: Updates the requirement's status in the knowledge graph using the forget-then-store protocol: first removes the old status fact, then stores the new one. This strict ordering prevents stale data.

#### Retry and Recovery

On `VERIFY_FAIL`: reverts the git commit via `git revert`, retries implementation (up to `MAX_RETRIES`), and marks as `Blocked` if all retries exhausted.

On crash: a trap handler logs the interrupted state and provides resume commands (`--no-clean` to resume from current state, `--check` to audit).

### 4.5 Epistemology-Ralph

**Purpose**: Systematic idea generation using epistemological protocols.

**Duration**: Variable (single run)

Epistemology-Ralph is the creative engine. It uses formal protocols from philosophy of science to generate new ideas that are grounded in existing knowledge rather than random brainstorming.

#### Six Modes

**Pool-Driven** (default): Analyzes the idea pool for gaps, combination opportunities, and assumption inversions. Protocols: Gap Analysis, Conceptual Combination, Assumption Inversion.

**Idea-Focused** (`--idea N`): Expands from a specific idea. Protocols: Extension, Lateral Transfer, Assumption Inversion, Decomposition, Synthesis with related ideas.

**Domain-Focused** (`--domain "X"`): Explores a specific domain for novel ideas using web research. Protocols: Gap Analysis, Analogical Transfer, Assumption Inversion.

**Problem-Driven** (`--problem "Q"`): Generates solutions to a specific question. Protocols: Direct Approach, Analogical Transfer, Assumption Inversion, Decomposition.

**Contradiction-Driven** (`--thesis A --antithesis B`): Hegelian dialectical synthesis. Identifies the valid kernel in each position, determines what must be preserved, and synthesizes a higher-order resolution. Resolution types: Transcendence, Integration, Reframing.

**Signal-Driven** (`--url URL`): Reacts to external content (papers, articles). Extracts key claims and integrates them with existing pool ideas. Types: Extension, Challenge, Application, Combination.

Generated ideas are automatically saved to the idea pool with full metadata (protocol used, source ideas, mode) via `capture_seed()`.

---

## 5. The Workflow Pipeline

### 5.1 Primary Flow

```
                         Epistemology-Ralph
                              │
                         (generates seeds)
                              │
                              ▼
                         Idea Pool
                              │
                    (select from backlog)
                              │
                              ▼
                    Discovery-Ralph (D1–D5)
                         │         │
                  (upstream)    (downstream)
                         │         │
                         ▼         │
                  Research-Ralph   │
                    (R1–R6)       │
                         │         │
                    (proceed)      │
                         │         │
                         ▼         ▼
                    Planning-Ralph (P1–P6)
                         │         │
                    (ready)    (blocked)
                         │         │
                         │         ▼
                         │    Research-Ralph
                         │         │
                         │    (findings)
                         │         │
                         │         ▼
                         │    Planning-Ralph
                         │    (retry P1–P5)
                         │         │
                         ▼         ▼
                    P6: RDF Export
                         │
                    (prd:Requirement facts)
                         │
                         ▼
                Implementation-Ralph
                    (per-requirement loop)
                         │
                    ┌────┴────┐
                    │         │
               VERIFY_PASS  VERIFY_FAIL
                    │         │
               (commit)    (revert + retry)
                    │         │
                    ▼         ▼
               Status: Complete / Blocked
```

### 5.2 Lifecycle State Machine

Ideas traverse a well-defined lifecycle managed by the knowledge graph:

```
seed → sprout → backlog → researching → researched →
  decomposing → scoped → implementing → completed
                 ↓                          ↓
               blocked                  invalidated / failed
                 ↓
               parked
```

Each transition is recorded in the knowledge graph with timestamps and reasons. The `get_ralph_status()` tool provides a dashboard view of the entire pipeline.

### 5.3 Decision Points and Routing

The workflow includes explicit decision points that control routing:

| Point | Decision | Outcomes |
|-------|----------|----------|
| R1 (Prior Art) | Is the idea novel? | `novel` → continue, `derivative` → invalidate |
| R6 (Synthesis) | Is it feasible? | `proceed` → PRD, `invalidate` → stop, `park` → human decision |
| D5 (Integration) | Ready or needs research? | `research` → Research-Ralph, `implement` → Planning-Ralph |
| P5 (Research Requests) | Any blocking unknowns? | `ready` → P6 export, `blocked` → Research-Ralph |

---

## 6. Implemented Ideas

The following ideas have been fully implemented and are operational in the system.

### 6.1 Idea-20: Full Knowledge Graph Backend

**Status**: Completed (2026-01-26)

The foundational infrastructure — an Oxigraph-backed triplestore with RocksDB persistence, exposed through the MCP protocol. Provides T-Box (ontology management) and A-Box (fact storage) operations, SPARQL querying across named graphs, and SHACL validation.

This was the enabler for everything that followed. Without persistent, queryable knowledge storage, the agents would have no memory between sessions.

### 6.2 Idea-21: Context-Graph Memory

**Status**: Completed (2026-01-26)

Added the A-Box memory layer to the knowledge graph — `store_fact()`, `recall_facts()`, `forget_fact()`. Facts are context-tagged triples (subject-predicate-object) with confidence scores and timestamps.

This is what Implementation-Ralph uses to read requirements from the knowledge graph. Planning-Ralph's P6 phase stores requirements as facts, and Implementation-Ralph recalls them — creating a machine-readable handoff that survives across sessions.

### 6.3 Idea-16: PhD Research Protocol

**Status**: Completed (2026-01-30)

The full R1–R6 research protocol implemented in `research-ralph.sh`. Six time-boxed phases following academic methodology: prior art scan, sub-aspect research, question formulation, literature review, research execution, and synthesis.

Key innovation: the `--start-from R#` flag allows resuming interrupted research without re-running earlier phases, provided output files exist.

### 6.4 Idea-17: Epistemology-Ralph

**Status**: Completed (2026-01-30)

Systematic idea generation with six modes (pool, idea, domain, problem, contradiction, signal) and multiple epistemological protocols (gap analysis, analogical transfer, assumption inversion, Hegelian synthesis, etc.).

This agent has generated 13 seeds that have been captured in the idea pool, including ideas about cognitive load ontologies, compositional argumentation, adversarial knowledge graph testing, and semantic bridge protocols.

### 6.5 Idea-23: Claude Memory Skill

**Status**: Completed (2026-01-27)

Research into persistent memory for Claude agents. The PhD protocol completed with a GO decision — the research validated that knowledge-graph-backed memory is viable and identified key design patterns for fact retrieval and context management.

### 6.6 Idea-26: Semantic Composition Patterns

**Status**: Completed (2026-01-27)

Research into VAO (Visual Artifacts Ontology) composition patterns — how visual elements combine semantically. The findings informed the design of the visual tools' composition engine.

### 6.7 Idea-36: A-Box Hygiene Protocol

**Status**: Completed (2026-01-30)

The `hygiene-lib.sh` shared library for managing A-Box state. Provides:

- **Pre-flight reset**: Clears all requirement statuses to `Pending` before a fresh implementation run
- **Stale fact detection**: Identifies facts from crashed subprocesses
- **Check mode**: Audits ontology state without implementing (counts requirements by status, identifies dependency issues)

This was critical for making Implementation-Ralph reliable — without hygiene, crashed runs would leave the knowledge graph in inconsistent states.

### 6.8 Idea-41: iSAQB Architecture Knowledge Base

**Status**: Completed (2026-01-31)

The marquee implementation — 76KB of formal architectural knowledge encoded as an OWL/SHACL ontology. 26 classes, 23 design principles, 31 quality attributes with tradeoff relationships, 11 architectural patterns, 12 design patterns, 4 views, 15 cross-cutting concerns, 5 SHACL shapes.

Wired into three Ralph agents:

- **Planning-Ralph P3**: Architecture design queries patterns, principles, quality tradeoffs
- **Discovery-Ralph D4**: Gap analysis checks quality-attribute gaps and architectural risks
- **Implementation-Ralph Phase 4**: Verification cross-checks against iSAQB concepts

This is the core neuro-symbolic contribution: formal architectural knowledge that LLM agents can query, reason about, and validate against — transforming architecture design from hallucination-prone generation into grounded, verifiable reasoning.

### 6.9 Idea-24: VAO Background and Scene Composition

**Status**: Completed (2026-01-30)

Empirical research into AI composition of visual backgrounds and scenes. Investigated how AI image generation (via nano-banana) handles semantic composition and identified failure modes.

---

## 7. Ideas In Progress

### 7.1 Idea-51: Ontology Server Security

**Status**: Partially Implemented

Adding Bearer token authentication to the ontology server:

- ✅ FastAPI middleware for Bearer auth
- ✅ MCP SSE auth coverage verified
- ✅ Credential setup script (`setup_auth.py`)
- ⏳ Verification scripts pending
- ⏳ Integration tests pending

Authentication is opt-in via `ONTOLOGY_AUTH_ENABLED=1` environment variable, allowing gradual rollout.

### 7.2 Idea-34: Implementation-Ralph Ontology-Driven Loop

**Status**: Researching (5 iterations)

The design and refinement of the ontology-driven implementation loop — mapping requirements to code components via RDF links. This idea produced the current implementation-ralph.sh through multiple research iterations.

### 7.3 Idea-27: VAO Semantic Preservation in AI Composition

**Status**: Implementing

Research into how AI image generation (nano-banana) corrupts VAO semantics during composition. Investigating what changes, when composition fails, architecture options, and metrics for semantic preservation.

### 7.4 Idea-50: Merge Ontology Viewer into Ontology Server

**Status**: Seed (599 requirements tracked)

Consolidating a standalone dashboard viewer into the main ontology server process. Eliminates network synchronization overhead and simplifies deployment.

---

## 8. Future Ideas — The Roadmap

### 8.1 Architecture Evolution Track

**Idea-42: arc42-Structured Architecture Design** (Backlog)

Transform Planning-Ralph's P3 phase into an arc42-compliant multi-output system. Instead of a single architecture document, P3 would produce structured sub-phase outputs (P3a–P3j) corresponding to arc42 sections: solution strategy, building block view, runtime view, deployment view, cross-cutting concepts, etc.

**Blocked by**: Idea-41 (completed) — ready to proceed.

**Idea-44: Quality-Traced Full Pipeline** (Seed)

End-to-end iSAQB traceability from discovery through implementation. Every requirement would link to quality attributes, every design decision would reference quality scenarios, and every code artifact would trace back to the requirement it satisfies. The traceability chain: Quality Attribute → Architecture Decision → Requirement → Code → Test.

**Idea-45: Architecture-Aware Implementation** (Seed)

Enhance Implementation-Ralph to consult the iSAQB ontology during code generation — not just during verification. The implementer would query patterns and principles before writing code, not just check conformance after.

**Idea-46: Architectural Drift Detector** (Seed)

Continuous conformance checking that monitors the codebase for deviations from the intended architecture. Would run as a background process, comparing code structure against the ontology and flagging violations.

**Idea-49: ADRs as Agent Guard Rails** (Seed)

Use architecture decision records (stored as `isaqb:ArchitectureDecision` in the ontology) as active constraints on agent behavior. Instead of passive documentation, ADRs would be machine-readable rules that agents must follow.

**Idea-43: Evaluation-Ralph** (Seed)

A new Ralph agent dedicated to architecture quality gates. Would use evaluation methods from the iSAQB ontology (ATAM, DCAR, etc.) to formally evaluate designs before implementation proceeds.

### 8.2 Workflow Evolution Track

**Idea-52: Agile Ralph — Scrum Ceremonies** (Seed)

Replace the linear planning pipeline with agile ceremonies:

- **Backlog Generation**: Coarse-grained user stories from discovery + architecture (replaces monolithic P4)
- **Refinement**: Break items down, apply INVEST criteria, clarify unknowns
- **Sprint Planning**: Estimate story points, select sprint scope, export sprint backlog to RDF
- **Sprint Execution**: Implementation-Ralph with Definition of Done and WIP limits
- **Sprint Review**: Demo shippable increments, track velocity
- **Retrospective**: Capture process improvements, feed action items back into config

Ontology additions: `prd:Sprint`, `prd:storyPoints`, `prd:velocity`, `prd:RetroAction`.

Open question: what is a "sprint" for an autonomous agent? Time-boxed (30 min)? Item-count-boxed (3–5 items)?

**Idea-53: Lightweight Ralph** (Seed)

A simplified workflow for incremental changes (bugfixes, small features, enhancements) that skips the full discovery/planning pipeline but still enforces architectural conformance:

- **Phase 0 — Intake** (~1 min): Classify change type
- **Phase 1 — Context Scan** (~3–5 min): Codebase grep + architecture conformance check
- **Phase 2 — Design Check** (~2–3 min): Pattern conformance + scope guard
- **Phase 3 — Implement + Verify** (variable): Make change with DoD
- **Phase 4 — Record** (~1 min): Store single fact in ontology

Key mechanism: automatic escalation. If the context scan reveals the change is bigger than expected (>3 modules, pattern violations, new infrastructure needed), it routes to full Ralph or Agile Ralph.

Lightweight Ralph is the execution model for individual items *within* an Agile Ralph sprint. The two compose: Agile Ralph manages cadence, Lightweight Ralph handles small-batch work.

**Idea-40: Implementation-Ralph Verified Loop** (Seed)

Address self-assessment bias: the current system has the same LLM session both implementing and verifying. This idea proposes independent verification using a fresh-context LLM subprocess plus git-committed iterations, ensuring the verifier has no shared state with the implementer.

### 8.3 Knowledge and Memory Track

**Idea-48: Temporal Architecture — Versioned A-Box** (Seed)

Add temporal versioning to the knowledge graph so that past states can be queried. Enables "archaeological" queries: *"What was the architecture design for this module three weeks ago?"* or *"How has the quality attribute prioritization changed over time?"*

**Idea-47: A-Box as Universal Agent Memory** (Seed)

Generalize the A-Box fact store beyond implementation requirements to serve as persistent memory for all agents. Agents would store observations, decisions, and learned heuristics as facts that persist across sessions.

### 8.4 Visual and Composition Track

**Idea-30: InstantDeck — AI-Powered Presentation Generator** (Seed)

Transform rough ideas, notes, or outlines into professional slide decks using Typst. Would integrate with the visual tools for diagram generation and the ontology for architectural content.

**Idea-31: Narrative Planner for InstantDeck** (Seed)

An AI that plans the narrative structure of presentations before generating slides. Uses storytelling frameworks to ensure coherent flow.

**Idea-14: VAO Meta-Layer** (Sprout)

A meta-layer for the Visual Artifacts Ontology that encodes visual best practices, style semantics, and composition rules. Would allow agents to reason about *why* a visualization works, not just how to render it.

**Idea-8: Visual Artifacts Ontology Redesign** (Seed)

A comprehensive 113KB domain ontology for visual artifacts. The largest single ontology in the system, covering all visualization types with formal semantics.

### 8.5 Research and Meta-Learning Track

**Idea-19: Wikidata MCP Service** (Researching)

Integrating Wikidata as a grounding source for factual claims. Currently implemented as a cache + SPARQL federation in the ontology server, but the full vision includes proactive fact-checking of LLM outputs against Wikidata.

**Idea-15: Idea Impact Scoring** (Backlog)

Automated scoring of ideas based on their potential impact, feasibility, and strategic alignment. Would use the value mapping framework from Discovery-Ralph (D3) applied retroactively to the entire idea pool.

**Idea-5: Formal Proof Verification** (Seed)

Integrating formal proof systems to verify critical properties of implementations. Goes beyond testing to mathematical proof of correctness for critical code paths.

---

## 9. The Neuro-Symbolic Integration Points

The system's power comes from specific integration points where neural and symbolic capabilities meet.

### 9.1 SPARQL-Grounded Architecture Design (P3)

When Planning-Ralph designs an architecture in P3, it doesn't rely solely on LLM training data. Instead:

1. The LLM identifies the top quality goals (neural: interpreting requirements)
2. It queries `isaqb:conflictsWith` (symbolic: formal tradeoff analysis)
3. It selects patterns that `isaqb:addresses` those goals (symbolic: pattern retrieval)
4. It generates a design using those patterns (neural: creative composition)
5. It validates ADRs against SHACL shapes (symbolic: constraint checking)

The result is architecture that is both creative (novel combinations of patterns) and grounded (every decision traceable to formal quality attributes).

### 9.2 Ontology-Driven Implementation

Implementation-Ralph reads requirements from the knowledge graph, not from markdown files. This means:

- **Dependency ordering is formal**: `prd:dependsOn` creates a DAG that the agent traverses correctly
- **Status tracking is persistent**: A requirement's status survives crashes
- **Verification is cross-referenced**: The verifier can query the ontology to check whether the implementation aligns with architectural patterns

### 9.3 Fact-Based Handoffs

The P6 → Implementation-Ralph handoff uses `store_fact()` / `recall_facts()`, not file I/O. This creates:

- **Machine-readable requirements**: No parsing of markdown needed
- **Context tagging**: Facts are tagged with PRD context (e.g., `prd-41`) so multiple PRDs can coexist
- **Temporal queries**: `recall_recent_facts()` shows what was added recently

### 9.4 SHACL Validation as Quality Gates

SHACL shapes act as quality gates at multiple points:

- **P3 (Architecture Design)**: ADRs validated against `ADRShapeStrict` — must have context, rationale, consequences
- **P3 (Quality Scenarios)**: Scenarios validated against `QualityScenarioShapeStrict` — must have stimulus, response, measure
- **Implementation**: Requirements validated against `RequirementQualityShape` — should link to quality attributes
- **Future (Evaluation-Ralph)**: Full ATAM-style evaluation with SHACL-enforced documentation

### 9.5 Epistemological Idea Generation

Epistemology-Ralph uses symbolic protocols (gap analysis, Hegelian dialectics, analogical transfer) to structure LLM creativity:

- The LLM generates ideas (neural: creative generation)
- But within formal protocols that ensure novelty, groundedness, and traceability (symbolic: epistemological framework)
- Generated ideas are stored as SKOS concepts in the knowledge graph (symbolic: persistent knowledge)

---

## 10. System Metrics and Scale

| Metric | Value |
|--------|-------|
| Total ideas managed | 67 |
| Ideas completed | 9 |
| Ideas in active development | 6 |
| RDF triples in knowledge graph | 5,266 |
| Stored facts (A-Box) | 599 |
| PRD contexts tracked | 5 |
| Ontology files | 3 (200KB total) |
| iSAQB knowledge elements | 196+ |
| Shell script lines (agents) | 6,211 |
| MCP tools available | 70+ |
| Visual tool servers | 12 |
| Git commits (pipeline-generated) | 50+ |
| Work directories created | 675+ |
| Epistemology seeds generated | 13 |

---

## 11. Design Decisions and Tradeoffs

### 11.1 Why Bash for Agents?

The Ralph agents are bash scripts, not Python programs. This is deliberate:

- **Process isolation**: Each phase spawns a fresh Claude subprocess with explicit tool permissions and budget limits. Bash makes this natural via `timeout` and process management.
- **Composability**: Phases chain via file I/O and exit codes. No shared state means no state corruption between phases.
- **Debuggability**: Every phase produces a markdown file. A human can read the intermediate outputs and understand exactly what the agent was thinking.
- **Language agnosticism**: The agents orchestrate Claude, which can write in any language. The orchestration layer doesn't need to be in the implementation language.

The tradeoff: bash is verbose and error-prone for complex logic. The `hygiene-lib.sh` shared library mitigates this by centralizing state management.

### 11.2 Why RDF/SPARQL over SQL?

- **Schema flexibility**: OWL ontologies can evolve without migrations. Adding a new class or property is a triple insert, not a schema change.
- **Cross-ontology queries**: A single SPARQL query can join across iSAQB patterns, PRD requirements, and code components. In SQL, this would require complex JOINs across normalized tables.
- **Standards compliance**: RDF, SPARQL, SHACL, and OWL are W3C standards with rich tooling (Protégé, SHACL validators, etc.).
- **Semantic expressiveness**: `isaqb:ArchitecturalPattern isaqb:addresses isaqb:Maintainability` is self-documenting. The equivalent in SQL would be a foreign key join through an association table.

The tradeoff: RDF/SPARQL has a steeper learning curve and less mainstream tooling than SQL. The MCP abstraction mitigates this — agents call `query_ontology()`, not raw SPARQL.

### 11.3 Why A-Box Facts for Requirements (not T-Box)?

Requirements are stored as A-Box facts (via `store_fact()`), not as T-Box triples (via `add_triple()`). This is because:

- **Requirements are instances, not schema**: A specific requirement ("Add Bearer auth to FastAPI") is an instance of `prd:Requirement`, not a new class.
- **Context tagging**: A-Box facts support context tags (`prd-41`, `prd-51`), allowing multiple PRDs to coexist. T-Box triples are global.
- **Lifecycle management**: Facts can be forgotten (`forget_fact()`) and re-stored when status changes. T-Box triples are meant to be permanent schema definitions.
- **Recall semantics**: `recall_facts(context="prd-41")` returns all requirements for a specific PRD. No SPARQL needed for the common case.

### 11.4 Why Independent Verification?

Implementation-Ralph uses a separate Claude subprocess (Phase 4) for verification, with read-only tool access. This prevents:

- **Confirmation bias**: The implementer cannot "fix" failing tests by changing the test rather than the implementation.
- **Tool scope creep**: The verifier cannot write files, preventing accidental modifications during verification.
- **Budget isolation**: Verification has a separate budget ($2.00 vs. $5.00 for implementation), preventing expensive verification loops.

The tradeoff: two Claude calls per requirement instead of one. The cost is justified by the higher reliability — failed verification triggers a revert-and-retry cycle that catches real issues.

---

## 12. Configuration and Operation

### 12.1 Service Management

The ontology server runs as a macOS LaunchD service:

```
Service: org.semantic-tool-use.ontology-server
Storage: ~/.semantic-tool-use/kg/ (RocksDB)
Logs:    ~/.semantic-tool-use/ontology-server.log
Port:    8420 (HTTP mode) or stdio (MCP mode)
```

### 12.2 Agent Configuration

Each agent reads from a `.conf` file with parameters:

| Parameter | Default | Purpose |
|-----------|---------|---------|
| `MAX_BUDGET_USD` | $5.00 | Maximum API cost per Claude subprocess |
| `SLEEP_INTERVAL` | 3600s | Time between checking for new ideas |
| `INTERACTIVE` | false | Pause between phases for human review |
| `DRY_RUN` | false | Show what would be done without executing |
| `SINGLE_RUN` | false | Process one idea and exit |
| Phase time boxes | Varies | Per-phase timeout (5–60 min) |

### 12.3 Running the Pipeline

```bash
# Generate new ideas
./epistemology-ralph.sh --domain "knowledge graphs"

# Discover context for an idea
./discovery-ralph.sh --idea 42

# Plan implementation
./planning-ralph.sh --idea 42

# Execute requirements
./implementation-ralph.sh --prd prd-42

# Check implementation status
./implementation-ralph.sh --prd prd-42 --check
```

---

## 13. Conclusion

The ideasralph neuro-symbolic workflow demonstrates that LLM agents can do more than generate code — they can reason about architecture, enforce design constraints, and maintain traceable knowledge across their entire lifecycle. The key insight is that **neural generation and symbolic reasoning are complementary**, not competing approaches.

The neural component provides creativity, language understanding, and the ability to work with ambiguous natural-language requirements. The symbolic component provides formal knowledge, constraint enforcement, traceability, and persistence. Neither is sufficient alone; together, they produce output that is both generative and verifiable.

The system is actively evolving. The immediate roadmap includes arc42-structured architecture design (Idea-42), agile sprint ceremonies (Idea-52), lightweight incremental workflows (Idea-53), and architectural drift detection (Idea-46). Each of these extends the neuro-symbolic integration further — from architecture design into execution cadence, quality assurance, and continuous conformance monitoring.

The long-term vision is an autonomous software engineering system where every design decision is grounded in formal architectural knowledge, every implementation is traceable to requirements, every quality attribute is measurable against scenarios, and every process improvement is captured and applied. Not AI that replaces architects, but AI that carries an architect's knowledge into every line of code it writes.

---

*System snapshot: 2026-01-31 — 67 ideas, 5,266 triples, 599 facts, 9 completed implementations, 6 active workstreams.*
