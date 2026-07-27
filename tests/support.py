from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
from typing import Iterator
from contextlib import contextmanager

from harness_reserve.manifest import LoadedManifest, load_manifest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPOSITORY_ROOT / "examples" / "minimal-python-project"


@contextmanager
def copied_example() -> Iterator[Path]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "project"
        shutil.copytree(EXAMPLE_ROOT, root)
        yield root


def load_example(root: Path) -> LoadedManifest:
    return load_manifest(root, root / ".harness-reserve" / "operator.json")


def read_manifest(root: Path) -> dict:
    path = root / ".harness-reserve" / "operator.json"
    return json.loads(path.read_text(encoding="utf-8"))


def write_manifest(root: Path, value: dict) -> None:
    path = root / ".harness-reserve" / "operator.json"
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
