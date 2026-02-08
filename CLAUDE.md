# Claude Code Guidelines for ideasralph

## Implementation Language

**Default language for NEW code is Python 3.11+**:
- New experiments (R5 phase)
- New prototypes and modules
- New scripts and tools

This ensures consistency with existing infrastructure (ontology-server, MCP tools, etc.).

**When modifying existing files, use the file's own language.** If a requirement says to modify a `.sh` file, write bash. If it says to modify a `.md` file, write markdown. If it says to modify a `.typ` file, write Typst. Never rewrite an existing file in a different language — modify it in place using its native syntax.

## Key Infrastructure

- **ontology-server MCP**: Use for all ontology operations (SPARQL, A-box, facts)
- **idea-pool MCP**: Use for idea management
- **Python 3.11+**: Target runtime

## File Locations

- Ideas: `~/.claude/ideas/`
- Tulla source: `src/tulla/`
- Tulla tests: `tests/`
- Ontologies (canonical): `ontologies/` (symlinked into ontology-server)
- Work directories: `./work/idea-{N}-{timestamp}/`
