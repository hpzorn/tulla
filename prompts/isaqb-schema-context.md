# iSAQB Architecture Knowledge — Schema Context

Use this ontology schema to guide architecture design decisions.
Query the ontology-server for specific individuals and relationships.

## Namespaces

```turtle
@prefix isaqb: <http://impl-ralph.io/isaqb#> .
@prefix prd:   <http://impl-ralph.io/prd#> .
@prefix code:  <http://impl-ralph.io/code#> .
@prefix trace: <http://impl-ralph.io/trace#> .
```

## T-Box: Classes

### Design Principles (LG 03-04)
- `isaqb:DesignPrinciple` — Fundamental principle guiding decomposition and code structure
- `isaqb:PrincipleCategory` — Grouping: Abstraction, Modularization, ConceptualIntegrity, ComplexityReduction, Robustness

### Quality Attributes (ISO/IEC 25010:2023)
- `isaqb:QualityAttribute` — Measurable system property (8 top-level + sub-attributes)
- `isaqb:QualityCategory` — Top-level grouping (ProductQuality)
- `isaqb:QualityScenario` — Concrete, testable scenario: stimulus → environment → response → measure
- `isaqb:QualityGoal` — Top-3-to-5 prioritized quality attributes per project

### Architectural Patterns (LG 03-08)
- `isaqb:ArchitecturalPattern` — Proven structural solution (Layers, Pipes&Filters, Microservices, Ports&Adapters, CQRS, EventSourcing, etc.)
- `isaqb:DesignPattern` — Component/class-level solution (Adapter, Facade, Proxy, Observer, Strategy, Factory, etc.)
- `isaqb:PatternRelevance` — CPSA-FL relevance: R1 (must-know), R2 (should-know), R3 (may-know)

### Architectural Views (LG 04-05)
- `isaqb:ArchitecturalView` — Context, BuildingBlock, Runtime, Deployment views

### Cross-Cutting Concerns (LG 03-10, arc42 section 8)
- `isaqb:CrossCuttingConcern` — Concern affecting multiple building blocks
- `isaqb:ConcernCategory` — Business/Domain, Architecture/Design, UX, Safety/Security, Under-the-Hood, Development, Operations

### Architecture Decisions
- `isaqb:ArchitectureDecision` — ADR: context, options, decision, consequences
- `isaqb:DecisionStatus` — Proposed, Accepted, Deprecated, Rejected
- `isaqb:DecisionOption` — A considered alternative within a decision

### Stakeholders & Constraints
- `isaqb:StakeholderRole` — ProductOwner, Developer, Architect, Tester, Operator, EnterpriseArchitect, ProjectManager, DomainExpert
- `isaqb:Constraint` — Non-negotiable boundary (Technical, Organizational, Regulatory, Convention)

### Risks & Technical Debt
- `isaqb:Risk` — Severity (Critical/High/Medium/Low), likelihood, mitigation
- `isaqb:TechnicalDebt` — Code/Architectural/Documentation/Test debt

### Documentation
- `isaqb:Arc42Section` — Sections 1-12 of the arc42 template

### Evaluation
- `isaqb:EvaluationMethod` — ATAM, DCAR, SAAM, LASR, ArchConformanceCheck

## Key Properties

### Intra-Ontology Relationships
- `isaqb:addresses` — Pattern/Decision → QualityAttribute (positive effect)
- `isaqb:challenges` — Pattern/Decision → QualityAttribute (negative effect)
- `isaqb:embodies` — Pattern → DesignPrinciple
- `isaqb:conflictsWith` — QualityAttribute ↔ QualityAttribute (tradeoff)
- `isaqb:supportedBy` — QualityAttribute ↔ QualityAttribute (synergy)
- `isaqb:hasSubAttribute` — QualityAttribute → QualityAttribute (ISO 25010 hierarchy)
- `isaqb:refines` — QualityScenario → QualityAttribute
- `isaqb:mitigates` — Decision/Pattern → Risk
- `isaqb:introduces` — Decision → TechnicalDebt
- `isaqb:governedBy` — CrossCuttingConcern → ArchitectureDecision
- `isaqb:documentedIn` — Concept → Arc42Section
- `isaqb:hasOption` / `isaqb:chosenOption` — Decision → DecisionOption

