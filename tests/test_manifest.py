from __future__ import annotations

import unittest

from harness_reserve.errors import ManifestError
from harness_reserve.manifest import load_manifest, validate_parameter_values

from support import copied_example, load_example, read_manifest, write_manifest


class ManifestTests(unittest.TestCase):
    def test_reference_manifest_loads(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            self.assertEqual(manifest.project_id, "minimal-python-project")
            self.assertEqual(manifest.default_action, "use")
            self.assertIn("process", manifest.actions)

    def test_unknown_top_level_field_is_rejected(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["surprise"] = True
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_manifest(root, root / ".harness-reserve" / "operator.json")

    def test_boolean_contract_version_and_invalid_schema_hint_are_rejected(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["contract_version"] = True
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_manifest(root, root / ".harness-reserve" / "operator.json")

            value = read_manifest(root)
            value["contract_version"] = 1
            value["$schema"] = ""
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_manifest(root, root / ".harness-reserve" / "operator.json")

    def test_unknown_fields_are_rejected_at_every_manifest_layer(self) -> None:
        mutations = {
            "runtime": lambda value: value["runtime"].__setitem__("extra", True),
            "project": lambda value: value["project"].__setitem__("extra", True),
            "state": lambda value: value["state"].__setitem__("extra", True),
            "action": lambda value: value["actions"]["status"].__setitem__(
                "extra", True
            ),
            "parameter": lambda value: value["actions"]["process"]["parameters"][
                "item"
            ].__setitem__("extra", True),
            "authority": lambda value: value["actions"]["status"]["authority"].__setitem__(
                "extra", True
            ),
            "confirmation": lambda value: value["actions"]["status"][
                "confirmation"
            ].__setitem__("extra", True),
            "constraints": lambda value: value["constraints"].__setitem__(
                "extra", True
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(layer=label), copied_example() as root:
                value = read_manifest(root)
                mutate(value)
                write_manifest(root, value)
                with self.assertRaises(ManifestError):
                    load_example(root)

    def test_explicit_falsey_non_objects_are_rejected(self) -> None:
        mutations = {
            "runtime": lambda value: value.__setitem__("runtime", ""),
            "state": lambda value: value.__setitem__("state", 0),
            "authority": lambda value: value["actions"]["status"].__setitem__(
                "authority", []
            ),
            "confirmation": lambda value: value["actions"]["status"].__setitem__(
                "confirmation", False
            ),
            "constraints": lambda value: value.__setitem__("constraints", []),
            "extensions": lambda value: value.__setitem__("extensions", False),
        }
        for label, mutate in mutations.items():
            with self.subTest(layer=label), copied_example() as root:
                value = read_manifest(root)
                mutate(value)
                write_manifest(root, value)
                with self.assertRaises(ManifestError):
                    load_example(root)

    def test_explicit_null_typed_fields_and_non_ascii_version_are_rejected(
        self,
    ) -> None:
        mutations = {
            "runtime": lambda value: value.__setitem__("runtime", None),
            "state": lambda value: value.__setitem__("state", None),
            "constraints": lambda value: value.__setitem__("constraints", None),
            "confirmation": lambda value: value["actions"]["status"].__setitem__(
                "confirmation", None
            ),
            "project description": lambda value: value["project"].__setitem__(
                "description", None
            ),
            "parameter description": lambda value: value["actions"]["process"][
                "parameters"
            ]["item"].__setitem__("description", None),
            "null phrase": lambda value: value["actions"]["status"][
                "confirmation"
            ].__setitem__("phrase", None),
            "non-ascii version": lambda value: value["runtime"].__setitem__(
                "minimum_version", "٠.١.٠"
            ),
        }
        for label, mutate in mutations.items():
            with self.subTest(field=label), copied_example() as root:
                value = read_manifest(root)
                mutate(value)
                write_manifest(root, value)
                with self.assertRaises(ManifestError):
                    load_example(root)

    def test_every_action_must_declare_all_authority_dimensions(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            del value["actions"]["status"]["authority"]["network"]
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_example(root)

    def test_entrypoint_path_escape_is_rejected(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["entrypoint"] = "../outside.py"
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_manifest(root, root / ".harness-reserve" / "operator.json")

    def test_absolute_entrypoint_is_rejected(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["entrypoint"] = "/tmp/outside.py"
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_manifest(root, root / ".harness-reserve" / "operator.json")

    def test_missing_entrypoint_and_working_directory_are_rejected(self) -> None:
        for field, missing in (
            ("entrypoint", ".harness-reserve/actions/missing.py"),
            ("working_directory", "missing-directory"),
        ):
            with self.subTest(field=field), copied_example() as root:
                value = read_manifest(root)
                value["actions"]["status"][field] = missing
                write_manifest(root, value)
                with self.assertRaises(ManifestError):
                    load_example(root)

    def test_unknown_parameter_is_rejected(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            action = manifest.action("process")
            with self.assertRaises(ManifestError):
                validate_parameter_values("process", action, {"item": "ok", "shell": "bad"})

    def test_parameter_pattern_is_enforced(self) -> None:
        with copied_example() as root:
            manifest = load_example(root)
            action = manifest.action("process")
            with self.assertRaises(ManifestError):
                validate_parameter_values("process", action, {"item": "../../bad"})

    def test_required_enum_and_integer_constraints_are_enforced(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            parameters = value["actions"]["status"]["parameters"]
            parameters["required-value"] = {
                "type": "string",
                "flag": "--required-value",
                "required": True,
            }
            parameters["mode"] = {
                "type": "enum",
                "flag": "--mode",
                "values": ["safe", "strict"],
            }
            parameters["count"] = {
                "type": "integer",
                "flag": "--count",
                "minimum": 1,
                "maximum": 3,
            }
            write_manifest(root, value)
            action = load_example(root).action("status")
            with self.assertRaises(ManifestError):
                validate_parameter_values("status", action, {})
            with self.assertRaises(ManifestError):
                validate_parameter_values(
                    "status",
                    action,
                    {"required-value": "ok", "mode": "other"},
                )
            with self.assertRaises(ManifestError):
                validate_parameter_values(
                    "status",
                    action,
                    {"required-value": "ok", "count": 0},
                )
            with self.assertRaises(ManifestError):
                validate_parameter_values(
                    "status",
                    action,
                    {"required-value": "ok", "count": 4},
                )

    def test_boolean_integer_bounds_and_duplicate_flags_are_rejected(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["process"]["parameters"]["open-after"]["minimum"] = True
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_example(root)

    def test_duplicate_clean_git_action_is_rejected(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["constraints"]["require_clean_git_for"] = ["verify", "verify"]
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_example(root)

        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["process"]["parameters"]["other"] = {
                "type": "boolean",
                "flag": "--item",
            }
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_example(root)

    def test_cmd_runner_is_not_part_of_contract_v1(self) -> None:
        with copied_example() as root:
            value = read_manifest(root)
            value["actions"]["status"]["runner"] = "cmd"
            write_manifest(root, value)
            with self.assertRaises(ManifestError):
                load_manifest(root, root / ".harness-reserve" / "operator.json")


if __name__ == "__main__":
    unittest.main()
