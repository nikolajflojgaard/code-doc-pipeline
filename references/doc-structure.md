# Documentation Structure

Use the smallest documentation set that gives engineers a reliable map of the system.

## Default Files

### `docs/README.md`

Purpose:
- orient a new engineer
- explain what the repository owns
- point to deeper docs

Include:
- system purpose
- primary runtime/deployable units
- stack and package managers
- build/test commands
- key directories
- links to architecture, operations, and interfaces docs

### `docs/architecture.md`

Purpose:
- describe the system shape and boundaries
- show how major parts interact

Include:
- context diagram
- container/component diagram
- dependency table
- data ownership
- trust boundaries
- known architectural constraints
- open questions or inferred assumptions

### `docs/interfaces.md`

Purpose:
- document how other systems or users interact with this codebase

Include when present:
- HTTP routes and auth
- GraphQL operations
- CLI commands
- scheduled jobs
- events/messages
- database schemas exposed to consumers
- file formats
- examples linked to tests or fixtures

### `docs/operations.md`

Purpose:
- help someone run and recover the system

Include when visible in code/config:
- environment variables, grouped by required/optional
- deploy targets
- startup commands
- health checks
- logs/metrics/traces
- backups and migrations
- incident/recovery notes
- common failure modes

### `docs/adr/`

Create ADRs only for real decisions visible in the repo or explicitly requested.

Good ADR candidates:
- framework/runtime choice
- database/persistence choice
- integration pattern
- auth/security model
- deployment topology
- major migration/refactor direction

Avoid fake ADRs that only restate current code.

## Generated Section Markers

When mixing generated and human-authored text, use explicit markers:

```markdown
<!-- code-doc-pipeline:start -->
Generated content.
<!-- code-doc-pipeline:end -->
```

Only replace content inside markers. Leave surrounding human notes intact.

## Confidence Language

Use:
- `Observed:` for facts directly visible in code/config/tests.
- `Inferred:` for likely behavior derived from multiple signals.
- `Unknown:` for gaps that need a human answer.

Do not convert guesses into facts.
