"""Tracked thin bootstrap for one pinned ATTUNE Codex host-state integration."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from pathlib import Path


WRAPPER_PATH = "tools/attune_host.py"
OBJECT_REPOSITORY = ".attune/vendor/attune.git"
MATERIALIZED_ROOT = ".attune/materialized/attune"
BOOTSTRAP_RELATIVE = "adapters/codex/host-state/bootstrap-host.py"
BOOTSTRAP_TIMEOUT_SECONDS = 180
ATTUNE_OBJECT_FORMAT = "sha1"
ATTUNE_COMMIT = "e55d1194a7da7899fcf601cccba2c941fe91876e"
ATTUNE_TREE = "8bfcb1125f69f957136207ec8755b499765a1bd4"
BOOTSTRAP_SHA256 = "55463a08be2e519198d3d9f7a68688ea2f98a8792797abcdbec7b7e5332bad95"
STDIN_EXECUTOR = (
    "import sys\n"
    "script=sys.argv[1]\n"
    "args=sys.argv[2:]\n"
    "payload=sys.stdin.buffer.read()\n"
    "sys.argv=[script,*args]\n"
    "scope={'__name__':'__main__','__file__':script,'__package__':None}\n"
    "exec(compile(payload,script,'exec'),scope,scope)\n"
)
SAFE_MESSAGES = {
    "bootstrap_host_mismatch": "The clean committed host does not match its ATTUNE bootstrap.",
    "bootstrap_materialization_mismatch": "The pinned ATTUNE bootstrap is missing or mismatched.",
    "bootstrap_unavailable": "The ATTUNE host bootstrap could not complete; no success is inferred.",
}
_GIT_EXECUTABLE: Path | None = None


class BootstrapError(Exception):
    """Allowlisted first-stage failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _fail(code: str) -> None:
    raise BootstrapError(code)


