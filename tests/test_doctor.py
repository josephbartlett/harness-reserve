from __future__ import annotations

import shutil
import subprocess
import unittest

from harness_reserve.doctor import run_doctor

from support import copied_example, load_example


@unittest.skipUnless(shutil.which("git"), "Git is required for ignore diagnostics")
class DoctorTests(unittest.TestCase):
    def test_directory_ignore_rules_are_checked_with_future_child_paths(self) -> None:
        with copied_example() as root:
            subprocess.run(
                ["git", "-C", str(root), "init", "-q"],
                check=True,
                capture_output=True,
                text=True,
            )
            report = run_doctor(load_example(root))
            self.assertTrue(report["state"]["ignored_by_git"])
            self.assertTrue(report["state"]["candidates_ignored_by_git"])
            self.assertTrue(report["ok"])

            (root / ".gitignore").write_text("", encoding="utf-8")
            report = run_doctor(load_example(root))
            self.assertFalse(report["state"]["ignored_by_git"])
            self.assertFalse(report["state"]["candidates_ignored_by_git"])
            self.assertFalse(report["ok"])


if __name__ == "__main__":
    unittest.main()
