# @pattern:LayeredArchitecture -- lightweight package sits in the phases layer alongside discovery/planning/research
# @pattern:Microservices -- lightweight agent is a self-contained vertical slice with own models, phases, and pipeline factory
# @pattern:SOA -- lightweight exposes a pipeline service boundary; CLI and other agents consume it through the factory function
# @pattern:CQRS -- non-Claude phases (Intake/ContextScan/Trace) read-only; Claude phases (Plan/Execute) perform write mutations
# @principle:SeparationOfConcerns -- isolates non-Claude phases (Intake/ContextScan/Trace) from Claude-dependent phases
# @principle:OpenClosedPrinciple -- new lightweight phases added as modules here without modifying Phase/Pipeline framework
# @principle:LooseCoupling -- lightweight phases depend only on Phase[T] ABC, no direct coupling to Claude subprocess
# @principle:InformationHiding -- package boundary encapsulates local-compute phase implementations from rest of codebase
