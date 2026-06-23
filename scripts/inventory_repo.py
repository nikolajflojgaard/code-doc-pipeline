#!/usr/bin/env python3
"""Create a deterministic repository inventory for documentation generation."""

from __future__ import annotations

import argparse
import json
import os
import re
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

TEXT_SUFFIXES = {
    ".cs",
    ".go",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".py",
    ".ts",
    ".tsx",
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
    if name == "Dockerfile":
        tags.append("deployment")
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


def read_text(path: Path, *, max_bytes: int = 500_000) -> str:
    try:
        if path.stat().st_size > max_bytes:
            return ""
        return path.read_text(errors="ignore")
    except OSError:
        return ""


def detect_frameworks(root: Path, files: list[dict[str, object]]) -> list[dict[str, str]]:
    detected: dict[str, dict[str, str]] = {}
    paths = {str(item["path"]) for item in files}

    package_json = root / "package.json"
    if package_json.exists():
        try:
            package = json.loads(read_text(package_json))
            deps = {
                **package.get("dependencies", {}),
                **package.get("devDependencies", {}),
            }
            for name, framework in {
                "express": "Express",
                "fastify": "Fastify",
                "next": "Next.js",
                "astro": "Astro",
                "@nestjs/core": "NestJS",
            }.items():
                if name in deps:
                    detected[framework] = {"name": framework, "source": "package.json"}
        except json.JSONDecodeError:
            pass

    requirements = "\n".join(
        read_text(root / path)
        for path in ("requirements.txt", "pyproject.toml", "Pipfile")
        if (root / path).exists()
    ).lower()
    for needle, framework in {
        "fastapi": "FastAPI",
        "django": "Django",
        "flask": "Flask",
    }.items():
        if needle in requirements:
            detected[framework] = {"name": framework, "source": "python manifest"}

    java_build = "\n".join(
        read_text(root / path)
        for path in ("pom.xml", "build.gradle", "settings.gradle")
        if (root / path).exists()
    ).lower()
    if "spring-boot" in java_build or "org.springframework" in java_build:
        detected["Spring"] = {"name": "Spring", "source": "java build file"}

    if any(path.endswith(".csproj") for path in paths):
        detected[".NET"] = {"name": ".NET", "source": "*.csproj"}
    if any(path.endswith(".tf") for path in paths):
        detected["Terraform"] = {"name": "Terraform", "source": "*.tf"}
    if any(path.endswith((".yaml", ".yml")) and ("k8s" in path or "helm" in path) for path in paths):
        detected["Kubernetes"] = {"name": "Kubernetes", "source": "k8s/helm yaml"}

    return [detected[name] for name in sorted(detected)]


def extract_routes(root: Path, files: list[dict[str, object]]) -> list[dict[str, str]]:
    routes: list[dict[str, str]] = []
    patterns = [
        ("Express/Fastify", re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)")),
        ("FastAPI/Flask", re.compile(r"@(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)")),
        ("Spring", re.compile(r"@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)\s*\(\s*(?:value\s*=\s*)?['\"]([^'\"]+)")),
    ]

    for item in files:
        path = root / str(item["path"])
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text(path)
        if not text:
            continue
        for framework, pattern in patterns:
            for match in pattern.finditer(text):
                method = match.group(1).replace("Mapping", "").upper() or "ANY"
                if method == "REQUEST":
                    method = "ANY"
                routes.append(
                    {
                        "framework": framework,
                        "method": method,
                        "path": match.group(2),
                        "source": str(item["path"]),
                    }
                )

    for item in files:
        rel = str(item["path"])
        if rel.startswith("app/api/") and rel.endswith(("route.ts", "route.js")):
            route = "/" + rel.removeprefix("app/api/").rsplit("/route.", 1)[0]
            routes.append({"framework": "Next.js", "method": "ANY", "path": route, "source": rel})

    unique = {(route["framework"], route["method"], route["path"], route["source"]): route for route in routes}
    return [unique[key] for key in sorted(unique)]


def collect_inventory(
    repo: str | Path,
    *,
    max_files: int = 5000,
    exclude: list[str] | None = None,
) -> dict[str, object]:
    root = Path(repo).resolve()
    excludes = DEFAULT_EXCLUDES | set(exclude or [])
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
            if len(files) >= max_files:
                truncated = True
                break
        if truncated:
            break

    manifests = [item for item in files if "manifest" in item["tags"]]
    entrypoints = [item for item in files if "entrypoint" in item["tags"]]
    interfaces = [item for item in files if "interface" in item["tags"]]
    deployments = [item for item in files if "deployment" in item["tags"]]
    frameworks = detect_frameworks(root, files)
    routes = extract_routes(root, files)

    return {
        "repo": root.name,
        "root": ".",
        "truncated": truncated,
        "counts": {
            "files": len(files),
            "manifests": len(manifests),
            "entrypoints": len(entrypoints),
            "interfaces": len(interfaces),
            "deployments": len(deployments),
            "frameworks": len(frameworks),
            "routes": len(routes),
        },
        "frameworks": frameworks,
        "routes": routes[:200],
        "manifests": manifests,
        "entrypoints": entrypoints,
        "interfaces": interfaces[:200],
        "deployments": deployments[:200],
        "files": files,
        "tree": build_tree(files[:500]),
    }


def main() -> int:
    args = parse_args()
    inventory = collect_inventory(
        args.repo,
        max_files=args.max_files,
        exclude=args.exclude,
    )

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
