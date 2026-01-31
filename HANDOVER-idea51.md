# Handover: Idea 51 — Add Security to the Ontology Server

## Current State

Auth is **live on production**. Server requires Bearer token on all endpoints except `/health`.

### What's done

- `research-ralph.sh` has new `--start-from R#` and `--work-dir DIR` flags
- `planning-ralph.sh` now loads downstream research findings (R4-R6) into P1 when they answer discovery RQs
- Ontology server has Bearer auth middleware (`__main__.py` gated by `ONTOLOGY_AUTH_ENABLED=1`)
- `~/.claude.json` patched with Authorization header (via `setup_auth.py`)
- `~/.ontology-server-key` exists with API key (chmod 600)
- `~/.zshrc` has `export ONTOLOGY_API_KEY`
- launchd plist has `ONTOLOGY_AUTH_ENABLED=1`

### PRD-51 requirement status (in ontology A-box, context `prd-51`)

| Req | Status | Task |
|-----|--------|------|
| req-51-1-1 | Complete | Add Bearer Auth Middleware |
| req-51-1-2 | Complete | Verify MCP SSE Auth Coverage |
| req-51-2-1 | Complete | Run setup_auth.py --apply |
| req-51-2-2 | **Pending** | Restart Ontology Server (was done but status not updated before kill) |
| req-51-3-1 | Pending | Adapt and Run Verification Script |
| req-51-3-2 | Pending | Manual Ralph Pipeline Test |
| req-51-4-1 | Pending | Verify Audit Log Output |

### To continue implementation

```bash
./implementation-ralph.sh --prd prd-51 --no-clean
```

Use `--no-clean` to preserve existing Complete statuses and resume from where it left off.

### Viewer

Start with auth token forwarding (viewer does NOT yet support auth headers — it will fail against the authenticated server):

```bash
ONTOLOGY_SERVER_URL=http://127.0.0.1:8100 ./work/impl-prd-39-20260130-173852/run.sh
```

The viewer needs to be patched to pass `Authorization: Bearer` headers. This was a gap in the planning — see analysis below.

### Key files modified this session

- `research-ralph.sh` — added `--start-from`, `--work-dir`, `should_skip_phase()`
- `planning-ralph.sh` — added `find_research_dir()`, wired research findings into P1
- `/Users/sandboxuser/semantic-tool-use/src/ontology_server/__main__.py` — auth gated by `ONTOLOGY_AUTH_ENABLED=1`
- `/Users/sandboxuser/Library/LaunchAgents/org.semantic-tool-use.ontology-server.plist` — added env var

### Planning gap analysis

Planning produced requirements that enabled auth on the production server without ensuring all clients could authenticate first. The deployment ordering was:
1. Add middleware (server-side)
2. Configure credentials (client-side)
3. Restart server ← breaks all existing connections

Missing from the plan:
- Viewer auth header support
- Coordinated cutover (test against staging, not production)
- Graceful degradation / feature flag for rollback

The `ONTOLOGY_AUTH_ENABLED=1` env var was added as a post-hoc fix to make auth opt-in rather than auto-enabled by `get_or_create_api_key()`.

### Work directories

- Discovery: `work/discovery-51-20260131-152153/`
- Research (seeded R1-R3, ran R4-R6): `work/idea-51-research/`
- Planning: `work/planning-51-20260131-162333/`
- Implementation: `work/impl-prd-51-20260131-170250/`
