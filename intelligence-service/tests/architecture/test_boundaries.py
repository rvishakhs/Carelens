"""Dependency rules for a reusable intelligence service."""

import ast
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]


def imported_modules(path):
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            yield node.module or ""


def test_carelens_application_is_not_imported():
    for path in (SERVICE_ROOT / "src/intelligence").rglob("*.py"):
        assert not any(m == "app" or m.startswith("app.") for m in imported_modules(path)), path


def test_provider_sdks_are_confined_to_adapters():
    root = SERVICE_ROOT / "src/intelligence"
    for path in root.rglob("*.py"):
        if path.is_relative_to(root / "providers"):
            continue
        assert not any(m.split(".")[0] in {"openai", "anthropic", "boto3"} for m in imported_modules(path)), (
            path
        )


def test_tests_do_not_import_other_test_modules():
    for path in (SERVICE_ROOT / "tests").rglob("*.py"):
        assert not any(
            m.startswith("tests.") and any(part.startswith("test_") for part in m.split("."))
            for m in imported_modules(path)
        ), path
