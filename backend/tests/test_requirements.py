"""Everything app/ imports must be declared in requirements.txt.

deploy.sh rsyncs requirements.txt to the box and pip-installs exactly that, with
no wheels/ to fall back on. A third-party import that is not declared works fine
here — some other package pulled it in — and is simply absent there, so the
service dies on startup with an ImportError and the first anyone knows is a
journalctl dump.

That is not hypothetical: `pydantic` was imported directly by app/schemas.py and
never declared. It installed only because fastapi depends on it, which breaks
quietly the day fastapi loosens that dependency.

The converse is deliberately NOT asserted. requirements.txt may legitimately
carry something app/ never imports by name — uvicorn is the server and is
launched by systemd, not imported.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"
REQUIREMENTS = BACKEND / "requirements.txt"

# Distribution name -> the name you import. Only needed where they differ.
_IMPORT_NAME = {"ortools": "ortools", "fastapi": "fastapi", "pydantic": "pydantic", "uvicorn": "uvicorn"}


def declared() -> set[str]:
    names = set()
    for raw in REQUIREMENTS.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "-")):
            continue
        dist = line.split("==")[0].split(">=")[0].split("[")[0].strip().lower()
        names.add(_IMPORT_NAME.get(dist, dist.replace("-", "_")))
    return names


def top_level_imports() -> set[str]:
    found = set()
    for path in sorted(APP.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    found.add(node.module.split(".")[0])
    return found


def test_every_third_party_import_in_app_is_declared():
    third_party = {
        name
        for name in top_level_imports()
        if name not in sys.stdlib_module_names and name != "app"
    }
    undeclared = sorted(third_party - declared())
    assert not undeclared, (
        f"imported by backend/app/ but not in requirements.txt: {undeclared}. "
        "The box installs exactly requirements.txt, so this would be an "
        "ImportError on startup and nothing else."
    )


def test_the_check_can_actually_fail():
    """A guard nothing can fail is not a guard."""
    assert "definitely_not_a_real_package" not in declared()