def _safe_environment() -> dict[str, str]:
    allowed = {
        "COMSPEC",
        "HOME",
        "HOMEDRIVE",
        "HOMEPATH",
        "LANG",
        "LC_ALL",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SYSTEMDRIVE",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    }
    environment = {
        key: value for key, value in os.environ.items() if key.upper() in allowed
    }
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_NO_REPLACE_OBJECTS"] = "1"
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    environment["GIT_TERMINAL_PROMPT"] = "0"
    environment["NoDefaultCurrentDirectoryInExePath"] = "1"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    return environment


def _git(
    repository: Path,
    *arguments: str,
    binary: bool = False,
    code: str,
) -> str | bytes:
    try:
        completed = subprocess.run(
            [
                str(_git_executable(code=code)),
                "--no-replace-objects",
                "-c",
                "core.fsmonitor=false",
                "-C",
                str(repository),
                *arguments,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=not binary,
            timeout=20,
            check=False,
            env=_safe_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        _fail(code)
    if completed.returncode != 0:
        _fail(code)
    if binary:
        return bytes(completed.stdout)
    return str(completed.stdout).strip()


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(
        attributes
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x00000400)
    )


def _reject_chain(path: Path, *, code: str) -> None:
    lexical = Path(os.path.abspath(path))
    for candidate in (lexical, *lexical.parents):
        if _is_link_or_reparse(candidate):
            _fail(code)


def _git_executable(*, code: str) -> Path:
    global _GIT_EXECUTABLE
    if _GIT_EXECUTABLE is not None:
        return _GIT_EXECUTABLE
    names = ("git.exe",) if os.name == "nt" else ("git",)
    for raw_entry in os.environ.get("PATH", "").split(os.pathsep):
        entry_text = raw_entry.strip().strip('"')
        if not entry_text:
            continue
        entry = Path(entry_text)
        if not entry.is_absolute():
            continue
        for name in names:
            candidate = entry / name
            try:
                if (
                    any(
                        _is_link_or_reparse(part)
                        for part in (candidate, *candidate.parents)
                    )
                    or not candidate.is_file()
                    or not os.access(candidate, os.X_OK)
                ):
                    continue
                _GIT_EXECUTABLE = candidate.resolve(strict=True)
            except OSError:
                continue
            return _GIT_EXECUTABLE
    _fail(code)


def _reject_status_hazards(repository: Path, *, code: str) -> None:
    config_keys = bytes(
        _git(
            repository,
            "config",
            "--includes",
            "--null",
            "--name-only",
            "--list",
            binary=True,
            code=code,
        )
    ).split(b"\0")
    for key in config_keys:
        key = key.lower()
        if key.startswith(b"filter.") and key.endswith(
            (b".clean", b".process", b".required")
        ):
            _fail(code)
    staged_entries = bytes(
        _git(
            repository,
            "ls-files",
            "--stage",
            "-z",
            binary=True,
            code=code,
        )
    ).split(b"\0")
    if any(entry.startswith(b"160000 ") for entry in staged_entries):
        _fail(code)
    entries = bytes(
        _git(
            repository,
            "ls-files",
            "-v",
            "-z",
            binary=True,
            code=code,
        )
    ).split(b"\0")
    for entry in entries:
        if not entry:
            continue
        if len(entry) < 3 or entry[1:2] != b" ":
            _fail(code)
        tag = entry[:1]
        if tag == b"S" or tag.islower():
            _fail(code)


def _under(root: Path, relative: str, *, directory: bool = False) -> Path:
    _reject_chain(root, code="bootstrap_materialization_mismatch")
    try:
        root = root.resolve(strict=True)
    except OSError:
        _fail("bootstrap_materialization_mismatch")
    path = root
    for part in relative.split("/"):
        if not part or part in {".", ".."}:
            _fail("bootstrap_materialization_mismatch")
        path = path / part
        if _is_link_or_reparse(path):
            _fail("bootstrap_materialization_mismatch")
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        _fail("bootstrap_materialization_mismatch")
    if root not in resolved.parents:
        _fail("bootstrap_materialization_mismatch")
    if directory:
        if not resolved.is_dir():
            _fail("bootstrap_materialization_mismatch")
    elif not resolved.is_file():
        _fail("bootstrap_materialization_mismatch")
    return resolved


def _clean_host(host_root: Path) -> tuple[str, str]:
    head = str(
        _git(
            host_root,
            "rev-parse",
            "HEAD",
            code="bootstrap_host_mismatch",
        )
    )
    tree = str(
        _git(
            host_root,
            "rev-parse",
            "HEAD^{tree}",
            code="bootstrap_host_mismatch",
        )
    )
    _reject_status_hazards(host_root, code="bootstrap_host_mismatch")
    if _git(
        host_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        code="bootstrap_host_mismatch",
    ):
        _fail("bootstrap_host_mismatch")
    return head, tree


def _run(arguments: list[str]) -> int:
    if (
        not sys.flags.isolated
        or not sys.flags.no_site
        or not sys.dont_write_bytecode
    ):
        _fail("bootstrap_unavailable")
    wrapper = Path(os.path.abspath(__file__))
    _reject_chain(wrapper, code="bootstrap_host_mismatch")
    host_root_text = _git(
        wrapper.parent,
        "rev-parse",
        "--show-toplevel",
        code="bootstrap_host_mismatch",
    )
    try:
        host_root = Path(str(host_root_text)).resolve(strict=True)
    except OSError:
        _fail("bootstrap_host_mismatch")
    expected_wrapper = _under(host_root, WRAPPER_PATH)
    if wrapper != expected_wrapper:
        _fail("bootstrap_host_mismatch")
    head_tree = _clean_host(host_root)
    wrapper_blob = bytes(
        _git(
            host_root,
            "cat-file",
            "blob",
            f"{head_tree[0]}:{WRAPPER_PATH}",
            binary=True,
            code="bootstrap_host_mismatch",
        )
    )
    if wrapper.read_bytes() != wrapper_blob:
        _fail("bootstrap_host_mismatch")

    object_repository = _under(host_root, OBJECT_REPOSITORY, directory=True)
    materialized_root = _under(host_root, MATERIALIZED_ROOT, directory=True)
    if (
        _git(
            object_repository,
            "rev-parse",
            "--show-object-format",
            code="bootstrap_materialization_mismatch",
        )
        != ATTUNE_OBJECT_FORMAT
        or _git(
            object_repository,
            "cat-file",
            "-t",
            ATTUNE_COMMIT,
            code="bootstrap_materialization_mismatch",
        )
        != "commit"
        or _git(
            object_repository,
            "rev-parse",
            f"{ATTUNE_COMMIT}^{{tree}}",
            code="bootstrap_materialization_mismatch",
        )
        != ATTUNE_TREE
    ):
        _fail("bootstrap_materialization_mismatch")
    bootstrap = _under(materialized_root, BOOTSTRAP_RELATIVE)
    pinned = bytes(
        _git(
            object_repository,
            "cat-file",
            "blob",
            f"{ATTUNE_COMMIT}:{BOOTSTRAP_RELATIVE}",
            binary=True,
            code="bootstrap_materialization_mismatch",
        )
    )
    working = bootstrap.read_bytes()
    if (
        working != pinned
        or hashlib.sha256(working).hexdigest() != BOOTSTRAP_SHA256
    ):
        _fail("bootstrap_materialization_mismatch")
    if head_tree != _clean_host(host_root) or wrapper.read_bytes() != wrapper_blob:
        _fail("bootstrap_host_mismatch")

    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-B",
                "-c",
                STDIN_EXECUTOR,
                str(bootstrap),
                "--bootstrap-host-root",
                str(host_root),
                "--bootstrap-wrapper",
                str(wrapper),
                "--",
                *arguments,
            ],
            cwd=materialized_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            input=working,
            timeout=BOOTSTRAP_TIMEOUT_SECONDS,
            check=False,
            env=_safe_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        _fail("bootstrap_unavailable")
    try:
        stdout = completed.stdout.decode("utf-8")
        stderr = completed.stderr.decode("utf-8")
    except UnicodeError:
        _fail("bootstrap_unavailable")
    if stdout:
        sys.stdout.write(stdout)
    if stderr:
        sys.stderr.write(stderr)
    return completed.returncode


def main() -> int:
    try:
        return _run(sys.argv[1:])
    except BootstrapError as exc:
        payload = {
            "code": exc.code,
            "message": SAFE_MESSAGES.get(
                exc.code,
                SAFE_MESSAGES["bootstrap_unavailable"],
            ),
        }
        print(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1
    except Exception:
        payload = {
            "code": "bootstrap_unavailable",
            "message": SAFE_MESSAGES["bootstrap_unavailable"],
        }
        print(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
