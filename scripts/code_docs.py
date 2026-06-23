#!/usr/bin/env python3
"""Generate and check codebase documentation artifacts."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from inventory_repo import collect_inventory


START = "<!-- code-doc-pipeline:start -->"
END = "<!-- code-doc-pipeline:end -->"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("generate", "check", "review"):
        cmd = sub.add_parser(name)
        cmd.add_argument("repo", nargs="?", default=".", help="Repository root")
        cmd.add_argument("--docs-dir", default="docs", help="Docs output directory")
        cmd.add_argument("--max-files", type=int, default=5000)
        cmd.add_argument("--exclude", action="append", default=[])

    return parser.parse_args()


def bullet_paths(items: list[dict[str, object]], *, limit: int = 20) -> str:
    if not items:
        return "- None detected\n"
    lines = [f"- `{item['path']}`" for item in items[:limit]]
    if len(items) > limit:
        lines.append(f"- ...and {len(items) - limit} more")
    return "\n".join(lines) + "\n"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def generated_block(body: str) -> str:
    return f"{START}\n{body.rstrip()}\n{END}\n"


def replace_generated_section(existing: str, body: str) -> str:
    block = generated_block(body)
    if START in existing and END in existing:
        before = existing.split(START, 1)[0]
        after = existing.split(END, 1)[1]
        return before.rstrip() + "\n\n" + block + after.lstrip()
    if existing.strip():
        return existing.rstrip() + "\n\n" + block
    return block


def upsert_doc(path: Path, title: str, body: str) -> None:
    existing = path.read_text() if path.exists() else f"# {title}\n"
    write_text(path, replace_generated_section(existing, body))


def mermaid_context(inventory: dict[str, object]) -> str:
    repo = inventory["repo"]
    has_interfaces = inventory["counts"]["interfaces"] > 0
    has_deploy = inventory["counts"]["deployments"] > 0
    lines = [
        "flowchart LR",
        "  Developer[Developer or operator]",
        f"  System[{repo}]",
    ]
    if has_interfaces:
        lines += ["  Consumer[API or UI consumer]", "  Consumer -->|uses| System"]
    if has_deploy:
        lines += ["  Runtime[Runtime or hosting platform]", "  System -->|deploys to| Runtime"]
    lines += ["  Developer -->|changes and operates| System"]
    return "\n".join(lines) + "\n"


def mermaid_flow(inventory: dict[str, object]) -> str:
    lines = ["flowchart TB", f"  Repo[{inventory['repo']} repository]"]
    if inventory["manifests"]:
        lines += ["  Manifests[Build and dependency manifests]", "  Repo -->|defines| Manifests"]
    if inventory["interfaces"]:
        lines += ["  Interfaces[Interfaces and routes]", "  Repo -->|exposes| Interfaces"]
    if inventory["deployments"]:
        lines += ["  Deploy[Deployment automation]", "  Repo -->|ships with| Deploy"]
    lines += ["  Docs[Generated documentation]", "  Repo -->|documents| Docs"]
    return "\n".join(lines) + "\n"


def mermaid_sequence(inventory: dict[str, object]) -> str:
    if inventory["interfaces"]:
        return """sequenceDiagram
  participant Consumer
  participant Interface
  participant Application
  participant Dependency

  Consumer->>Interface: Request or command
  Interface->>Application: Validate and dispatch
  Application->>Dependency: Read/write/call
  Dependency-->>Application: Result
  Application-->>Consumer: Response or side effect
"""
    if inventory["deployments"]:
        return """sequenceDiagram
  participant Developer
  participant CI
  participant Artifact
  participant Runtime

  Developer->>CI: Push change
  CI->>CI: Build and test
  CI->>Artifact: Publish artifact
  Artifact->>Runtime: Deploy
"""
    return """sequenceDiagram
  participant Developer
  participant Repository
  participant Documentation

  Developer->>Repository: Change code
  Repository->>Documentation: Regenerate docs
  Documentation-->>Developer: Review diff
"""


def mermaid_data_flow(inventory: dict[str, object]) -> str:
    data_files = [item for item in inventory["files"] if "data" in item["tags"]]
    if data_files:
        source = "Data source"
        store = "Owned schema or model"
    else:
        source = "Code and config"
        store = "Generated inventory"
    return f"""flowchart LR
  Source[{source}]
  Processor[Documentation pipeline]
  Store[({store})]
  Docs[Markdown and Mermaid docs]

  Source -->|reads| Processor
  Processor -->|writes| Store
  Processor -->|updates| Docs
"""


def mermaid_deployment(inventory: dict[str, object]) -> str:
    return """flowchart TB
  Change[Code change]
  CI[CI pipeline]
  Docs[Generated docs]
  Review[Pull request review]

  Change -->|triggers| CI
  CI -->|generates/checks| Docs
  Docs -->|diff reviewed in| Review
