from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "SCAFFOLD_MANIFEST.json"
EXCLUDED_PARTS = {
    ".git",
    ".attune",
    ".mypy_cache",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "candidates",
    "dist",
    "state",
}
EXCLUDED_NAMES = {OUTPUT.name, ".coverage", ".DS_Store", "Thumbs.db"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def included_files() -> list[Path]:
    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if path.name in EXCLUDED_NAMES:
            continue
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if any(part.endswith(".egg-info") for part in relative.parts):
            continue
        if path.suffix == ".pyc":
            continue
        paths.append(path)
    return sorted(paths, key=lambda value: value.relative_to(ROOT).as_posix())


def main() -> int:
    files = []
    for path in included_files():
        relative = path.relative_to(ROOT).as_posix()
        files.append(
            {
                "path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = {
        "schema_version": 1,
        "scaffold": "harness-reserve",
        "version": (ROOT / "VERSION").read_text(encoding="utf-8").strip(),
        "manifest_date": date.today().isoformat(),
        "self_excluded": OUTPUT.name,
        "file_count": len(files),
        "files": files,
    }
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"PASS: wrote {OUTPUT.name} with {len(files)} file records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
