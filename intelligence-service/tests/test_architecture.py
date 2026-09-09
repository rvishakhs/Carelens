import ast
from pathlib import Path


def test_package_does_not_import_carelens_or_provider_sdks() -> None:
    root = Path(__file__).parents[1] / "src" / "intelligence"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            assert not any(m == "app" or m.startswith("app.") for m in modules), path
            assert not any(m.split(".")[0] in {"openai", "anthropic", "boto3"} for m in modules), path
