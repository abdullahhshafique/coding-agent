"""CLI entry point for the coding agent."""

from __future__ import annotations

import argparse
import sys

from coding_agent.models import RunRequest
from coding_agent.orchestrator import AgentOrchestrator


def main() -> int:
    """Parse arguments and invoke the agent orchestrator."""
    parser = argparse.ArgumentParser(
        prog="coding-agent",
        description="AI coding agent for GitHub repos.",
    )
    subparsers = parser.add_subparsers(dest="command")

    fix_parser = subparsers.add_parser("fix", help="Generate a patch for an issue")
    fix_parser.add_argument(
        "--repo",
        default=None,
        help="Repository identifier, e.g. owner/name or GitHub URL",
    )
    fix_parser.add_argument(
        "--issue",
        default=None,
        help="Bug description as raw text",
    )
    fix_parser.add_argument(
        "--issue-url",
        default=None,
        help="GitHub issue URL to fetch description from",
    )
    fix_parser.add_argument(
        "--budget",
        type=int,
        default=20,
        help="Maximum tool calls per run (default: 20)",
    )

    args = parser.parse_args()

    if args.command != "fix":
        parser.print_help()
        return 1

    if not args.repo:
        print("Error: --repo is required.", file=sys.stderr)
        fix_parser.print_help()
        return 1

    if not args.issue and not args.issue_url:
        print(
            "Error: either --issue or --issue-url must be provided.",
            file=sys.stderr,
        )
        return 1

    request = RunRequest(
        repo=args.repo,
        issue_text=args.issue,
        issue_url=args.issue_url,
        tool_call_budget=args.budget,
    )

    orchestrator = AgentOrchestrator()
    result = orchestrator.run(request)

    return 0 if result.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
