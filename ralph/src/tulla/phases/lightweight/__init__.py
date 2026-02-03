# @pattern:LayeredArchitecture -- lightweight package sits in the phases layer alongside discovery/planning/research
# @principle:SeparationOfConcerns -- isolates non-Claude phases (Intake/ContextScan/Trace) from Claude-dependent phases
# @principle:OpenClosedPrinciple -- new lightweight phases added as modules here without modifying Phase/Pipeline framework
# @principle:LooseCoupling -- lightweight phases depend only on Phase[T] ABC, no direct coupling to Claude subprocess
# @principle:InformationHiding -- package boundary encapsulates local-compute phase implementations from rest of codebase
