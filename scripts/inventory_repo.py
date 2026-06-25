#!/usr/bin/env python3
"""Create a deterministic repository inventory for documentation generation."""

from __future__ import annotations

import argparse
import ast
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
    ".husky",
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

CALL_STOP_WORDS = {
    "app",
    "async",
    "await",
    "console",
    "def",
    "delete",
    "for",
    "function",
    "get",
    "if",
    "json",
    "len",
    "listen",
    "map",
    "next",
    "patch",
    "post",
    "print",
    "put",
    "res",
    "return",
    "send",
    "str",
    "status",
}

DATA_HINT_WORDS = (
    "collection",
    "database",
    "db",
    "find",
    "model",
    "mongoose",
    "prisma",
    "query",
    "repo",
    "repository",
    "save",
    "schema",
    "select",
    "sql",
    "supabase",
)


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
    return any(part in excludes or part.endswith(".egg-info") for part in rel_parts)


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


def ast_call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        current = node
        while isinstance(current, ast.Attribute):
            current = current.value
        if isinstance(current, ast.Name) and current.id.lower() not in CALL_STOP_WORDS:
            return current.id
        return node.attr
    return None


def ast_route_from_decorator(decorator: ast.AST) -> tuple[str, str] | None:
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in {"get", "post", "put", "patch", "delete"}:
        return None
    owner = func.value
    if not isinstance(owner, ast.Name) or owner.id not in {"app", "router"}:
        return None
    if not decorator.args or not isinstance(decorator.args[0], ast.Constant) or not isinstance(decorator.args[0].value, str):
        return None
    return func.attr.upper(), decorator.args[0].value


def ast_function_calls(function: ast.AST) -> list[str]:
    calls: list[str] = []
    for node in ast.walk(function):
        if isinstance(node, ast.Call):
            name = ast_call_name(node.func)
            if name and name.lower() not in CALL_STOP_WORDS and name not in calls:
                calls.append(name)
    return calls[:12]


def python_ast_routes_and_symbols(
    root: Path,
    files: list[dict[str, object]],
) -> tuple[list[dict[str, str]], dict[str, tuple[list[str], list[str]]]]:
    routes: list[dict[str, str]] = []
    symbols: dict[str, tuple[list[str], list[str]]] = {}

    for item in files:
        if "test" in item["tags"]:
            continue
        path = root / str(item["path"])
        if path.suffix.lower() != ".py":
            continue
        text = read_text(path)
        if not text:
            continue
        try:
            tree = ast.parse(text)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            calls = ast_function_calls(node)
            data_hints = extract_data_hints(" ".join([node.name, *calls]))
            symbols[node.name] = (calls, data_hints)
            for decorator in node.decorator_list:
                route = ast_route_from_decorator(decorator)
                if route:
                    method, route_path = route
                    routes.append(
                        {
                            "framework": "FastAPI/Flask",
                            "method": method,
                            "path": route_path,
                            "source": str(item["path"]),
                            "entrypoint": node.name,
                        }
                    )

    return routes, symbols


def extract_routes(root: Path, files: list[dict[str, object]]) -> list[dict[str, str]]:
    routes, _python_symbols = python_ast_routes_and_symbols(root, files)
    patterns = [
        ("Express/Fastify", re.compile(r"\b(?:app|router)\.(get|post|put|patch|delete)\s*\(\s*['\"]([^'\"]+)")),
        ("Spring", re.compile(r"@(GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)\s*\(\s*(?:value\s*=\s*)?['\"]([^'\"]+)")),
    ]

    for item in files:
        if "test" in item["tags"]:
            continue
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
        if "test" in item["tags"]:
            continue
        rel = str(item["path"])
        if rel.startswith("app/api/") and rel.endswith(("route.ts", "route.js")):
            route = "/" + rel.removeprefix("app/api/").rsplit("/route.", 1)[0]
            routes.append({"framework": "Next.js", "method": "ANY", "path": route, "source": rel})

    unique = {(route["framework"], route["method"], route["path"], route["source"]): route for route in routes}
    return [unique[key] for key in sorted(unique)]


def first_match(patterns: list[str], text: str) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def handler_reference(block: str) -> str | None:
    match = re.search(r"['\"][^'\"]+['\"]\s*,\s*([A-Za-z_][A-Za-z0-9_]*)", block)
    if not match:
        return None
    name = match.group(1)
    if name.lower() in CALL_STOP_WORDS:
        return None
    return name


