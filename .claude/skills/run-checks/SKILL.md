---
name: run-checks
description: Runs every ragConsumer check in one command — backend pytest (with the venv correctly activated), frontend tsc, Vitest and oxlint, and optionally the running Docker stack's health — then prints a PASS/FAIL summary. Use after any code change, before marking a Jira ticket Done, before committing, after a rebase or merge, or whenever asked to "run the tests" or "check everything works".
---

# Run checks

## When to use
- After changing backend or frontend code, or after a rebase or merge.
- Before a Jira ticket moves to Done.
- When the user asks whether everything still works.

## Inputs
- None. Add `--stack` when the Docker stack should be running and reachable, for example after `docker compose up`.

## Steps
Run from any directory:

```bash
bash /c/Users/zazuk/MLH/ragConsumer/.claude/skills/run-checks/run-checks.sh
bash /c/Users/zazuk/MLH/ragConsumer/.claude/skills/run-checks/run-checks.sh --stack
PYTEST_ARGS="-k collections" bash /c/Users/zazuk/MLH/ragConsumer/.claude/skills/run-checks/run-checks.sh
```

- `--stack` also checks the running Docker stack.
- `PYTEST_ARGS` runs only a subset of the backend tests.

The script finds the repo root from its own location, so the working directory doesn't matter.

## How to tell it worked
- The output ends with a `SUMMARY` block listing each check, then `ALL CHECKS PASSED`, and the exit code is 0.
- Any failure prints `FAIL (...)`, ends with `SOME CHECKS FAILED`, and exits 1. The tail of each check's output is printed above the summary, so read it to see what failed.
- Report the summary to the user as-is. Never describe a FAIL as a pass.

## Known gotchas (why this skill exists)
- **Each Bash call is a fresh shell.** Running pytest without activating `backend/.venv` in the *same* command uses the global Python, and fails with misleading import errors (e.g. "email-validator is not installed"). The script handles this. Don't run pytest by hand without it.
- oxlint warnings (e.g. `only-export-components` in shadcn files) don't fail the check. Only errors do.
- `npm notice` lines are noise. The script filters them.
- If `--stack` fails for the frontend while the backend passes, check for a leftover local `npm run dev` on port 5173 shadowing the Docker frontend. Look for `node.exe` processes.
