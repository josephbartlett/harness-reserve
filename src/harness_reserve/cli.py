from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from .constants import RUNTIME_VERSION
from .discovery import discover_project
from .doctor import run_doctor
from .errors import ReserveError
from .handoff import build_handoff
from .init_project import initialize_adapter
from .intent import dispatch_intent
from .local_model import propose_intent
from .manifest import LoadedManifest, load_manifest
from .receipts import load_latest
from .runner import ExecutionResult, execute_action
from .util import parse_json_argument

_OUTCOME_EXIT = {"PASS": 0, "DEGRADED": 10, "BLOCK": 20, "ERROR": 1}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness-reserve",
        description="Deterministic local operator for manifest-driven project actions.",
    )
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--version", action="version", version=RUNTIME_VERSION)
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List declared project actions.")
    sub.add_parser("validate", help="Validate the project manifest and referenced paths.")
    sub.add_parser("doctor", help="Inspect runtime, runner, Git, and ignore readiness.")

    describe = sub.add_parser("describe", help="Describe one declared action.")
    describe.add_argument("action")

    run = sub.add_parser("run", help="Run one declared action, or the project default.")
    run.add_argument("action", nargs="?")
    run.add_argument("--params-json")
    run.add_argument("--confirm", action="store_true")
    run.add_argument("--confirmation-text")
    run.add_argument("--dry-run", action="store_true")

    handoff = sub.add_parser("handoff", help="Write a safe aggregate continuation packet.")
    handoff.add_argument("--print-packet", action="store_true")

    sub.add_parser("latest", help="Show the latest aggregate run receipt.")

    intent = sub.add_parser(
        "dispatch-intent",
        help="Validate a local-model action intent; dry-run unless --execute is supplied.",
    )
    intent.add_argument("intent_file", type=Path)
    intent.add_argument("--execute", action="store_true")
    intent.add_argument("--confirm", action="store_true")
    intent.add_argument("--confirmation-text")

    proposal = sub.add_parser(
        "propose-intent",
        help=(
            "Ask the fixed loopback gpt-oss model for one validated action "
            "proposal; never execute it."
        ),
    )
    proposal.add_argument("--request", required=True)
    proposal.add_argument("--timeout-seconds", type=int, default=300)

    init = sub.add_parser("init", help="Create a fail-closed adapter in an existing project.")
    init.add_argument("--target", type=Path, required=True)
    init.add_argument("--project-id", required=True)
    init.add_argument("--display-name", required=True)

    return parser


def _emit_json(value: Any, *, stream: Any | None = None) -> None:
    print(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        ),
        file=sys.stdout if stream is None else stream,
    )


def _load(args: argparse.Namespace) -> LoadedManifest:
    root, manifest_path = discover_project(
        project_root=args.project_root,
        manifest_path=args.manifest,
    )
    return load_manifest(root, manifest_path)


