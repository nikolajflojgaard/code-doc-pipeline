#!/usr/bin/env python3
"""Generate and check codebase documentation artifacts."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from inventory_repo import collect_inventory


START = "<!-- code-doc-pipeline:start -->"
END = "<!-- code-doc-pipeline:end -->"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("generate", "check", "review", "validate-diagrams"):
        cmd = sub.add_parser(name)
        cmd.add_argument("repo", nargs="?", default=".", help="Repository root")
        cmd.add_argument("--docs-dir", default="docs", help="Docs output directory")
        cmd.add_argument("--config", help="Path to code-docs.yml or JSON config")
        cmd.add_argument("--max-files", type=int, default=5000)
        cmd.add_argument("--exclude", action="append", default=[])
        if name == "review":
            cmd.add_argument("--report", help="Write Markdown review report to this path")
            cmd.add_argument("--github-summary", action="store_true", help="Append review report to GITHUB_STEP_SUMMARY")

    return parser.parse_args()


def parse_scalar(value: str):
    value = value.strip().strip('"').strip("'")
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.isdigit():
        return int(value)
    return value


def parse_simple_yaml(text: str) -> dict[str, object]:
    data: dict[str, object] = {}
    current_key = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line.startswith("  - ") and current_key:
            data.setdefault(current_key, []).append(parse_scalar(line[4:]))
            continue
        if ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            data[key] = [] if value == "" else parse_scalar(value)
    return data


def load_config(repo: Path, config_path: str | None) -> dict[str, object]:
    candidates = []
    if config_path:
        candidates.append(Path(config_path))
    candidates.extend([repo / "code-docs.yml", repo / "code-docs.yaml", repo / "code-docs.json"])

    for candidate in candidates:
        path = candidate if candidate.is_absolute() else repo / candidate
        if not path.exists():
            continue
        text = path.read_text()
        if path.suffix == ".json":
            return json.loads(text)
        return parse_simple_yaml(text)
    return {}


def merge_config(args: argparse.Namespace) -> argparse.Namespace:
    repo = Path(args.repo).resolve()
    config = load_config(repo, getattr(args, "config", None))
    if "docs_dir" in config and args.docs_dir == "docs":
        args.docs_dir = str(config["docs_dir"])
    if "max_files" in config and args.max_files == 5000:
        args.max_files = int(config["max_files"])
    configured_excludes = config.get("exclude", [])
    if isinstance(configured_excludes, str):
        configured_excludes = [configured_excludes]
    args.exclude = [*configured_excludes, *args.exclude]
    args.config_data = config
    return args


def bullet_paths(items: list[dict[str, object]], *, limit: int = 20) -> str:
    if not items:
        return "- None detected\n"
    lines = [f"- `{item['path']}`" for item in items[:limit]]
    if len(items) > limit:
        lines.append(f"- ...and {len(items) - limit} more")
    return "\n".join(lines) + "\n"


def framework_lines(inventory: dict[str, object]) -> str:
    frameworks = inventory.get("frameworks", [])
    if not frameworks:
        return "- None detected\n"
    return "".join(f"- `{item['name']}` from `{item['source']}`\n" for item in frameworks)


def route_lines(inventory: dict[str, object]) -> str:
    routes = inventory.get("routes", [])
    if not routes:
        return "- None detected\n"
    return "".join(
        f"- `{route['method']} {route['path']}` from `{route['source']}` ({route['framework']})\n"
        for route in routes
    )


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
    if inventory.get("frameworks"):
        lines += ["  Frameworks[Detected frameworks]", "  Repo -->|uses| Frameworks"]
    if inventory["manifests"]:
        lines += ["  Manifests[Build and dependency manifests]", "  Repo -->|defines| Manifests"]
    if inventory["interfaces"] or inventory.get("routes"):
        lines += ["  Interfaces[Interfaces and routes]", "  Repo -->|exposes| Interfaces"]
    if inventory["deployments"]:
        lines += ["  Deploy[Deployment automation]", "  Repo -->|ships with| Deploy"]
    lines += ["  Docs[Generated documentation]", "  Repo -->|documents| Docs"]
    return "\n".join(lines) + "\n"


def mermaid_sequence(inventory: dict[str, object]) -> str:
    if inventory.get("routes"):
        route = inventory["routes"][0]
        return f"""sequenceDiagram
  participant Consumer
  participant Route as {route['method']} {route['path']}
  participant Application
  participant Dependency

  Consumer->>Route: Request
  Route->>Application: Validate and dispatch
  Application->>Dependency: Read/write/call
  Dependency-->>Application: Result
  Application-->>Consumer: Response or side effect