### Cross-Ontology Links (isaqb ↔ prd ↔ code)
- `isaqb:addressesQuality` — prd:Requirement → isaqb:QualityAttribute
- `isaqb:justifiedBy` — prd:Requirement → isaqb:ArchitectureDecision
- `isaqb:realizesPattern` — code:Module/Class/Function → isaqb:ArchitecturalPattern/DesignPattern
- `isaqb:appliesPrinciple` — code:Module/Class or prd:Requirement → isaqb:DesignPrinciple
- `isaqb:verifiedByScenario` — prd:Requirement → isaqb:QualityScenario

### SHACL Validation (Two-Tier Severity)
- **ADRShapeStrict**: Tier 1 (Violation) — title, context, rationale, consequences, status; Tier 2 (Warning) — >=2 options, quality linkage
- **QualityScenarioShapeStrict**: Tier 1 — stimulus, response, responseMeasure; Tier 2 — refines quality attribute, environment
- **RiskShapeStrict**: Tier 1 — label, severity; Tier 2 — mitigation, likelihood
- **QualityGoalShapeStrict**: Tier 1 — must refine a quality attribute

## Quality Attribute Top-Level (ISO 25010:2023)

| Attribute | Key Sub-Attributes | Common Conflicts |
|-----------|-------------------|------------------|
| FunctionalSuitability | Completeness, Correctness, Appropriateness | — |
| PerformanceEfficiency | TimeBehaviour, ResourceUtilization, Capacity | Maintainability, Security, Reliability, Flexibility |
| Compatibility | CoExistence, Interoperability | Security |
| InteractionCapability | Learnability, Operability, UserErrorProtection, Accessibility | — |
| Reliability | Availability, FaultTolerance, Recoverability, Maturity | PerformanceEfficiency |
| Security | Confidentiality, Integrity, NonRepudiation, Accountability, Authenticity | InteractionCapability, PerformanceEfficiency, Flexibility |
| Maintainability | Modularity, Reusability, Analysability, Modifiability, Testability | PerformanceEfficiency |
| Flexibility | Adaptability, Installability, Replaceability | — |

## Usage in Architecture Design (P3)

When designing architecture, use the iSAQB schema to:

1. **Select quality goals**: Pick top-3-to-5 `isaqb:QualityAttribute` values as `isaqb:QualityGoal` instances.
2. **Identify tradeoffs**: Query `isaqb:conflictsWith` to find tensions between chosen quality goals.
3. **Choose patterns**: Select `isaqb:ArchitecturalPattern` and `isaqb:DesignPattern` instances that `isaqb:addresses` the desired quality attributes.
4. **Document decisions**: Create `isaqb:ArchitectureDecision` instances with context, options, rationale, and consequences. SHACL shapes enforce completeness.
5. **Write quality scenarios**: Create `isaqb:QualityScenario` instances with stimulus/environment/response/measure to make quality goals testable.
6. **Map cross-cutting concerns**: Identify which `isaqb:CrossCuttingConcern` instances are relevant and link them to decisions via `isaqb:governedBy`.
7. **Link to requirements**: Use `isaqb:addressesQuality` and `isaqb:justifiedBy` to connect `prd:Requirement` instances to quality attributes and decisions.
8. **Assess risks**: Create `isaqb:Risk` instances and link mitigating decisions via `isaqb:mitigates`.

## Example SPARQL Queries

```sparql
# Find patterns that address Maintainability
SELECT ?pattern ?label WHERE {
  ?pattern isaqb:addresses isaqb:Maintainability .
  ?pattern rdfs:label ?label .
}

# Find quality attribute tradeoffs
SELECT ?qa1 ?label1 ?qa2 ?label2 WHERE {
  ?qa1 isaqb:conflictsWith ?qa2 .
  ?qa1 rdfs:label ?label1 .
  ?qa2 rdfs:label ?label2 .
}

# Find principles embodied by a pattern
SELECT ?principle ?label WHERE {
  isaqb:PortsAndAdapters isaqb:embodies ?principle .
  ?principle rdfs:label ?label .
}
```
