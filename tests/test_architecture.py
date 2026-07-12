"""Architecture-rule enforcement (Clean Architecture + tenant safety).

Pure static analysis over the source tree — no Neo4j required. Fails CI if a
layer imports a layer it must not, if Cypher is run outside the sanctioned
``tenant_query``/``initialize`` seams, or if a file exceeds the size limit.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "context_engine"

# layer -> layers it may NOT import from
_FORBIDDEN_IMPORTS = {
    "core": {"api", "prediction", "profiler", "mcp"},
    "prediction": {"api", "profiler", "mcp"},
    "profiler": {"api", "prediction", "mcp"},
}

_MAX_FILE_LINES = 300

# The only places raw Cypher execution is allowed: the tenant_query wrapper and
# the schema-DDL bootstrap, both in core/graph.py.
_ALLOWED_RAW_RUN = {("core/graph.py", "tenant_query"), ("core/graph.py", "initialize")}


def _source_files() -> list[Path]:
    return [
        path
        for path in SRC_ROOT.rglob("*.py")
        if "__pycache__" not in path.parts
    ]


def _relative(path: Path) -> str:
    return path.relative_to(SRC_ROOT).as_posix()


def _layer_of(path: Path) -> str:
    return path.relative_to(SRC_ROOT).parts[0]


def _internal_import_layers(tree: ast.AST) -> set[str]:
    layers: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("context_engine."):
                    layers.add(alias.name.split(".")[1])
            continue
        else:
            continue
        if module.startswith("context_engine."):
            layers.add(module.split(".")[1])
    return layers


def test_layers_do_not_import_forbidden_layers() -> None:
    violations: list[str] = []
    for path in _source_files():
        layer = _layer_of(path)
        forbidden = _FORBIDDEN_IMPORTS.get(layer)
        if forbidden is None:
            continue
        tree = ast.parse(path.read_text())
        offending = _internal_import_layers(tree) & forbidden
        if offending:
            violations.append(f"{_relative(path)} imports {sorted(offending)}")
    assert not violations, "Dependency rule violations: " + "; ".join(violations)


def _raw_run_calls(tree: ast.AST) -> list[str]:
    """Return the enclosing function name of each tx.run/session.run call."""
    calls: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Call)
                and isinstance(inner.func, ast.Attribute)
                and inner.func.attr == "run"
                and isinstance(inner.func.value, ast.Name)
                and inner.func.value.id in {"tx", "session"}
            ):
                calls.append(node.name)
    return calls


def test_cypher_only_runs_through_tenant_query() -> None:
    violations: list[str] = []
    for path in _source_files():
        tree = ast.parse(path.read_text())
        for function_name in _raw_run_calls(tree):
            if (_relative(path), function_name) not in _ALLOWED_RAW_RUN:
                violations.append(f"{_relative(path)}::{function_name}")
    assert not violations, (
        "Raw tx.run/session.run outside tenant_query: " + "; ".join(violations)
    )


def test_no_source_file_exceeds_line_limit() -> None:
    oversized = [
        f"{_relative(path)} ({count} lines)"
        for path in _source_files()
        if (count := len(path.read_text().splitlines())) > _MAX_FILE_LINES
    ]
    assert not oversized, "Files over 300 lines: " + "; ".join(oversized)
