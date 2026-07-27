from __future__ import annotations

from common import project_root, write_result

root = project_root()
required = [
    root / "app.py",
    root / ".harness-reserve" / "operator.json",
]
missing = [path.name for path in required if not path.is_file()]
passed = not missing
write_result(
    outcome="PASS" if passed else "BLOCK",
    summary="The example verification gate passed." if passed else "Required example files are missing.",
    project_state="READY" if passed else "BLOCKED",
    warnings=["Missing: " + ", ".join(missing)] if missing else [],
    next_action="use" if passed else "Restore required files",
)
print("PASS: example verification passed" if passed else "BLOCK: example verification failed")
raise SystemExit(0 if passed else 20)
