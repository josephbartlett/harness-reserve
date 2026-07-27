from __future__ import annotations

from common import project_root, write_result

root = project_root()
ready = (root / "app.py").is_file()
write_result(
    outcome="PASS" if ready else "BLOCK",
    summary="The example app and operator adapter are present." if ready else "The example app is missing.",
    project_state="READY" if ready else "BLOCKED",
    next_action="use" if ready else "Restore app.py",
)
print("PASS: example status is ready" if ready else "BLOCK: app.py is missing")
raise SystemExit(0 if ready else 20)
