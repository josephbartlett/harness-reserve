from __future__ import annotations

import json
import unittest

from harness_reserve.handoff import build_handoff
from harness_reserve.runner import execute_action

from support import copied_example, load_example, read_manifest, write_manifest


class HandoffTests(unittest.TestCase):
    def test_handoff_uses_only_aggregate_receipt(self) -> None:
        with copied_example() as root:
            action_path = (
                root / ".harness-reserve" / "actions" / "private_stdout.py"
            )
            action_path.write_text(
                "\n".join(
                    [
                        "import json, os",
                        "from pathlib import Path",
                        "print('PRIVATE-STDOUT-MARKER')",
                        "payload = {'contract_version': 1, 'outcome': 'PASS', 'safe_summary': 'Aggregate-only result.', 'project_state': 'READY', 'warnings': [], 'evidence': [], 'next_action': 'status'}",
                        "Path(os.environ['HARNESS_RESERVE_RESULT_PATH']).write_text(json.dumps(payload) + '\\n', encoding='utf-8')",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            value = read_manifest(root)
            value["actions"]["private-stdout"] = {
                "description": "Print a private synthetic marker.",
                "runner": "python",
                "entrypoint": ".harness-reserve/actions/private_stdout.py",
                "working_directory": ".",
                "fixed_args": [],
                "parameters": {},
                "environment": {},
                "timeout_seconds": 60,
                "authority": {
                    "filesystem": "read-only",
                    "network": "none",
                    "git": "none",
                    "external_systems": "none",
                    "secrets": "none",
                    "semantic_authority": "none",
                },
                "confirmation": {"mode": "none", "prompt": "Synthetic test."},
                "model_invocable": False,
            }
            write_manifest(root, value)
            manifest = load_example(root)
            result = execute_action(manifest, "private-stdout", {})
            self.assertIn("PRIVATE-STDOUT-MARKER", result.stdout)
            self.assertNotIn("PRIVATE-STDOUT-MARKER", json.dumps(result.receipt))
            packet, json_path, md_path = build_handoff(manifest)
            serialized = json.dumps(packet) + json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE-STDOUT-MARKER", serialized)
            self.assertNotIn(str(root), serialized)
            self.assertNotIn("root", packet["project"])
            self.assertIn("private-stdout", serialized)
            self.assertIn("grants no authority", serialized)


if __name__ == "__main__":
    unittest.main()
