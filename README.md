# Code Doc Pipeline

An AgentSkill for generating useful documentation from codebases, including architecture docs, API/interface docs, operational notes, Mermaid diagrams, and CI/CD documentation drift checks.

The point is not to dump a repo tree into Markdown. The point is to keep documentation close enough to the code that it can be regenerated, reviewed, and trusted.

## What It Helps With

- Generate architecture documentation from source code and config
- Produce Mermaid/C4-style diagrams as a default output, not an afterthought
- Create sequence, flow, data-flow, context, component, and deployment diagrams where the code supports them
- Document APIs, events, jobs, modules, deployment surfaces, and config
- Separate observed facts from inferred behavior
- Add pipeline checks so documentation drift is visible in pull requests
- Preserve human-written context while refreshing generated sections

## Repository Layout

```text
code-doc-pipeline/
  SKILL.md
  agents/
    openai.yaml
  references/
    diagram-patterns.md
    doc-structure.md
    pipeline-patterns.md
  scripts/
    inventory_repo.py
```

## Install

Copy this folder into your Codex/OpenClaw skills directory, for example:

```bash
mkdir -p ~/.codex/skills
git clone https://github.com/nikolajflojgaard/code-doc-pipeline.git ~/.codex/skills/code-doc-pipeline
```

Then invoke it explicitly:

```text
Use $code-doc-pipeline to generate pipeline-ready architecture documentation for this repository.
```

## Quick Start

From a repository you want to document:

```bash
python3 ~/.codex/skills/code-doc-pipeline/scripts/inventory_repo.py . --out docs/generated/code-doc-inventory.json
```

Then ask the agent to use the skill to turn the inventory plus source code into docs:

```text
Use $code-doc-pipeline to create docs/README.md, docs/architecture.md, docs/interfaces.md, docs/operations.md, and Mermaid context, flow, sequence, and data-flow diagrams for this repo. Preserve existing human-written docs where possible.
```

## CI Example

```yaml
name: Code documentation

on:
  pull_request:
  workflow_dispatch:

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Generate inventory
        run: python3 .codex/skills/code-doc-pipeline/scripts/inventory_repo.py . --out docs/generated/code-doc-inventory.json
      - name: Check docs drift
        run: git diff --exit-code docs
```

In a mature setup, wrap this in your own `code-docs generate` and `code-docs check` commands so teams do not need to remember skill paths.

## Documentation Philosophy

Good generated documentation should:

- explain system ownership and boundaries
- link back to code, config, tests, schemas, and deployment files
- include Mermaid diagrams that are small enough to review in pull requests
- show both structure and behavior when the codebase is non-trivial
- mark uncertainty instead of inventing facts
- keep generated sections deterministic
- avoid leaking secrets or private environment values

Bad generated documentation:

- rewrites every function into prose
- creates unreadable mega-diagrams
- produces noisy diffs on every run
- hides assumptions
- becomes a second stale source of truth

## Status

Initial public version. Built to be adapted per repo rather than pretending one documentation generator can understand every architecture perfectly.

## License

MIT
