#!/usr/bin/env python3
"""Create a deterministic repository inventory for documentation generation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


DEFAULT_EXCLUDES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".next",
    ".nuxt",
    ".astro",
    ".cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "target",
    "vendor",
    "__pycache__",
    ".DS_Store",
}

MANIFEST_NAMES = {
    "package.json",
    "pnpm-workspace.yaml",
    "yarn.lock",
    "package-lock.json",
    "pyproject.toml",
    "requirements.txt",
    "poetry.lock",
    "Pipfile",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "pom.xml",
    "build.gradle",
    "settings.gradle",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "Makefile",
    "justfile",
}

ENTRYPOINT_HINTS = {
    "main.py",
    "app.py",
    "server.py",
    "index.js",
    "index.ts",
    "main.ts",
    "main.go",
    "cmd",
    "src/main",
}

CONFIG_HINTS = {
    ".env.example",
    ".env.sample",
    "astro.config.mjs",
    "next.config.js",
    "vite.config.ts",
    "tsconfig.json",
    "biome.json",
    "eslint.config.js",
    "terraform.tf",
    "serverless.yml",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".", help="Repository root")
    parser.add_argument("--out", help="Write JSON inventory to this path")
    parser.add_argument(
        "--max-files",
        type=int,
        default=5000,
        help="Maximum files to include before truncating",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional directory or file names to exclude",
    )
    return parser.parse_args()


def should_skip(path: Path, root: Path, excludes: set[str]) -> bool:
    rel_parts = path.relative_to(root).parts
    return any(part in excludes for part in rel_parts)


def classify(path: Path) -> list[str]:
    tags: list[str] = []
    name = path.name
    rel = path.as_posix()

    if name in MANIFEST_NAMES:
        tags.append("manifest")
    if name in CONFIG_HINTS or name.startswith(".github"):
        tags.append("config")
    if "test" in rel.lower() or "spec" in rel.lower():
        tags.append("test")
    if any(hint in rel for hint in ("routes", "controllers", "api", "pages")):
        tags.append("interface")
    if any(hint in rel for hint in ("migration", "schema", "models")):
        tags.append("data")
    if any(hint in rel for hint in ("deploy", "infra", "terraform", "k8s", "helm")):
        tags.append("deployment")
    if name in ENTRYPOINT_HINTS or any(rel.endswith(f"/{hint}") for hint in ENTRYPOINT_HINTS):
        tags.append("entrypoint")

    return sorted(set(tags))


def build_tree(files: list[dict[str, object]]) -> dict[str, object]:
    tree: dict[str, object] = {}
    for item in files:
        current = tree
        parts = str(item["path"]).split("/")
        for part in parts[:-1]:
            current = current.setdefault(part, {})
        current[parts[-1]] = None
    return tree


def main() -> int:
    args = parse_args()
    root = Path(args.repo).resolve()
    excludes = DEFAULT_EXCLUDES | set(args.exclude)

    if not root.exists():
        raise SystemExit(f"Repo path does not exist: {root}")

    files: list[dict[str, object]] = []
    truncated = False

    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if d not in excludes)
        if should_skip(current, root, excludes):
            continue

        for filename in sorted(filenames):
            path = current / filename
            if should_skip(path, root, excludes):
                continue
            rel = path.relative_to(root).as_posix()
            try:
                size = path.stat().st_size
            except OSError:
                continue

            files.append(
                {
                    "path": rel,
                    "size": size,
                    "suffix": path.suffix.lower(),
                    "tags": classify(Path(rel)),
                }
            )
            if len(files) >= args.max_files:
                truncated = True
                break
        if truncated:
            break

    manifests = [item for item in files if "manifest" in item["tags"]]
    entrypoints = [item for item in files if "entrypoint" in item["tags"]]
    interfaces = [item for item in files if "interface" in item["tags"]]
    deployments = [item for item in files if "deployment" in item["tags"]]

    inventory = {
        "repo": root.name,
        "root": str(root),
        "truncated": truncated,
        "counts": {
            "files": len(files),
            "manifests": len(manifests),
            "entrypoints": len(entrypoints),
            "interfaces": len(interfaces),
            "deployments": len(deployments),
        },
        "manifests": manifests,
        "entrypoints": entrypoints,
        "interfaces": interfaces[:200],
        "deployments": deployments[:200],
        "files": files,
        "tree": build_tree(files[:500]),
    }

    output = json.dumps(inventory, indent=2, sort_keys=True)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output + "\n")
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
