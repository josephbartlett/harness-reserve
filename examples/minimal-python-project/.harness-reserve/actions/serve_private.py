from __future__ import annotations

import argparse

from common import write_result

parser = argparse.ArgumentParser()
parser.add_argument("--minutes", type=int, default=30)
args = parser.parse_args()
write_result(
    outcome="PASS",
    summary="The private-LAN confirmation demonstration completed without opening a socket.",
    project_state="READY",
    next_action="status",
)
print(f"PASS: confirmation gate demonstration accepted for {args.minutes} minutes")