"""
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


def validate_mermaid_content(content: str, path: Path) -> list[str]:
    stripped = [line.strip() for line in content.splitlines() if line.strip()]
    if not stripped:
        return [f"{path}: empty diagram"]
    allowed = ("flowchart", "sequenceDiagram", "classDiagram", "stateDiagram", "erDiagram", "gantt", "journey", "pie")
    if not stripped[0].startswith(allowed):
        return [f"{path}: first non-empty line must start with a Mermaid diagram type"]
    errors = []
    for left, right in (("[", "]"), ("(", ")"), ("{", "}")):
        if content.count(left) != content.count(right):
            errors.append(f"{path}: unbalanced {left}{right}")
    return errors


def validate_diagrams(docs_dir: Path) -> list[str]:
    diagrams_dir = docs_dir / "diagrams"
    if not diagrams_dir.exists():
        return [f"{diagrams_dir}: missing diagrams directory"]
    errors: list[str] = []
    for path in sorted(diagrams_dir.glob("*.mmd")):
        errors.extend(validate_mermaid_content(path.read_text(), path))
    return errors


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
- Frameworks detected: `{inventory['counts']['frameworks']}`
- Routes detected: `{inventory['counts']['routes']}`
- Interfaces/routes hints: `{inventory['counts']['interfaces']}`
- Deployment hints: `{inventory['counts']['deployments']}`
- Inventory truncated: `{inventory['truncated']}`

## Key Manifests

{bullet_paths(inventory['manifests'])}

## Detected Frameworks

{framework_lines(inventory)}

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

### Detected Frameworks

{framework_lines(inventory)}

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

## Detected Routes

{route_lines(inventory)}

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
    args = merge_config(args)
    repo = Path(args.repo).resolve()
    docs_dir = (repo / args.docs_dir).resolve()
    generate(repo, docs_dir, args.max_files, args.exclude)
    print(f"Generated docs in {docs_dir}")
    return 0


def command_check(args: argparse.Namespace) -> int:
    args = merge_config(args)
    repo = Path(args.repo).resolve()
    docs_dir = (repo / args.docs_dir).resolve()
    generate(repo, docs_dir, args.max_files, args.exclude)
    diagram_errors = validate_diagrams(docs_dir)
    if diagram_errors:
        print("\n".join(diagram_errors), file=sys.stderr)
        return 1
    if (repo / ".git").exists() and git_diff_has_changes(repo, docs_dir):
        print("Documentation drift detected. Run `code_docs.py generate` and commit the docs changes.", file=sys.stderr)
        return 1
    print("Documentation is up to date.")
    return 0


def command_review(args: argparse.Namespace) -> int:
    args = merge_config(args)
    repo = Path(args.repo).resolve()
    inventory = collect_inventory(repo, max_files=args.max_files, exclude=args.exclude)
    report = render_review_report(inventory)
    print(report)
    if args.report:
        write_text(Path(args.report), report)
    if args.github_summary:
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(report + "\n")
    return 0


def command_validate_diagrams(args: argparse.Namespace) -> int:
    args = merge_config(args)
    repo = Path(args.repo).resolve()
    docs_dir = (repo / args.docs_dir).resolve()
    errors = validate_diagrams(docs_dir)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print("Mermaid diagrams passed lightweight validation.")
    return 0


def render_review_report(inventory: dict[str, object]) -> str:
    frameworks = ", ".join(item["name"] for item in inventory["frameworks"]) or "none detected"
    return f"""## Code documentation review

- Files inventoried: `{inventory['counts']['files']}`
- Frameworks: {frameworks}
- Routes detected: `{inventory['counts']['routes']}`
- Interface hints: `{inventory['counts']['interfaces']}`
- Deployment hints: `{inventory['counts']['deployments']}`
- Inventory truncated: `{inventory['truncated']}`

### Recommended next checks

- Confirm generated Mermaid diagrams match the real architecture.
- Confirm detected routes are public APIs, internal handlers, or framework conventions.
- Add owner/team, service name, and strictness to `code-docs.yml` for stable CI behavior.
"""


def main() -> int:
    args = parse_args()
    if args.command == "generate":
        return command_generate(args)
    if args.command == "check":
        return command_check(args)
    if args.command == "review":
        return command_review(args)
    if args.command == "validate-diagrams":
        return command_validate_diagrams(args)
    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
