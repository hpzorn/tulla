# Tulla

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![CI](https://github.com/hpzorn/tulla/actions/workflows/ci.yml/badge.svg)](https://github.com/hpzorn/tulla/actions/workflows/ci.yml)

## *Disclaimer* 

**Tulla is *experimental* software built for research purposes. It is not meant for production use. It still has major security issues (such as prompt injection during research) that are typical for LLM based agents. It should only be used in sandbox environments without access to sensitive data/information. It is completely AI generated - mostly coded by itself. I only prompt, I did not review every line of code - which is an experiment and not recommended policy, especially it is not policy at my employer. This is a private project**


Tulla is an autonomous agent that takes a raw idea and drives it through a structured pipeline — discovery, research, planning, and implementation — producing code at the end. Each phase is backed by an ontology and validated with SHACL, so the agent can't skip steps or produce incomplete work. It extends Geoffrey Huntley's [Ralph Wiggum loop](https://ghuntley.com/ralph/) with mandatory research, idea decomposition, and PRD-driven implementation.

Tulla has been built to verify the following Research Questions
* If guided properly, how long can a code agent go along without experiencing context drift?
* Does guidance by Architecture Principles improve overall quality?
* Does mapping to semantic concepts help to keep track of architecure decisions? (-> agentic memory)
* Can the Zero Trust Reasoning Framework be implemented for such a coding harness? 


## The Loop

```
backlog → researching → researched → scoped → implementing → completed
              │              │                      │
              ▼              ▼                      ▼
         invalidated    decomposing            blocked/failed
            parked      (→ children)
```

| State | Meaning |
|-------|---------|
| `backlog` | Queued for processing |
| `researching` | Research phase active (R1–R6) |
| `researched` | Research done, ready for scoping |
| `invalidated` | Dead end, won't implement |
| `parked` | Needs human decision |
| `decomposing` | Breaking into sub-ideas |
| `scoped` | PRD created |
| `implementing` | Code being written |
| `blocked` | Stuck on dependency |
| `completed` | Done |

## Installation

```bash
git clone https://github.com/hpz/tulla.git
cd tulla
uv sync --all-extras
uv run python -m pytest tests/ -x -q
```

## Requirements

- Python 3.11+
- [ontology-server](https://github.com/hpz/semantic-tool-use) MCP server for ontology operations
- `claude` CLI ([Claude Code](https://github.com/anthropics/claude-code)) for the autonomous loop

## Project Structure

```
src/tulla/
├── core/           # Pipeline, phase facts, configuration
├── phases/         # Discovery (D1-D5), Research (R1-R6), Planning, Implementation, Epistemology
├── ontology/       # Phase ontology (SHACL shapes, namespace definitions)
├── ports/          # Ontology and MCP integration
└── cli.py          # CLI entry point

ontologies/         # Shared ontology files (symlinked into ontology-server)
tests/              # pytest test suite
```

## References

- [ghuntley.com/ralph](https://ghuntley.com/ralph/) — Original technique
- [anthropics/claude-code](https://github.com/anthropics/claude-code) — Claude Code CLI
- [snarktank/ralph](https://github.com/snarktank/ralph) — PRD-driven autonomous agent

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-change`)
3. Run the test suite (`uv run python -m pytest tests/ -x -q`)
4. Run linting (`ruff check src/` and `mypy src/`)
5. Open a pull request

## Acknowledgements

The `isaqb-ontology.ttl` ontology encodes terminology and concepts from the [iSAQB Glossary of Software Architecture Terminology](https://github.com/isaqb-org/glossary), originally created by **Gernot Starke** and **Dr. Peter Hruschka** and maintained by the [International Software Architecture Qualification Board (iSAQB)](https://www.isaqb.org/). The glossary is licensed under the [Creative Commons Attribution-ShareAlike 4.0 International License (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/). We gratefully acknowledge their work and that of the wider iSAQB contributor community for making this resource freely available.

## License

[Apache 2.0](LICENSE)
