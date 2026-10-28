# Repository Standard — <Domain Name> Services

| Field | Value |
|---|---|
| Standard version | 1.1.0 |
| Applies to | All Java services in domains: <Domain A>, <Domain B>, <Domain C> |
| Owner | <Platform / SRE team name> |
| Inherits from | `tech-standards` repo, tag `v2.3.0` (see section 0) |
| Template | <link to golden template repo>, tag `v1.1.0` |
| Conformance check | `./scripts/check-conformance.sh` (from template repo) |
| Last updated | <YYYY-MM-DD> |

> This file defines the **target state** every repo in scope must match.
> It is read by humans, by the conformance check, and by the migration agent.
> Rules use MUST / SHOULD / MAY as in RFC 2119.
>
> This is a **fleet-level** file. It lives once in the template repo, not copied
> into each service repo. Service repos only hold `AGENTS.md`,
> `standard-exceptions.yaml` and a `.standard-version` marker.

---

## 0. Inherited standards

This standard builds on the organisation's approved tech standards. Inherited
rules are referenced by ID, never copied. Their wording and intent are owned by
the tech-standards repo.

```yaml
inherits:
  - source: <host>/<org>/tech-standards
    ref: v2.3.0                     # MUST be a tag or commit, never a branch
    rules:
      - TS-LOG-01                   # Structured logging
      - TS-LOG-02                   # Log levels and PII redaction
      - TS-SEC-01..TS-SEC-04        # Dependency, image and secrets policy
      - TS-API-03                   # Health endpoint contract
    checks:                         # Machine checks published with the standards
      - policies/logging.rego
      - policies/dependencies.rego
```

**Conventions**

- Inherited rule IDs keep their `TS-` prefix. Local rules use local prefixes (`BUILD-`, `OBS-`, …).
- A local rule MAY tighten an inherited rule. It MUST NOT loosen or contradict one.
  If a conflict is found, the inherited rule wins and the local rule is fixed.
- Bumping `ref` is a standard change: it needs a new version of this file and
  a changelog entry (section 12).

**Resolve step (run by the orchestrator before every assessment or migration)**

1. Fetch `tech-standards` at the pinned `ref`.
2. Extract the listed rules and checks.
3. Write `STANDARD.resolved.md`: this file with every `TS-` reference expanded
   to its full text, plus the source ref and commit hash at the top.
4. Pass `STANDARD.resolved.md` (not this file) to the agent, and run the listed
   policy checks as part of the conformance check.
5. Fail the run if any referenced rule ID or check file cannot be found.

---

## 1. How to read this file

Each rule has:

- **ID**: stable identifier used in PR descriptions and check output (e.g. `BUILD-01`).
- **Rule**: what must be true.
- **Check**: how conformance is verified (automated where possible).
- **Fix**: who/what may fix it — `auto` (recipe or template sync), `agent` (AI may attempt), or `human` (needs an owner decision).

---

## 2. Repository layout

| ID | Rule | Check | Fix |
|---|---|---|---|
| LAYOUT-01 | Repo MUST follow the template directory structure: `src/main/java`, `src/test/java`, `src/integrationTest/java`, `config/`, `docs/`. | Script compares directory tree to template | auto |
| LAYOUT-02 | Repo MUST contain `README.md`, `CODEOWNERS`, `catalog-info.yaml`, `AGENTS.md`. | File existence check | auto (from template), owner fills content |
| LAYOUT-03 | Repo MUST NOT contain committed build outputs (`target/`, `*.jar`) or IDE files. | `.gitignore` matches template; no tracked matches | auto |
| LAYOUT-04 | Root package SHOULD be `com.<org>.<domain>.<service>`. | Static check | human (renaming packages is risky) |

## 3. Build

| ID | Rule | Check | Fix |
|---|---|---|---|
| BUILD-01 | `pom.xml` MUST inherit from `<org>-service-parent` version `X.Y.Z` or later. | Parse `<parent>` | auto (OpenRewrite) |
| BUILD-02 | Dependency versions MUST come from the parent/BOM; no explicit versions for managed dependencies. | Maven enforcer rule | auto |
| BUILD-03 | Java version MUST be 21. | Parse `maven.compiler.release` | auto, agent fixes compile errors |
| BUILD-04 | `mvn verify` MUST pass with no new warnings-as-errors. | CI build | agent |

## 4. CI/CD

| ID | Rule | Check | Fix |
|---|---|---|---|
| CI-01 | Pipeline MUST reference the shared pipeline template at version `vX`; no copied pipeline YAML. | Parse pipeline file | auto |
| CI-02 | Pipeline MUST run unit tests, integration tests, SAST and dependency scanning. | Inherited from shared template | auto |
| CI-03 | Pipeline MUST run the conformance check and fail on any MUST violation. | Inherited from shared template | auto |
| CI-04 | Deployments MUST use the standard canary/staged rollout. | Inherited from shared template | auto |

## 5. Configuration

| ID | Rule | Check | Fix |
|---|---|---|---|
| CONF-01 | Config MUST use `application.yaml` with per-environment profiles; no `.properties` files. | File check | agent |
| CONF-02 | Secrets handling MUST meet **TS-SEC-03**. | Secret scanner | human (rotate first, then remove) |
| CONF-03 | Environment-specific values MUST come from the approved config/secret store. | Static check | agent |

