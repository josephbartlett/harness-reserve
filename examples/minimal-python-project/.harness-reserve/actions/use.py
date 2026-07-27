from __future__ import annotations

from datetime import datetime, timezone
import subprocess
import sys

from common import project_root, write_result

root = project_root()
completed = subprocess.run([sys.executable, str(root / "app.py")], check=False)
state_root = root / ".harness-reserve" / "state"
state_root.mkdir(parents=True, exist_ok=True)
marker = state_root / "example-app-opened.txt"
marker.write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")
passed = completed.returncode == 0
write_result(
    outcome="PASS" if passed else "ERROR",
    summary="The example app ran and local derived evidence was recorded." if passed else "The example app failed.",
    project_state="READY" if passed else "BLOCKED",
    evidence=[
        {
            "kind": "derived-marker",
            "label": "Example app invocation marker",
            "path": ".harness-reserve/state/example-app-opened.txt",
            "safe_to_share": True,
        }
    ],
    next_action="process" if passed else "verify",
)
raise SystemExit(0 if passed else 1)
