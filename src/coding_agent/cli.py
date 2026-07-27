"""CLI entry point for the coding agent."""

from __future__ import annotations

import argparse
import sys

from coding_agent.models import RunRequest


def main() -> int:
    """Parse arguments and invoke the agent orchestrator."""
    parser = argparse.ArgumentParser(
        prog="coding-agent",
        description="AI coding agent that finds and patches bugs in GitHub repos.",
    )
    subparsers = parser.add_subparsers(dest="command")

    fix_parser = subparsers.add_parser("fix", help="Generate a patch for an issue")
    fix_parser.add_argument(
        "--repo",
        required=True,
        help="Repository identifier, e.g. owner/name or a full GitHub URL",
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

    if not args.issue and not args.issue_url:
        print("Error: either --issue or --issue-url must be provided.", file=sys.stderr)
        return 1

    request = RunRequest(
        repo=args.repo,
        issue_text=args.issue,
        issue_url=args.issue_url,
        tool_call_budget=args.budget,
    )

    print(f"Received request for repo: {request.repo}")
    print("Not yet implemented.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