## 6. Observability

| ID | Rule | Check | Fix |
|---|---|---|---|
| OBS-01 | Service MUST implement the health endpoint contract in **TS-API-03**. | Integration test in template | agent |
| OBS-02 | Logging MUST meet **TS-LOG-01** and **TS-LOG-02**, using the shared logging library. Local tightening: `traceId` on every line. | `policies/logging.rego` + config check | auto |
| OBS-03 | Service MUST emit the standard RED metrics (rate, errors, duration) per endpoint. | Metrics endpoint check | agent |
| OBS-04 | Service MUST have SLOs defined in `docs/slo.yaml`. | File + schema check | human (owner sets targets) |

## 7. Security

| ID | Rule | Check | Fix |
|---|---|---|---|
| SEC-01 | Dependencies MUST meet **TS-SEC-01** (vulnerability policy). | Dependency scan + `policies/dependencies.rego` | auto (Renovate), agent if code changes needed |
| SEC-02 | Container images MUST meet **TS-SEC-02** (approved base images). | Dockerfile check | auto |
| SEC-03 | Authentication MUST use the shared security library; no custom auth code. | Static check | human |

## 8. Testing

| ID | Rule | Check | Fix |
|---|---|---|---|
| TEST-01 | Line coverage MUST NOT decrease as a result of a migration PR. | Coverage diff in CI | agent |
| TEST-02 | Line coverage SHOULD be at least 70%. | Coverage report | human |
| TEST-03 | Tests MUST use JUnit 5; no JUnit 4. | Dependency check | auto (OpenRewrite) |

## 9. Documentation and ownership

| ID | Rule | Check | Fix |
|---|---|---|---|
| DOC-01 | `README.md` MUST include: purpose, how to run locally, how to deploy, on-call contact. | Heading check | agent drafts, owner reviews |
| DOC-02 | `CODEOWNERS` MUST name a team, not individuals. | Parse file | human |
| DOC-03 | `catalog-info.yaml` MUST declare owner, domain, lifecycle and tier. | Schema check | agent drafts, owner confirms |

---

## 10. Rules for the migration agent

These apply to any automated or AI-driven change made against this standard.

**The agent MUST:**

- Read `STANDARD.resolved.md`, never this file directly, so inherited rules are in context.
- Work on a new branch named `standard/v<version>`.
- Change only what is needed to satisfy rules in this file.
- Run `mvn verify` and `./scripts/check-conformance.sh` before opening a PR.
- List every rule ID it addressed in the PR description (local and `TS-`), plus any it could not fix and why.
- Record the standard version and tech-standards ref in the PR description and update `.standard-version`.
- Stop and report if it cannot make the build pass within the attempt limit.

**The agent MUST NOT:**

- Change business logic, API contracts, or database schemas.
- Delete, skip, or weaken tests (no `@Disabled`, no loosened assertions).
- Touch rules marked `human`.
- Add new dependencies not managed by the parent/BOM.
- Merge its own PRs or push to the default branch.
- Edit inherited rule text or treat a local rule as overriding a `TS-` rule.

---

## 11. Exceptions

A repo MAY be exempt from a specific rule if listed in `standard-exceptions.yaml` with:

- rule ID,
- reason,
- approving owner,
- expiry date (max 90 days).

Expired exceptions fail the conformance check.

---

## 12. Changelog

| Version | Date | Changes |
|---|---|---|
| 1.1.0 | <YYYY-MM-DD> | Inherit approved tech standards `v2.3.0` by ID; add resolve step and assessment output |
| 1.0.0 | <YYYY-MM-DD> | Initial standard |

---

## 13. Assessment output

The assessment run produces one `assessment.json` per repo. The orchestrator
aggregates these into a fleet view to plan migration waves.

```json
{
  "repo": "<org>/payments-ledger-service",
  "assessed_at": "2026-11-02T09:14:00Z",
  "standard_version": "1.1.0",
  "tech_standards_ref": "v2.3.0 (a1b2c3d)",
  "build_passes_today": true,
  "summary": { "pass": 21, "fail": 7, "not_applicable": 2, "exception": 1 },
  "results": [
    { "rule": "BUILD-01", "status": "fail", "fix": "auto",  "evidence": "parent is service-parent 3.1.0, need >= 4.0.0" },
    { "rule": "TS-LOG-01", "status": "fail", "fix": "auto",  "evidence": "logback.xml uses plain-text pattern" },
    { "rule": "OBS-04",   "status": "fail", "fix": "human", "evidence": "docs/slo.yaml missing" },
    { "rule": "SEC-03",   "status": "exception", "expires": "2027-01-15" }
  ],
  "effort": "medium",
  "risks": ["integration test coverage 31%", "custom auth filter in SecurityConfig.java"]
}
```

- `status` and `evidence` for rules with automated checks MUST come from the
  check, not the agent's judgement.
- The agent MAY fill `effort` and `risks`, and assess rules that have no
  automated check yet. Those results are marked `"source": "agent"`.
- Re-run the assessment after migration. A repo is done when every MUST rule is
  `pass`, `not_applicable` or a valid `exception`.
