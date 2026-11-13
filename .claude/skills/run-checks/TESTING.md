# Test log

## 2026-11-12 — PASS
- **Why this skill:** the full check suite was run by hand 8+ times during KAN-44/45/58/59. The venv-activation gotcha caused two real failures: an `email-validator` ImportError from the global Python, and a `pip install` that landed in the global Python.
- **Test case:** the real repo at commit `352acc8` (`main`), with the stack started via `docker compose up -d`.
- **Expected** (written before running): all 4 code checks PASS. With `--stack`, all 3 stack checks PASS. Exit 0. It works when invoked from an unrelated working directory (`/c/Users/zazuk`).
- **Run by:** the main session, following `SKILL.md` literally (it is one script invocation).
- **Result:**
  1. **First run:** the stack checks reported `FAIL (HTTP 000)` with exit 1. The stack was genuinely down (`docker ps` was empty), so this was a correct failure report.
  2. **After `docker compose up -d`:** 7/7 PASS (`23 passed` in pytest, `16 passed` in Vitest), `ALL CHECKS PASSED`, exit 0.
- **Failure paths checked:**
  - Stack down: all three stack checks `FAIL (HTTP 000)`, exit 1. Correct.
  - Backend tests: `PYTEST_ARGS="-k nonexistent_test_xyz"` gave `backend pytest FAIL (exit 5)`, `SOME CHECKS FAILED`, exit 1. Correct.
