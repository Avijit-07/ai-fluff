---
name: standard-assess
description: Assess a Java service repo against the fleet standard (STANDARDS.MD) and write assessment.json. Use when asked to assess, audit or check conformance of a repo against the standard, or to plan a migration wave. Read-only; it never changes the repo.
---

# Standard assessment (phase 1)

You produce one `assessment.json` for one repo. A script does the checking.
You only add judgement where the script cannot.

## Inputs

- The repo to assess (current directory unless the user names another path).
- `STANDARDS.MD` (or `STANDARD.resolved.md` if the orchestrator produced one).
  Read it before step 3.

## Steps

1. **Run the script.** From the repo root:

   ```bash
   python3 <skill-dir>/scripts/check_conformance.py . --out assessment.json
   ```

   Exit code 1 only means some MUST rule failed. That is a normal result,
   not an error. Exit code 2 means bad input: stop and report.

2. **Do not change script results.** Every entry with `"source": "script"`
   is final. Do not edit its `status` or `evidence`, even if you disagree.
   If you think the script is wrong, say so in your summary instead.

3. **Assess the `unchecked` rules.** For each result with
   `"status": "unchecked"`, look at the code and decide `pass`, `fail` or
   `not_applicable`. Replace the entry with:

   ```json
   { "rule": "OBS-03", "level": "MUST", "fix": "agent",
     "status": "fail", "source": "agent",
     "evidence": "<file:line or what you looked at>" }
   ```

   If you cannot tell, leave it `unchecked` and say why in `evidence`.
   Update `summary` counts to match.

4. **Fill `effort` and `risks`.**
   - `effort`: `low` (only `auto` fixes), `medium` (some `agent` fixes),
     `high` (any `human` fix, or build does not pass today).
   - `risks`: short facts a reviewer needs, such as low test coverage,
     custom security code, or a large module count.

5. **Report.** Print a short table: failed MUST rules, who fixes them
   (`auto` / `agent` / `human`), and the effort. Point to `assessment.json`.

## Rules

- Do not modify any file in the repo except `assessment.json`.
- Do not run builds that deploy or publish anything. `mvn -q -DskipTests compile`
  is fine if you need to check whether the build passes today.
- Do not guess. Every `agent` result needs evidence a human can verify.
