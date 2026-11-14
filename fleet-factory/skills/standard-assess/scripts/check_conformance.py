#!/usr/bin/env python3
"""Deterministic conformance check against STANDARDS.MD (phase 1).

Reads one repo, runs file-level checks for the rules it knows, and writes
assessment.json in the shape defined in STANDARDS.MD section 13.

No AI here. Every status and evidence string comes from code, so the result
is the same every run and can be trusted in CI. Rules this script cannot
check are listed as "unchecked" so the agent (or a human) can assess them
and mark them "source": "agent".

Python 3.9+, standard library only.

Usage:
  check_conformance.py <repo-dir> [--out assessment.json]
                       [--standard-version 1.1.0]
                       [--min-parent-version 4.0.0] [--java 21]

Exit code: 0 if no MUST rule fails, 1 if any MUST rule fails, 2 on bad input.
"""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# rule id -> (level, fix owner). Mirrors the tables in STANDARDS.MD.
RULES = {
    "LAYOUT-01": ("MUST", "auto"),
    "LAYOUT-02": ("MUST", "auto"),
    "LAYOUT-03": ("MUST", "auto"),
    "LAYOUT-04": ("SHOULD", "human"),
    "BUILD-01": ("MUST", "auto"),
    "BUILD-02": ("MUST", "auto"),
    "BUILD-03": ("MUST", "auto"),
    "BUILD-04": ("MUST", "agent"),
    "CI-01": ("MUST", "auto"),
    "CONF-01": ("MUST", "agent"),
    "CONF-02": ("MUST", "human"),
    "CONF-03": ("MUST", "agent"),
    "OBS-01": ("MUST", "agent"),
    "OBS-02": ("MUST", "auto"),
    "OBS-03": ("MUST", "agent"),
    "OBS-04": ("MUST", "human"),
    "SEC-03": ("MUST", "human"),
    "TEST-03": ("MUST", "auto"),
    "DOC-01": ("MUST", "agent"),
    "DOC-02": ("MUST", "human"),
    "DOC-03": ("MUST", "agent"),
}

POM_NS = {"m": "http://maven.apache.org/POM/4.0.0"}


# ---------------------------------------------------------------- helpers

def result(rule, status, evidence):
    level, fix = RULES[rule]
    return {"rule": rule, "level": level, "status": status, "fix": fix,
            "evidence": evidence, "source": "script"}


def parse_version(text):
    return tuple(int(p) for p in re.findall(r"\d+", text)[:3])


def load_pom(repo):
    pom = repo / "pom.xml"
    if not pom.exists():
        return None
    try:
        return ET.parse(pom).getroot()
    except ET.ParseError:
        return None


def pom_find(root, path):
    """Find in a pom with or without the Maven namespace."""
    el = root.find("/".join("m:" + p for p in path.split("/")), POM_NS)
    return el if el is not None else root.find(path)


def pom_findall(root, path):
    found = root.findall("/".join("m:" + p for p in path.split("/")), POM_NS)
    return found or root.findall(path)


def tracked_files(repo):
    try:
        out = subprocess.run(["git", "-C", str(repo), "ls-files"],
                             capture_output=True, text=True, check=True).stdout
        return out.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Not a git repo: fall back to walking the tree.
        return [str(p.relative_to(repo)) for p in repo.rglob("*")
                if p.is_file() and ".git" not in p.parts]


