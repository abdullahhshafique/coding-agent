"""Build the Phase 3 curated test set from real CLOSED GitHub issues.

Approach: take recent closed (non-PR) bug issues from active repos, then
resolve ground-truth fix files by matching merged pull requests that
reference the issue (GitHub timeline + PR file lists). A case is emitted only
when a merged PR fixing the issue yields at least one source file, so every
entry is verifiable ground truth, not a guess.

Note on rate limits: the issues search and PR-file fetches are REST calls
(higher budget than code search); we pace calls and stop early at the target.
"""

from __future__ import annotations

import json
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(__file__))
from _env import load_env  # noqa: E402

load_env()
TOKEN = os.environ.get("GITHUB_TOKEN", "")
HEADERS = {
    "Accept": "application/vnd.github+json",
    **({"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}),
}
BASE = "https://api.github.com"
TARGET = 16
SOURCE_EXT = (".py", ".pyi", ".js", ".ts")

# Active repos with a long history of small, fixable, well-labelled bugs.
REPOS = [
    "encode/httpx",
    "pallets/click",
    "pallets/jinja",
    "pallets/werkzeug",
    "psf/requests",
    "giampaolo/psutil",
    "dateutil/dateutil",
]


def get(url: str, params: dict | None = None) -> requests.Response:
    resp = requests.get(url, headers=HEADERS, params=params, timeout=20)
    if resp.status_code == 403 and "rate limit" in resp.text.lower():
        raise RuntimeError("rate-limited; wait and re-run")
    return resp


def recent_closed_bugs(repo: str, n: int = 8) -> list[dict]:
    q = f"repo:{repo} is:issue is:closed label:bug"
    resp = get(f"{BASE}/search/issues", {"q": q, "sort": "updated",
                                          "order": "desc", "per_page": n})
    if resp.status_code != 200:
        return []
    return resp.json().get("items", [])


def merged_fix_files(repo: str, number: int) -> list[str]:  # noqa: C901
    """Find merged PR files that close this issue, via the issue timeline."""
    resp = get(f"{BASE}/repos/{repo}/issues/{number}/timeline",
               params={"per_page": 100})
    if resp.status_code != 200:
        return []
    files: list[str] = []
    for event in resp.json():
        if event.get("event") != "cross-referenced":
            continue
        src = event.get("source", {}).get("issue", {})
        pr = src.get("pull_request")
        if not pr:
            continue
        pr_url = pr.get("url")
        try:
            pr_data = get(pr_url).json()
        except Exception:
            continue
        if not pr_data.get("merged_at"):
            continue  # only merged fixes count as ground truth
        fresp = get(f"{pr_url}/files", params={"per_page": 50})
        if fresp.status_code != 200:
            continue
        for f in fresp.json():
            fn = f.get("filename", "")
            if fn.endswith(SOURCE_EXT) and "test" not in fn.lower():
                files.append(fn)
        if files:
            break
        time.sleep(0.5)
    return files[:5]


def main() -> None:
    seen_issues: set[str] = set()
    cases: list[dict] = []
    for repo in REPOS:
        if len(cases) >= TARGET:
            break
        for issue in recent_closed_bugs(repo):
            if len(cases) >= TARGET:
                break
            num = issue["number"]
            key = f"{repo}#{num}"
            if key in seen_issues or "pull_request" in issue:
                continue
            seen_issues.add(key)
            body = (issue.get("body") or "").strip()
            if len(body) < 80:  # too thin to be a real bug report
                continue
            files = merged_fix_files(repo, num)
            if not files:
                continue
            title = issue.get("title", "")
            cases.append({
                "repo": repo,
                "issue_number": num,
                "issue_url": f"https://github.com/{repo}/issues/{num}",
                "issue_title": title,
                "issue_body": body[:3000],
                "expected_files": files,
                "description": f"Patch should address: {title[:120]}",
            })
            print(f"OK  {key}  ({len(files)} files)  {title[:60]}", flush=True)
            time.sleep(1.0)  # pace timeline/PR calls
    with open("test_set.json", "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)
    print(f"\nWrote {len(cases)} cases to test_set.json")


if __name__ == "__main__":
    main()
