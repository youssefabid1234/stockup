---
description: Team 12 hourly sync — freeze, status, explain, push, merge, read the others
---

Run the team sync ritual of AGENTS.md "Team 12" rule 5, step by step, in short lines (French, simple words):

1. Show the current branch and `git status`. If on `main`, stop and ask which branch to use.
2. Run the AI tests: `cd apps/ai && uv run --group dev pytest -q` (Windows: uv may need its full path, see
   docs/team/setup-windows.md). If red: say what fails and ask whether to fix, put it behind its switch, or stop.
3. Update `docs/team/status/<first-name>.md` (ask the name if unknown) from docs/team/status/README.md's template.
4. Explain in plain words what changed since the last sync and what could break. List the files touched; warn if any
   is outside my files (my task sheet). **Wait for my OK**, then commit and push the branch, open or update the PR to
   `main` (`gh pr create` / `gh pr view`).
5. If the tests are green and I agree, merge the PR into `main`.
6. `git fetch --all && git merge origin/main` into my branch (ask before resolving conflicts outside my files).
7. Read every `docs/team/status/*.md` and the new commits on `origin/main`; tell me in ≤ 10 lines what the others did,
   what affects my work, and anything someone waits on from me.
