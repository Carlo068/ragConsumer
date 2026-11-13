---
name: skill-builder
description: Turns a repetitive workflow into a tested, reusable Claude Code skill for this project. Use when the same multi-step task has been done 3+ times (or 2+ times if it is long or error-prone), when a workflow keeps hitting the same gotcha, or when the user says a task is repetitive or asks to "make this a skill". Never installs a skill that has not passed a recorded test.
---

# Skill builder

Turns a workflow that keeps repeating into a skill under `ragConsumer/.claude/skills/`. The non-negotiable rule: **a skill is only installed after it has been tested against a real case and passed.** An untested skill is worse than none, because future sessions will trust it.

## 1. Decide whether it's worth a skill

Create a skill only if **all** of these hold:
- **It's been repeated:** done 3+ times, or 2+ times if it's long, fiddly, or has already caused a mistake. Name the actual occurrences — when, and what was done.
- **The steps are stable.** If they're still changing each time, wait.
- **It isn't already covered.** List `.claude/skills/*/SKILL.md`. If an existing skill covers this, **update and re-test that skill** instead of adding a new one.
- **It's procedural.** It isn't a one-line fact. Facts go in `CLAUDE.md`, not a skill.

Tell the user in one line that you're building a skill, and for what. Don't wait for an answer unless the skill would perform outward or irreversible actions (see step 5).

## 2. Draft it in staging, not in the live folder

Write the draft to `ragConsumer/.claude/skills-staging/<skill-name>/SKILL.md`. Skills there are not loaded, so a broken draft can't affect anything.

```markdown
---
name: <kebab-case-name>
description: <what it does AND when to use it — concrete trigger phrases and situations. This line is all Claude sees when deciding whether to load the skill, so make it specific.>
---

# <Title>

## When to use
## Inputs (what you need before starting)
## Steps (exact commands, in order, with the directory each runs in)
## How to tell it worked (expected output)
## Known gotchas (the mistakes that made this worth a skill)
```

Rules for the content:
- **Exact commands**, copied from the runs that actually worked, not paraphrased. Include the working directory, and the venv activation in the same command, because each Bash call is a fresh shell.
- **Put every gotcha from the past occurrences into the skill.** Those are the reason it exists.
- **Keep it short.** If a step needs a long explanation, it probably belongs in a script file next to `SKILL.md`, which the skill tells you to run.
- **No secrets, and no user-specific credentials.** Point to where they live instead (e.g. "seed users are in `backend/scripts/seed.py`").

## 3. Test it, mandatory, against a real case

1. **Pick a test case.** Use a real, recent instance of the task, with a known correct outcome. Write the expected outcome down *before* running.
2. **Run the skill exactly as written**, start to finish, using only what's in the `SKILL.md`.
   - **Preferred:** give it to a fresh subagent (`qa-verifier`, or `general-purpose` if the skill edits files). Pass only the staged `SKILL.md` path and the test input. A fresh context exposes steps that silently relied on knowledge you happen to have.
   - **Otherwise:** follow it literally yourself, without filling gaps from memory. If you had to fill a gap, the test failed: fix the skill.
3. **Check the result** against the expected outcome. Confirm:
   - every command ran on this machine (Windows + Git Bash),
   - the output matched,
   - no step was ambiguous.
4. **Check one failure path if it's cheap.** For example, make sure a failing test or a down service is reported as a failure, not as success.
5. **Keep tests side-effect free.** A test must not commit, push, transition Jira tickets, deploy, delete real data, or message anyone.
   - Use dry runs, scratch data or read-only variants.
   - If the skill's whole purpose is one of those actions, test everything up to that step, and **ask the user** before running the real action for the first time.

If the test fails, fix the draft and re-run the whole test. If it can't be made to pass, delete the staged draft, and tell the user what blocked it.

## 4. Record the evidence

Add `TESTING.md` next to the staged `SKILL.md`:

```markdown
# Test log
## <YYYY-MM-DD> — <PASS|FAIL>
- Test case: <real instance used>
- Expected: <outcome written before running>
- Run by: <fresh subagent | main session, followed literally>
- Result: <what actually happened, key output lines>
- Failure path checked: <yes/no — what>
```

## 5. Install, only after PASS

- Move `skills-staging/<name>/` to `skills/<name>/`, with `SKILL.md` and `TESTING.md` together.
- If the skill performs outward or irreversible actions (git push, Jira writes, deploys, deleting data, sending messages), **ask the user before installing.** Otherwise install and report.
- **Tell the user:**
  - the skill's name and what triggers it,
  - the test result in one line,
  - the path,
  - how to remove it (delete the folder).
- Don't commit it. The user handles git.

## 6. Editing an existing skill

Any change to an installed skill goes back through steps 2–4: edit a staged copy, re-test, and append to `TESTING.md`. Replace the live copy only on PASS.