def extract_calls(block: str) -> list[str]:
    calls: list[str] = []
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)(?:\.[A-Za-z_][A-Za-z0-9_]*)+\s*\(", block):
        name = match.group(1)
        if name.lower() not in CALL_STOP_WORDS and name not in calls:
            calls.append(name)
    for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", block):
        name = match.group(1)
        if name.lower() in CALL_STOP_WORDS:
            continue
        if name not in calls:
            calls.append(name)
    return calls[:12]


def extract_data_hints(block: str) -> list[str]:
    lowered = block.lower()
    hints = [word for word in DATA_HINT_WORDS if word in lowered]
    return hints[:8]


def route_window(text: str, start: int, *, suffix: str) -> str:
    if suffix == ".py":
        rest = text[start:]
        next_route = re.search(r"\n@(?:app|router)\.(?:get|post|put|patch|delete)\s*\(", rest[1:])
        return rest[: next_route.start() + 1] if next_route else rest[:2500]

    rest = text[start:]
    next_route = re.search(r"\b(?:app|router)\.(?:get|post|put|patch|delete)\s*\(", rest[1:])
    route_end = re.search(r"\n\s*\}\s*\)\s*;?", rest)
    end_positions = []
    if next_route:
        end_positions.append(next_route.start() + 1)
    if route_end:
        end_positions.append(route_end.end())
    return rest[: min(end_positions)] if end_positions else rest[:2500]


def symbol_windows(root: Path, files: list[dict[str, object]]) -> dict[str, str]:
    symbols: dict[str, str] = {}
    pattern = re.compile(
        r"\b(?:export\s+)?(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)|"
        r"\b(?:export\s+)?(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=|"
        r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\("
    )
    for item in files:
        if "test" in item["tags"]:
            continue
        path = root / str(item["path"])
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = read_text(path)
        if not text:
            continue
        for match in pattern.finditer(text):
            name = next(group for group in match.groups() if group)
            symbols.setdefault(name, text[match.start() : match.start() + 1800])
    return symbols


def expand_calls_and_data(calls: list[str], data_hints: list[str], symbols: dict[str, str]) -> tuple[list[str], list[str]]:
    expanded_calls = list(calls)
    expanded_data = list(data_hints)
    queue = list(calls)
    seen = set(queue)

    for _ in range(2):
        next_queue: list[str] = []
        for call in queue:
            block = symbols.get(call)
            if not block:
                continue
            for hint in extract_data_hints(block):
                if hint not in expanded_data:
                    expanded_data.append(hint)
            for downstream in extract_calls(block):
                if downstream not in seen:
                    seen.add(downstream)
                    expanded_calls.append(downstream)
                    next_queue.append(downstream)
        queue = next_queue

    return expanded_calls[:12], expanded_data[:8]


def expand_python_calls_and_data(
    calls: list[str],
    data_hints: list[str],
    symbols: dict[str, tuple[list[str], list[str]]],
) -> tuple[list[str], list[str]]:
    expanded_calls = list(calls)
    expanded_data = list(data_hints)
    queue = list(calls)
    seen = set(queue)

    for _ in range(2):
        next_queue: list[str] = []
        for call in queue:
            symbol = symbols.get(call)
            if not symbol:
                continue
            downstream_calls, downstream_data = symbol
            for hint in downstream_data:
                if hint not in expanded_data:
                    expanded_data.append(hint)
            for downstream in downstream_calls:
                if downstream not in seen:
                    seen.add(downstream)
                    expanded_calls.append(downstream)
                    next_queue.append(downstream)
        queue = next_queue

    return expanded_calls[:12], expanded_data[:8]


def extract_flows(root: Path, files: list[dict[str, object]], routes: list[dict[str, str]]) -> list[dict[str, object]]:
    flows: list[dict[str, object]] = []
    routes_by_source: dict[str, list[dict[str, str]]] = {}
    symbols = symbol_windows(root, files)
    _python_routes, python_symbols = python_ast_routes_and_symbols(root, files)
    for route in routes:
        routes_by_source.setdefault(route["source"], []).append(route)

    for source, source_routes in routes_by_source.items():
        path = root / source
        text = read_text(path)
        if not text:
            continue

        for route in source_routes:
            if path.suffix.lower() == ".py" and route.get("entrypoint"):
                entrypoint = route["entrypoint"]
                calls, data_hints = python_symbols.get(entrypoint, ([], []))
                calls, data_hints = expand_python_calls_and_data(calls, data_hints, python_symbols)
                flows.append(
                    {
                        "route": f"{route['method']} {route['path']}",
                        "framework": route["framework"],
                        "source": source,
                        "entrypoint": entrypoint,
                        "calls": [call for call in calls if call != entrypoint],
                        "data_hints": data_hints,
                        "confidence": "ast",
                        "analyzer": "python-ast",
                    }
                )
                continue

            escaped_path = re.escape(route["path"])
            method = route["method"].lower()
            if route["framework"] == "Spring":
                pattern = re.compile(rf"@(?:{method.title()}Mapping|RequestMapping)\s*\([^)]*['\"]{escaped_path}['\"]", re.I)
            elif path.suffix == ".py":
                pattern = re.compile(rf"@(?:app|router)\.{method}\s*\(\s*['\"]{escaped_path}['\"]")
            else:
                pattern = re.compile(rf"\b(?:app|router)\.{method}\s*\(\s*['\"]{escaped_path}['\"]")

            match = pattern.search(text)
            if not match:
                continue
            window = route_window(text, match.start(), suffix=path.suffix.lower())
            entrypoint = handler_reference(window) or first_match(
                [
                    r"(?:async\s+)?function\s+([A-Za-z_][A-Za-z0-9_]*)",
                    r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                    r"public\s+\w+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
                ],
                window,
            )
            calls = [call for call in extract_calls(window) if call != entrypoint]
            if entrypoint and entrypoint in symbols and entrypoint not in calls:
                calls.insert(0, entrypoint)
            calls, data_hints = expand_calls_and_data(calls, extract_data_hints(window), symbols)
            calls = [call for call in calls if call != entrypoint]
            flows.append(
                {
                    "route": f"{route['method']} {route['path']}",
                    "framework": route["framework"],
                    "source": source,
                    "entrypoint": entrypoint or "inline handler",
                    "calls": calls,
                    "data_hints": data_hints,
                    "confidence": "heuristic",
                    "analyzer": "typescript-structured" if path.suffix.lower() in {".ts", ".tsx", ".js", ".jsx", ".mjs"} else "regex-window",
                }
            )

    unique = {(flow["route"], flow["source"], flow["entrypoint"]): flow for flow in flows}
    return [unique[key] for key in sorted(unique)][:100]


def collect_inventory(
    repo: str | Path,
    *,
    max_files: int = 5000,
    exclude: list[str] | None = None,
    repo_name: str | None = None,
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
    flows = extract_flows(root, files, routes)

    return {
        "repo": repo_name or root.name,
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
            "flows": len(flows),
        },
        "frameworks": frameworks,
        "routes": routes[:200],
        "flows": flows,
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
