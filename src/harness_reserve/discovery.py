from __future__ import annotations

from pathlib import Path

from .constants import MANIFEST_RELATIVE_PATH
from .errors import DiscoveryError
from .util import is_relative_to


def _contained_manifest(root: Path, manifest: Path) -> Path:
    root_resolved = root.expanduser().resolve()
    manifest_resolved = manifest.expanduser().resolve()
    if not manifest_resolved.is_file():
        raise DiscoveryError(f"Manifest does not exist: {manifest_resolved}")
    if not is_relative_to(manifest_resolved, root_resolved):
        raise DiscoveryError(
            "Manifest must resolve inside the project root: "
            f"{manifest_resolved} is outside {root_resolved}."
        )
    return manifest_resolved


def discover_project(
    start: Path | None = None,
    *,
    project_root: Path | None = None,
    manifest_path: Path | None = None,
) -> tuple[Path, Path]:
    if manifest_path is not None:
        supplied_manifest = manifest_path.expanduser()
        if project_root is not None:
            root = project_root.expanduser().resolve()
        else:
            manifest = supplied_manifest.resolve()
            if manifest.parent.name == ".harness-reserve":
                root = manifest.parent.parent.resolve()
            else:
                root = manifest.parent.resolve()
        manifest = _contained_manifest(root, supplied_manifest)
        return root, manifest

    if project_root is not None:
        root = project_root.expanduser().resolve()
        manifest_path_value = root / MANIFEST_RELATIVE_PATH
        if not manifest_path_value.is_file():
            raise DiscoveryError(
                f"No {MANIFEST_RELATIVE_PATH} exists under project root {root}."
            )
        manifest = _contained_manifest(root, manifest_path_value)
        return root, manifest

    current = (start or Path.cwd()).expanduser().resolve()
    if current.is_file():
        current = current.parent
    for candidate_root in (current, *current.parents):
        manifest_path_value = candidate_root / MANIFEST_RELATIVE_PATH
        if manifest_path_value.is_file():
            manifest = _contained_manifest(candidate_root, manifest_path_value)
            return candidate_root.resolve(), manifest
    raise DiscoveryError(
        f"Could not find {MANIFEST_RELATIVE_PATH} from {current} or any parent."
    )