"""


def write_diagrams(docs_dir: Path, inventory: dict[str, object]) -> None:
    diagrams_dir = docs_dir / "diagrams"
    diagrams = {
        "context.mmd": mermaid_context(inventory),
        "container-or-flow.mmd": mermaid_flow(inventory),
        "critical-sequence.mmd": mermaid_sequence(inventory),
        "data-flow.mmd": mermaid_data_flow(inventory),
        "deployment.mmd": mermaid_deployment(inventory),
    }
    for name, content in diagrams.items():
        write_text(diagrams_dir / name, content)


def generate(repo: Path, docs_dir: Path, max_files: int, exclude: list[str]) -> dict[str, object]:
    effective_exclude = list(exclude)
    try:
        docs_rel = docs_dir.relative_to(repo)
        if len(docs_rel.parts) == 1:
            effective_exclude.append(docs_rel.parts[0])
    except ValueError:
        pass

    inventory = collect_inventory(repo, max_files=max_files, exclude=effective_exclude)
    generated_dir = docs_dir / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)
    write_text(generated_dir / "code-doc-inventory.json", json.dumps(inventory, indent=2, sort_keys=True))
    write_diagrams(docs_dir, inventory)

    overview = f"""
## Repository Snapshot

- Repository: `{inventory['repo']}`
- Files inventoried: `{inventory['counts']['files']}`
- Manifests: `{inventory['counts']['manifests']}`
- Interfaces/routes hints: `{inventory['counts']['interfaces']}`
- Deployment hints: `{inventory['counts']['deployments']}`
- Inventory truncated: `{inventory['truncated']}`

## Key Manifests

{bullet_paths(inventory['manifests'])}

## Where To Look First

- Architecture: [`architecture.md`](architecture.md)
- Interfaces: [`interfaces.md`](interfaces.md)
- Operations: [`operations.md`](operations.md)
- Diagrams: [`diagrams/`](diagrams/)
"""
    upsert_doc(docs_dir / "README.md", "Repository Documentation", overview)

    architecture = f"""
## Observed Structure

### Manifests

{bullet_paths(inventory['manifests'])}

### Entrypoints

{bullet_paths(inventory['entrypoints'])}

### Deployment Hints

{bullet_paths(inventory['deployments'])}

## Diagrams

- [Context](diagrams/context.mmd)
- [Container or flow](diagrams/container-or-flow.mmd)
- [Critical sequence](diagrams/critical-sequence.mmd)
- [Data flow](diagrams/data-flow.mmd)
- [Deployment](diagrams/deployment.mmd)

## Unknowns

- Confirm runtime boundaries with a service owner.
- Confirm whether detected interface hints are public APIs, internal routes, or framework conventions.
"""
    upsert_doc(docs_dir / "architecture.md", "Architecture", architecture)

    interfaces = f"""
## Detected Interface Hints

{bullet_paths(inventory['interfaces'], limit=50)}

## Notes

- Treat this list as a discovery aid, not a complete API contract.
- Confirm auth, schemas, request/response examples, and external consumers from code and tests.
"""
    upsert_doc(docs_dir / "interfaces.md", "Interfaces", interfaces)

    operations = f"""
## Deployment and Operations Hints

{bullet_paths(inventory['deployments'], limit=50)}

## Operational Follow-Up

- Document required environment variables.
- Document build, test, deploy, rollback, and health-check commands.
- Link logs, metrics, traces, dashboards, and alert ownership when known.
"""
    upsert_doc(docs_dir / "operations.md", "Operations", operations)

    return inventory


def git_diff_has_changes(repo: Path, docs_dir: Path) -> bool:
    status = subprocess.run(
        ["git", "status", "--porcelain", "--", str(docs_dir.relative_to(repo))],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    if status.stdout.strip():
        return True

    result = subprocess.run(
        ["git", "diff", "--quiet", "--", str(docs_dir.relative_to(repo))],
        cwd=repo,
        text=True,
    )
    return result.returncode != 0


def command_generate(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    docs_dir = (repo / args.docs_dir).resolve()
    generate(repo, docs_dir, args.max_files, args.exclude)
    print(f"Generated docs in {docs_dir}")
    return 0


def command_check(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    docs_dir = (repo / args.docs_dir).resolve()
    generate(repo, docs_dir, args.max_files, args.exclude)
    if (repo / ".git").exists() and git_diff_has_changes(repo, docs_dir):
        print("Documentation drift detected. Run `code_docs.py generate` and commit the docs changes.", file=sys.stderr)
        return 1
    print("Documentation is up to date.")
    return 0


def command_review(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    inventory = collect_inventory(repo, max_files=args.max_files, exclude=args.exclude)
    print(json.dumps({"counts": inventory["counts"], "truncated": inventory["truncated"]}, indent=2, sort_keys=True))
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "generate":
        return command_generate(args)
    if args.command == "check":
        return command_check(args)
    if args.command == "review":
        return command_review(args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
