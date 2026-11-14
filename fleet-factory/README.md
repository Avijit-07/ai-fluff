# fleet-factory

Tooling to bring many Java service repos to the standard in
[`STANDARDS.MD`](../STANDARDS.MD), and keep them there.

The pattern everywhere: **a script decides, the agent fills gaps, a human approves.**

| Layer | What | Trust |
|---|---|---|
| Script | Deterministic checks and fixes (Python, OpenRewrite / Moderne recipes) | Same result every run. CI can gate on it. |
| Skill | `SKILL.md` that tells Claude when to run the script and what to do with the gaps | Judgement, always with evidence |
| Human | Reviews PRs, owns `human` rules | Final say |

## Phase 1: assessment (this folder)

Read-only. For one repo, produce `assessment.json` (shape in STANDARDS.MD §13).

```
skills/standard-assess/
  SKILL.md                      # instructions for Claude
  scripts/check_conformance.py  # the checks; stdlib Python, no AI
examples/legacy-service/        # a deliberately non-conforming repo to try it on
```

Run the script alone (no Claude needed):

```bash
python3 skills/standard-assess/scripts/check_conformance.py examples/legacy-service --out /tmp/assessment.json
```

On the example it reports 9 MUST failures, 1 valid exception, and 10 rules it
cannot check from files. Those 10 are what the skill asks Claude to assess.

Use it as a skill: copy `skills/standard-assess` to `.claude/skills/` in a repo
(or `~/.claude/skills/`), then ask Claude "assess this repo against the standard".

Fleet-wide: loop the script over every repo (or run it in each repo's CI) and
merge the JSON files into one table. That table decides migration waves.

## Later phases

| Phase | Adds | Writes code? |
|---|---|---|
| 1 Assess | `standard-assess` | No |
| 2 Migrate | `standard-migrate` skill: run `auto` fixes (recipes/template sync), then let the agent do `agent` rules, open a PR | Yes, PR only |
| 3 Keep current | `library-upgrade` skill + event trigger (see below) | Yes, PR only |

## Where Moderne fits

Moderne runs OpenRewrite recipes across many repos and tracks the campaign.
It is the best tool for the deterministic part. It does not read release notes
or fix the leftover compile and test failures. That is the skill's job.

So per repo the order is always: **recipe first, agent second, checks last.**

The Moderne UI is manual, which is fine for one-off campaigns (phase 2). For
"new major of library X → PR in every repo" (phase 3), do not drive it from
the UI. Use an event trigger instead. See
[`examples/workflows/on-major-upgrade.yml`](examples/workflows/on-major-upgrade.yml):
Renovate detects the release and opens the PR, a workflow runs the recipe and
then Claude on that branch, and the PR is labelled for a human.

The recipe step can be the OpenRewrite Maven plugin in the workflow, or a call
to Moderne's CLI / API if you want Moderne to stay the system of record.
