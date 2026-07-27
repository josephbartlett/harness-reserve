from __future__ import annotations

import argparse
import subprocess
import sys

from common import project_root, write_result

parser = argparse.ArgumentParser()
parser.add_argument("--item", required=True)
parser.add_argument("--open-after", action="store_true")
args = parser.parse_args()
root = project_root()
output = root / ".harness-reserve" / "state" / "processed-items.txt"
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("a", encoding="utf-8") as handle:
    handle.write(args.item + "\n")
if args.open_after:
    completed = subprocess.run([sys.executable, str(root / "app.py")], check=False)
    if completed.returncode != 0:
        write_result(
            outcome="ERROR",
            summary="The bounded item was recorded, but the requested app launch failed.",
            project_state="DEGRADED",
            warnings=["The example app returned a nonzero exit code."],
            next_action="verify",
        )
        raise SystemExit(completed.returncode or 1)
write_result(
    outcome="PASS",
    summary="One bounded example item was processed into ignored derived state.",
    project_state="READY",
    evidence=[
        {
            "kind": "derived-log",
            "label": "Processed item ledger",
            "path": ".harness-reserve/state/processed-items.txt",
            "safe_to_share": True,
        }
    ],
    next_action="status",
)
print(f"PASS: processed {args.item}")
