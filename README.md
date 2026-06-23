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
  .github/
    workflows/
      validate.yml
  SKILL.md
  agents/
    openai.yaml
  references/
    diagram-patterns.md
    doc-structure.md
    pipeline-patterns.md
  scripts/
    code_docs.py
    inventory_repo.py
  examples/
    tiny-api/
  tests/
    test_code_docs.py
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
python3 ~/.codex/skills/code-doc-pipeline/scripts/code_docs.py generate .
```

This creates:

```text
docs/
  README.md
  architecture.md
  interfaces.md
  operations.md
  diagrams/
    context.mmd
    container-or-flow.mmd
    critical-sequence.mmd
    data-flow.mmd
    deployment.mmd
  generated/
    code-doc-inventory.json
```

Then ask the agent to review and improve the generated baseline:

```text
Use $code-doc-pipeline to create docs/README.md, docs/architecture.md, docs/interfaces.md, docs/operations.md, and Mermaid context, flow, sequence, and data-flow diagrams for this repo. Preserve existing human-written docs where possible.
```

## CLI

```bash
# Generate or refresh docs and diagrams
python3 scripts/code_docs.py generate .

# CI mode: regenerate and fail if docs changed
python3 scripts/code_docs.py check .

# Non-writing summary mode
python3 scripts/code_docs.py review .

# Lightweight Mermaid validation
python3 scripts/code_docs.py validate-diagrams .

# Inventory only
python3 scripts/inventory_repo.py . --out docs/generated/code-doc-inventory.json
```

## Configuration

Add `code-docs.yml` at the repository root:

```yaml
docs_dir: docs
max_files: 5000
exclude:
  - node_modules
  - dist
  - generated
```

The parser intentionally supports a small YAML subset so the tool stays dependency-free.

## CI Example

The workflow can be strict with `check`, advisory with `review`, or both. For pull requests in the same repository, the example below keeps one sticky docs review comment updated instead of adding a new comment every run.

```yaml
name: Code documentation

on:
  pull_request:
  workflow_dispatch:

permissions:
  contents: read
  pull-requests: write

jobs:
  docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Check documentation drift
        run: python3 .codex/skills/code-doc-pipeline/scripts/code_docs.py check .
      - name: Add docs review summary
        if: always()
        run: python3 .codex/skills/code-doc-pipeline/scripts/code_docs.py review . --github-summary --report /tmp/code-doc-review.md
      - name: Update PR documentation comment
        if: github.event_name == 'pull_request' && github.event.pull_request.head.repo.full_name == github.repository
        env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
        run: |
          marker='<!-- code-doc-pipeline:review -->'
          body_file=/tmp/code-doc-review-with-marker.md
          printf '%s\n\n' "$marker" > "$body_file"
          cat /tmp/code-doc-review.md >> "$body_file"

          comment_id="$(
            gh api "repos/$REPO/issues/$PR_NUMBER/comments" \
              --jq ".[] | select(.user.login == \"github-actions[bot]\" and (.body | contains(\"$marker\"))) | .id" \
              | head -n 1
          )"

          if [ -n "$comment_id" ]; then
            body="$(cat "$body_file")"
            gh api "repos/$REPO/issues/comments/$comment_id" --method PATCH --field body="$body"
          else
            gh pr comment "$PR_NUMBER" --repo "$REPO" --body-file "$body_file"
          fi
```

In a mature setup, wrap this in your own `code-docs generate` and `code-docs check` commands so teams do not need to remember skill paths.

## Example

See [`examples/tiny-api`](examples/tiny-api) for a small Express-style API and generated documentation output.

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

Production baseline: includes a runnable CLI, deterministic generation/check behavior, stdlib tests, and GitHub Actions validation. Still designed to be adapted per repo rather than pretending one documentation generator can understand every architecture perfectly.

## License

MIT
