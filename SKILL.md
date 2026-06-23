---
name: code-doc-pipeline
description: Generate maintainable documentation from codebases, including architecture docs, module/API docs, Mermaid/C4-style diagrams, ADR suggestions, and CI/CD documentation drift checks. Use when asked to document code, create docs from source, add docs generation to a pipeline, produce architecture diagrams from repositories, or keep engineering documentation current automatically.
---

# Code Doc Pipeline

Use this skill to turn a repository into useful, reviewable documentation that can run in CI/CD. Optimize for docs that help engineers operate and change the system, not broad generated noise.

Diagrams are a default output, not a bonus. For any non-trivial codebase, produce Mermaid diagrams as naturally as prose: context/flow diagrams for structure, sequence diagrams for runtime behavior, data-flow diagrams for ownership and movement, and deployment diagrams when infrastructure is visible.

## Workflow

1. Establish the documentation contract.
   - Identify audience: new engineer onboarding, service owners, platform operators, API consumers, auditors, or architects.
   - Identify output location: usually `docs/`, `architecture/`, `handbook/`, or existing repo conventions.
   - Identify pipeline mode:
     - `generate`: create or refresh docs.
     - `check`: fail when generated docs differ from committed docs.
     - `review`: produce a report without writing files.

2. Inventory the repository before writing.
   - Prefer existing manifest files and source structure over guesses.
   - Run `scripts/inventory_repo.py <repo> --out <repo>/docs/code-doc-inventory.json` when no better local inventory tool exists.
   - Read build files, route/API declarations, package manifests, schema/migration folders, IaC, deployment files, and existing docs.
   - Exclude generated/vendor directories such as `node_modules`, `dist`, `build`, `.git`, `.next`, `target`, `vendor`, and lockfile-only noise.

3. Infer system boundaries.
   - Identify entrypoints, deployable units, modules/packages, external dependencies, persistence, message flows, scheduled jobs, and operational surfaces.
   - Mark confidence explicitly when the code does not prove a claim.
   - Do not invent runtime behavior that is not visible in code, config, tests, or existing docs.

4. Generate docs in stable layers.
   - Repository overview: purpose, stack, how to run/test/build, key directories.
   - Architecture: containers/components, data flow, runtime dependencies, trust boundaries, and diagrams.
   - API/interface docs: routes, commands, events, schemas, examples, auth expectations.
   - Operational docs: config, env vars, jobs, deployment, observability, failure/recovery notes.
   - Decision docs: ADR candidates only when the code reveals meaningful architectural decisions.

5. Generate diagrams as text-first artifacts by default.
   - Prefer Mermaid diagrams committed as Markdown code blocks or `.mmd` files.
   - Create at least one structure diagram and one behavior diagram unless the repo is trivial.
   - Use C4-like levels: context, container, component, sequence, data flow, deployment.
   - Default diagram set for a service or app:
     - `context.mmd`: users, system, external dependencies.
     - `container-or-flow.mmd`: main runtime parts and their connections.
     - `critical-sequence.mmd`: one important request, job, event, or workflow.
     - `data-flow.mmd`: data ownership and movement when persistence or integrations exist.
   - Keep diagrams small enough to review in a PR.
   - Split diagrams when more than 8-10 nodes or when one diagram mixes unrelated concerns.
   - See `references/diagram-patterns.md` for diagram selection and Mermaid patterns.

6. Make the pipeline safe.
   - In `generate` mode, write deterministic files and avoid timestamps unless needed.
   - In `check` mode, regenerate into a temp directory and diff against committed docs.
   - Fail only on meaningful docs drift, broken diagrams, missing required doc sections, or stale generated inventory.
   - Do not fail because of unrelated formatting churn.
   - Keep human-authored sections clearly separated from generated sections.

7. Review for usefulness.
   - Remove obvious restatements of filenames.
   - Prefer short explanations tied to concrete code paths.
   - Link to source files, schemas, routes, config, migrations, and deployment files.
   - Include open questions when the code is ambiguous.
   - Keep secrets, internal tokens, credentials, and private customer data out of generated docs.

## Output Shape

Default to:

```text
docs/
  README.md
  architecture.md
  operations.md
  interfaces.md
  diagrams/
    context.mmd
    container-or-flow.mmd
    critical-sequence.mmd
    data-flow.mmd
    deployment.mmd
  generated/
    code-doc-inventory.json
```

Adapt to the repo's existing conventions. Do not create parallel doc systems when one already exists.

## Pipeline Pattern

Use a two-command pattern:

```bash
# Regenerate docs locally or in a scheduled job
code-docs generate

# CI check mode
code-docs check
```

If no dedicated CLI exists yet, implement the pipeline as a script wrapper around:

```bash
python3 scripts/inventory_repo.py . --out docs/generated/code-doc-inventory.json
```

Then have the agent or repo-specific doc generator update Markdown and Mermaid artifacts from the inventory.

## Quality Bar

Generated documentation must:

- explain what the system does and where to start reading
- expose important dependencies and boundaries
- show useful Mermaid diagrams for both structure and behavior in non-trivial systems
- document how to build, test, deploy, configure, and observe the system when the repo contains that information
- separate facts proven by code from assumptions
- be stable enough that repeated runs do not create meaningless diffs

Reject documentation that:

- dumps directory trees without explaining ownership or behavior
- rewrites every function into prose
- hides uncertainty
- skips diagrams for systems where a visual map would clarify structure or behavior
- creates one massive diagram that nobody can read
- leaks secrets or environment-specific private values
- makes CI brittle with timestamps, random ordering, or formatting churn

## References

- Read `references/doc-structure.md` when deciding which docs to create and how to organize generated versus human-authored sections.
- Read `references/diagram-patterns.md` when choosing Mermaid/C4-style diagrams.
- Read `references/pipeline-patterns.md` when adding CI/CD generation and drift checks.