def load_exceptions(repo, today):
    """Minimal reader for standard-exceptions.yaml.

    Expected shape (kept flat on purpose so no YAML library is needed):
      - rule: SEC-03
        reason: ...
        owner: ...
        expires: 2027-01-15
    """
    path = repo / "standard-exceptions.yaml"
    exceptions, current = {}, None
    if not path.exists():
        return exceptions
    for line in path.read_text().splitlines():
        m = re.match(r"\s*-?\s*(rule|reason|owner|expires)\s*:\s*(.+?)\s*$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip("'\"")
        if key == "rule":
            current = {"rule": value}
            exceptions[value] = current
        elif current is not None:
            current[key] = value
    for exc in exceptions.values():
        try:
            exc["valid"] = dt.date.fromisoformat(exc.get("expires", "")) >= today
        except ValueError:
            exc["valid"] = False
    return exceptions


# ---------------------------------------------------------------- checks

def check_layout(repo, files):
    out = []
    wanted = ["src/main/java", "src/test/java", "src/integrationTest/java",
              "config", "docs"]
    missing = [d for d in wanted if not (repo / d).is_dir()]
    out.append(result("LAYOUT-01", "fail" if missing else "pass",
                      "missing dirs: " + ", ".join(missing) if missing
                      else "all template dirs present"))

    required = ["README.md", "CODEOWNERS", "catalog-info.yaml", "AGENTS.md"]
    missing = [f for f in required
               if not (repo / f).exists() and not (repo / ".github" / f).exists()]
    out.append(result("LAYOUT-02", "fail" if missing else "pass",
                      "missing files: " + ", ".join(missing) if missing
                      else "all required files present"))

    bad = [f for f in files
           if f.startswith("target/") or "/target/" in f or f.endswith(".jar")
           or f.startswith(".idea/") or f.endswith(".iml")]
    bad = [f for f in bad if not f.endswith(("maven-wrapper.jar", "gradle-wrapper.jar"))]
    out.append(result("LAYOUT-03", "fail" if bad else "pass",
                      "tracked build/IDE files: " + ", ".join(bad[:5]) if bad
                      else "no build outputs or IDE files tracked"))
    return out


def check_build(pom, min_parent, java):
    if pom is None:
        reason = "no readable pom.xml at repo root"
        return [dict(result(r, "not_applicable", reason))
                for r in ("BUILD-01", "BUILD-02", "BUILD-03")]
    out = []

    parent = pom_find(pom, "parent")
    if parent is None:
        out.append(result("BUILD-01", "fail", "pom has no <parent>"))
    else:
        art = (pom_find(parent, "artifactId").text or "").strip()
        ver = (pom_find(parent, "version").text or "").strip()
        ok = art.endswith("service-parent") and parse_version(ver) >= parse_version(min_parent)
        out.append(result("BUILD-01", "pass" if ok else "fail",
                          "parent is %s %s, need *service-parent >= %s" % (art, ver, min_parent)))

    pinned = []
    for dep in pom_findall(pom, "dependencies/dependency"):
        if pom_find(dep, "version") is not None:
            pinned.append(pom_find(dep, "artifactId").text)
    out.append(result("BUILD-02", "fail" if pinned else "pass",
                      "explicit versions on: " + ", ".join(pinned) if pinned
                      else "no explicit dependency versions"))

    release = None
    for key in ("maven.compiler.release", "java.version", "maven.compiler.target"):
        el = pom_find(pom, "properties/" + key)
        if el is not None and el.text:
            release = el.text.strip()
            break
    if release is None:
        out.append(result("BUILD-03", "fail", "no Java version property found"))
    else:
        out.append(result("BUILD-03", "pass" if release == str(java) else "fail",
                          "Java version is %s, need %s" % (release, java)))
    return out


def check_config(repo):
    res = repo / "src/main/resources"
    props = sorted(str(p.relative_to(repo)) for p in res.rglob("*.properties")) if res.is_dir() else []
    return [result("CONF-01", "fail" if props else "pass",
                   ".properties files: " + ", ".join(props) if props
                   else "no .properties config files")]


def check_tests(repo, pom):
    hits = []
    for p in (repo / "src").rglob("*.java") if (repo / "src").is_dir() else []:
        text = p.read_text(errors="ignore")
        if re.search(r"^import\s+org\.junit\.(Test|Before|After|Assert|runner)", text, re.M):
            hits.append(str(p.relative_to(repo)))
    if pom is not None:
        for dep in pom_findall(pom, "dependencies/dependency"):
            g, a = pom_find(dep, "groupId"), pom_find(dep, "artifactId")
            if g is not None and a is not None and (g.text, a.text) == ("junit", "junit"):
                hits.insert(0, "pom.xml: junit:junit dependency")
    return [result("TEST-03", "fail" if hits else "pass",
                   "JUnit 4 usage: " + ", ".join(hits[:5]) if hits
                   else "no JUnit 4 usage found")]


def check_docs(repo):
    out = []
    readme = repo / "README.md"
    if not readme.exists():
        out.append(result("DOC-01", "fail", "README.md missing"))
    else:
        heads = " ".join(re.findall(r"^#+\s*(.+)$", readme.read_text(), re.M)).lower()
        topics = {"purpose": ["purpose", "overview", "about"],
                  "run locally": ["run", "local", "getting started"],
                  "deploy": ["deploy", "release"],
                  "on-call": ["on-call", "oncall", "support", "contact"]}
        missing = [t for t, words in topics.items() if not any(w in heads for w in words)]
        out.append(result("DOC-01", "fail" if missing else "pass",
                          "README missing sections: " + ", ".join(missing) if missing
                          else "README has all required sections"))

    owners = repo / "CODEOWNERS"
    if not owners.exists():
        owners = repo / ".github" / "CODEOWNERS"
    if not owners.exists():
        out.append(result("DOC-02", "fail", "CODEOWNERS missing"))
    else:
        handles = re.findall(r"@[\w./-]+", owners.read_text())
        people = [h for h in handles if "/" not in h]
        out.append(result("DOC-02", "fail" if people or not handles else "pass",
                          "individuals listed: " + ", ".join(people) if people
                          else ("no owners listed" if not handles else "owners are teams")))

    out.append(result("OBS-04", "pass" if (repo / "docs/slo.yaml").exists() else "fail",
                      "docs/slo.yaml present" if (repo / "docs/slo.yaml").exists()
                      else "docs/slo.yaml missing"))
    return out


# ---------------------------------------------------------------- main

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("repo")
    ap.add_argument("--out", default="assessment.json")
    ap.add_argument("--standard-version", default="1.1.0")
    ap.add_argument("--min-parent-version", default="4.0.0")
    ap.add_argument("--java", default="21")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print("not a directory: %s" % repo, file=sys.stderr)
        return 2

    today = dt.date.today()
    pom = load_pom(repo)
    files = tracked_files(repo)

    results = []
    results += check_layout(repo, files)
    results += check_build(pom, args.min_parent_version, args.java)
    results += check_config(repo)
    results += check_tests(repo, pom)
    results += check_docs(repo)

    # Apply exceptions after checks so evidence is kept.
    exceptions = load_exceptions(repo, today)
    for r in results:
        exc = exceptions.get(r["rule"])
        if exc and r["status"] == "fail":
            if exc["valid"]:
                r["status"], r["expires"] = "exception", exc.get("expires")
            else:
                r["evidence"] += " (exception expired %s)" % exc.get("expires", "?")

    checked = {r["rule"] for r in results}
    unchecked = [{"rule": rid, "level": lvl, "fix": fix, "status": "unchecked"}
                 for rid, (lvl, fix) in RULES.items() if rid not in checked]

    summary = {}
    for r in results:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    summary["unchecked"] = len(unchecked)

    remote = ""
    # Only read the remote if the repo is its own git root; otherwise git
    # would report the enclosing repo (e.g. for examples/legacy-service).
    if (repo / ".git").exists():
        try:
            remote = subprocess.run(["git", "-C", str(repo), "remote", "get-url", "origin"],
                                    capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            pass

    report = {
        "repo": remote or repo.name,
        "assessed_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "standard_version": args.standard_version,
        "summary": summary,
        "results": results + unchecked,
        "effort": None,   # filled by the agent
        "risks": [],      # filled by the agent
    }
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")

    must_fails = [r["rule"] for r in results if r["status"] == "fail" and r["level"] == "MUST"]
    print("%s: %s" % (report["repo"], json.dumps(summary)))
    if must_fails:
        print("MUST failures: " + ", ".join(must_fails))
    print("wrote " + args.out)
    return 1 if must_fails else 0


if __name__ == "__main__":
    sys.exit(main())
