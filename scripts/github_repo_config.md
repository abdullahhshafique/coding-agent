# GitHub repo polish — apply when taking the repo public

These are the exact values to set on the GitHub repo once it's made public
(Phases.md: repo goes public only in Phase 4, gated on Phase 3 metrics existing).

## Settings → General
- **Description (tagline):**
  > Autonomous CLI agent that turns a natural-language GitHub bug report into a reviewable unified-diff patch — identifier-aware code search, AST-structured context, budget-capped agent loop, loud-failure path, and a measured evaluation scorecard. (Portfolio project)

- **Website:** leave blank
- **Topics (suggested, paste into the Topics box):**
  `llm` · `ai-agent` · `github-api` · `ast` · `code-search` ·
  `patch-generation` · `cli` · `python` · `groq` · `prompt-engineering` ·
  `portfolio` · `agentic-coding`

## Steps to take it public (when ready)
1. `git remote add origin git@github.com:abdullahhshafique/coding-agent.git`
2. Create the repo on GitHub (public), no template files (we have README/LICENSE/.gitignore).
3. `git push -u origin master`  (or `main` after renaming branch)
4. In repo **Settings → General**, set the description + topics above.
5. Verify README renders + LICENSE shows the MIT banner.

Note: branch is currently `master`; if your GitHub default is `main`, run
`git branch -M main` before push so the default branch shows the README.
