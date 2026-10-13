"""Check the published dataset and the README's key findings against data/stats.json.

Standard library only. Exit code 0 when everything matches, 1 otherwise.

Checks:
1. data/dataset.csv and data/dataset.json each have stats["repos"] rows and the same columns.
2. The columns the analysis needs are present, and no per-repository column exists for the
   secret rules whose counts are withheld (SSG203, SSG405, SSG501, SSG502, SSG503).
3. In the README's "Key findings" section, every "A of B (C%)" matches a fraction in stats.json,
   and every other number appears somewhere in stats.json.
"""
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WITHHELD = ("SSG203", "SSG405", "SSG501", "SSG502", "SSG503")
REQUIRED = [
    "repo", "commit", "stars", "owner_type", "created_at", "github_licence_spdx", "github_security_policy",
    "n_skill_md", "has_plugin_json", "has_marketplace_json", "has_server_json", "has_mcp_json",
    "n_hooks", "n_mcp_stdio", "SSG401", "SSG402", "SSG403", "SSG601", "SSG606", "SSG607",
    "n_skill_yaml_reject", "n_skill_no_front_matter", "n_skill_desc_over_1024", "n_skill_with_desc",
    "n_portability_findings", "any_unrestricted_bash", "hook_network_flag", "hook_network_review",
    "any_unpinned_mcp", "no_licence_file", "no_security_md", "any_yaml_reject", "any_desc_over_1024",
]
FRACTION = re.compile(r"^(\d+)/(\d+) \((\d+(?:\.\d+)?)%\)$")
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
CLAIM = re.compile(r"(\d[\d,]*) of (\d[\d,]*) \((\d+(?:\.\d+)?)%\)")


def num(s):
    return float(s.replace(",", ""))


def stats_numbers(stats):
    """Return (fractions, numbers): every a/b (p%) triple and every number found in stats.json."""
    fractions, numbers = set(), set()

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            numbers.add(float(v))
        elif isinstance(v, str):
            m = FRACTION.match(v)
            if m:
                fractions.add((num(m.group(1)), num(m.group(2)), num(m.group(3))))
            for n in NUMBER.findall(v):
                numbers.add(num(n))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(stats)
    return fractions, numbers


def key_findings(readme):
    m = re.search(r"^## Key findings\s*$(.*?)^## ", readme, re.S | re.M)
    if not m:
        return None
    return [ln for ln in m.group(1).splitlines() if ln.startswith("- ")]


def main():
    errors = []
    stats = json.load(open(os.path.join(ROOT, "data", "stats.json"), encoding="utf-8"))
    with open(os.path.join(ROOT, "data", "dataset.csv"), newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)
    js = json.load(open(os.path.join(ROOT, "data", "dataset.json"), encoding="utf-8"))

    if len(rows) != stats["repos"]:
        errors.append(f"dataset.csv has {len(rows)} rows, stats.json says {stats['repos']}")
    if len(js) != stats["repos"]:
        errors.append(f"dataset.json has {len(js)} rows, stats.json says {stats['repos']}")
    if js and list(js[0].keys()) != columns:
        errors.append("dataset.json keys differ from dataset.csv columns")
    if len({r["repo"] for r in rows}) != len(rows):
        errors.append("dataset.csv has duplicate repositories")
    for c in REQUIRED:
        if c not in columns:
            errors.append(f"dataset.csv is missing column {c}")
    for c in columns:
        if any(w in c for w in WITHHELD):
            errors.append(f"dataset.csv has withheld secret-rule column {c}")
    if sum(1 for r in rows if int(r["n_skill_md"] or 0) > 0) != stats["repos_with_skills"]:
        errors.append("repositories with skills in dataset.csv do not match stats.json")

    findings = key_findings(open(os.path.join(ROOT, "README.md"), encoding="utf-8").read())
    if not findings:
        errors.append("README has no '## Key findings' list")
        findings = []
    fractions, numbers = stats_numbers(stats)
    checked = 0
    for line in findings:
        rest = line
        for a, b, p in CLAIM.findall(line):
            checked += 1
            if (num(a), num(b), num(p)) not in fractions:
                errors.append(f"'{a} of {b} ({p}%)' is not in stats.json: {line[:80]}")
            rest = rest.replace(f"{a} of {b} ({p}%)", " ")
        for n in NUMBER.findall(rest):
            checked += 1
            if num(n) not in numbers:
                errors.append(f"number {n} is not in stats.json: {line[:80]}")

    for e in errors:
        print("FAIL:", e)
    if errors:
        return 1
    print(f"OK: {len(rows)} rows, {len(columns)} columns, no withheld columns; "
          f"{checked} numbers in {len(findings)} key findings match stats.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
