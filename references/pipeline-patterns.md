# Pipeline Patterns

Documentation generation should be deterministic and reviewable.

## Recommended Modes

### Generate

Use locally or in scheduled automation:

```bash
code-docs generate
```

Expected behavior:
- inspect the repo
- update generated Markdown/Mermaid/JSON artifacts
- preserve human-authored sections
- produce stable output ordering

### Check

Use in pull requests:

```bash
code-docs check
```

Expected behavior:
- regenerate docs into a temp directory or worktree
- compare against committed docs
- fail when docs drift from code
- print a concise diff summary and the command to refresh

### Review

Use when teams are not ready to fail CI:

```bash
code-docs review
```

Expected behavior:
- produce a report artifact
- comment on missing or stale docs if the pipeline supports comments
- avoid blocking merges

## GitHub Actions Example

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
      - name: Generate code inventory
        run: python3 .codex/skills/code-doc-pipeline/scripts/inventory_repo.py . --out docs/generated/code-doc-inventory.json
      - name: Check docs drift
        run: git diff --exit-code docs
```

Adjust the script path to wherever the skill is installed in the project or CI image.

## Drift Policy

Fail CI for:
- changed APIs without updated interface docs
- changed deploy/config files without updated operations docs
- changed major dependencies or entrypoints without updated architecture docs
- invalid Mermaid syntax when validation is available

Do not fail CI for:
- missing aspirational docs that the team has not agreed to maintain
- formatting churn outside generated sections
- docs that require product decisions not visible in code

## Determinism Checklist

- Sort files, routes, modules, and dependencies alphabetically.
- Omit timestamps by default.
- Use relative paths from repo root.
- Normalize path separators.
- Keep generated JSON pretty-printed with sorted keys.
- Isolate generated sections with markers.