def _print_dry_run_plan(plan: dict[str, Any]) -> None:
    print(f"Action: {plan.get('action')}")
    print(f"Runner: {plan.get('runner')}")
    print(f"Entrypoint: {plan.get('entrypoint')}")
    print(f"Working directory: {plan.get('working_directory')}")
    print(
        "Parameters: "
        + json.dumps(
            plan.get("parameters", {}),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
    )
    print("Authority:")
    for key, value in plan.get("authority", {}).items():
        print(f"  {key}: {value}")


def _print_execution(result: ExecutionResult, *, as_json: bool) -> int:
    if as_json:
        _emit_json(result.receipt)
    else:
        if result.stdout:
            print(
                result.stdout,
                end="" if result.stdout.endswith("\n") else "\n",
                file=sys.stdout,
            )
        if result.stderr:
            print(
                result.stderr,
                end="" if result.stderr.endswith("\n") else "\n",
                file=sys.stderr,
            )
        execution = result.receipt.get("execution")
        if execution:
            print(
                f"Harness Reserve: {execution.get('outcome')} "
                f"({result.receipt.get('invocation', {}).get('action')})"
            )
            if result.receipt_path:
                print(f"Receipt: {result.receipt_path}")
        elif result.receipt.get("dry_run"):
            print("Harness Reserve dry run")
            _print_dry_run_plan(result.receipt)
            print("No process was executed.")
    if result.receipt.get("dry_run"):
        return 0
    outcome = result.receipt.get("execution", {}).get("outcome", "ERROR")
    return _OUTCOME_EXIT.get(outcome, 1)


def _human_list(manifest: LoadedManifest) -> None:
    print(f"{manifest.display_name} ({manifest.project_id})")
    print(f"Default action: {manifest.default_action}")
    for action_id, action in sorted(manifest.actions.items()):
        default = " [default]" if action_id == manifest.default_action else ""
        model = " model" if action.get("model_invocable") else " human-only"
        print(f"  {action_id}{default} - {action['description']} ({model})")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 2
    try:
        if args.command == "init":
            result = initialize_adapter(
                args.target,
                project_id=args.project_id,
                display_name=args.display_name,
            )
            if args.as_json:
                _emit_json(result)
            else:
                print(f"Created Harness Reserve adapter in {result['project_root']}")
                for item in result["created"]:
                    print(f"  + {item}")
                print("Next steps:")
                for item in result["next_steps"]:
                    print(f"  - {item}")
            return 0

        manifest = _load(args)

        if args.command == "list":
            if args.as_json:
                _emit_json(
                    {
                        "project": manifest.project,
                        "default_action": manifest.default_action,
                        "actions": manifest.actions,
                    }
                )
            else:
                _human_list(manifest)
            return 0

        if args.command == "validate":
            value = {
                "valid": True,
                "project_id": manifest.project_id,
                "manifest": str(manifest.manifest_path),
                "action_count": len(manifest.actions),
            }
            if args.as_json:
                _emit_json(value)
            else:
                print(
                    f"PASS: {manifest.manifest_path} declares {len(manifest.actions)} valid actions."
                )
            return 0

        if args.command == "doctor":
            report = run_doctor(manifest)
            if args.as_json:
                _emit_json(report)
            else:
                print(f"Project: {manifest.display_name} ({manifest.project_id})")
                print(f"Platform: {report['current_platform']}")
                print(f"Python: {report['python']['version']}")
                for action_id, info in report["runners"].items():
                    status = "PASS" if info["available"] else "BLOCK"
                    print(f"{status}: {action_id} -> {info['runner']} ({info['detail']})")
                for warning in report["warnings"]:
                    print(f"WARN: {warning}")
                ignored = report["state"]["ignored_by_git"]
                candidates_ignored = report["state"]["candidates_ignored_by_git"]
                print(
                    "State ignored by Git: "
                    + (
                        "yes"
                        if ignored is True
                        else "no"
                        if ignored is False
                        else "unknown"
                    )
                )
                print(
                    "Candidates ignored by Git: "
                    + (
                        "yes"
                        if candidates_ignored is True
                        else "no"
                        if candidates_ignored is False
                        else "unknown"
                    )
                )
            return 0 if report["ok"] else 20

        if args.command == "describe":
            action = manifest.action(args.action)
            value = {"action": args.action, **action}
            if args.as_json:
                _emit_json(value)
            else:
                print(f"Action: {args.action}")
                print(f"Description: {action['description']}")
                print(f"Runner: {action['runner']}")
                print(f"Entrypoint: {action['entrypoint']}")
                print(f"Model invocable: {action['model_invocable']}")
                print("Authority:")
                for key, val in action["authority"].items():
                    print(f"  {key}: {val}")
            return 0

        if args.command == "run":
            parameters = parse_json_argument(args.params_json)
            result = execute_action(
                manifest,
                args.action,
                parameters,
                confirmed=args.confirm,
                confirmation_text=args.confirmation_text,
                invoked_by="human",
                dry_run=args.dry_run,
            )
            return _print_execution(result, as_json=args.as_json)

        if args.command == "dispatch-intent":
            result = dispatch_intent(
                args.intent_file.expanduser().resolve(),
                manifest,
                execute=args.execute,
                confirmed=args.confirm,
                confirmation_text=args.confirmation_text,
            )
            return _print_execution(result, as_json=args.as_json)

        if args.command == "propose-intent":
            result = propose_intent(
                manifest,
                request=args.request,
                timeout_seconds=args.timeout_seconds,
            )
            if args.as_json:
                _emit_json(result.plan)
            else:
                print("Harness Reserve local-model proposal (dry run)")
                _print_dry_run_plan(result.plan)
                print(f"Intent: {result.intent_path}")
                print("No action was executed and no run receipt was created.")
            return 0

        if args.command == "latest":
            latest = load_latest(manifest)
            if args.as_json:
                _emit_json(latest)
            else:
                receipt = latest["receipt"]
                print(f"Run: {latest['run_id']}")
                print(f"Action: {receipt['invocation']['action']}")
                print(f"Outcome: {receipt['execution']['outcome']}")
                print(f"Project state: {receipt['result']['project_state']}")
                print(f"Receipt: {latest['receipt_path']}")
            return 0

        if args.command == "handoff":
            packet, json_path, md_path = build_handoff(manifest)
            if args.as_json or args.print_packet:
                _emit_json(packet)
            else:
                print(f"PASS: Wrote handoff JSON: {json_path}")
                print(f"PASS: Wrote handoff Markdown: {md_path}")
            return 0

        parser.error(f"Unhandled command: {args.command}")
        return 2
    except ReserveError as exc:
        if getattr(args, "as_json", False):
            _emit_json({"outcome": "BLOCK", "error": str(exc)})
        else:
            print(str(exc), file=sys.stderr)
        return getattr(exc, "exit_code", 20)
    except (ValueError, OSError) as exc:
        if getattr(args, "as_json", False):
            _emit_json({"outcome": "ERROR", "error": str(exc)})
        else:
            print(f"ERROR: {exc}", file=sys.stderr)
        return 1
