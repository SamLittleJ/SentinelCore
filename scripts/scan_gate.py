"""The gate of `make scan`: a scanner's findings against security/exceptions.yaml.

    python scripts/scan_gate.py checkov <report.json>...
    python scripts/scan_gate.py pip-audit <report.json>

Fails (exit 1) on any finding no exception covers, and on the exceptions
file itself when an entry is malformed, expired, dated too far ahead or
covers nothing the scanner reported: an exception outlives its finding only
until the next scan. Runs with the scanners' own Python (scripts/tools.sh),
which has PyYAML through Checkov.
"""

import datetime
import fnmatch
import json
import sys
from pathlib import Path

import yaml

EXCEPTIONS = Path(__file__).resolve().parent.parent / "security" / "exceptions.yaml"
TOOLS = {"checkov", "pip-audit"}
FIELDS = {"tool", "id", "resources", "reason", "expires"}
# An exception is a decision to look at again, not a permanent pass.
LONGEST = datetime.timedelta(days=180)


def load_exceptions(today: datetime.date) -> tuple[list[dict], list[str]]:
    """The entries of the exceptions file, and every problem found in it."""
    data = yaml.safe_load(EXCEPTIONS.read_text()) or {}
    entries = data.get("exceptions") or []
    problems = []
    for number, entry in enumerate(entries, start=1):
        where = f"exception {number}"
        if not isinstance(entry, dict) or set(entry) != FIELDS:
            problems.append(f"{where}: needs exactly the fields {sorted(FIELDS)}")
            continue
        where = f"exception {number} ({entry['tool']} {entry['id']})"
        if entry["tool"] not in TOOLS:
            problems.append(f"{where}: unknown tool")
        if not isinstance(entry["resources"], list) or not entry["resources"]:
            problems.append(f"{where}: resources must be a non-empty list")
        if not str(entry["reason"]).strip():
            problems.append(f"{where}: no reason")
        expires = entry["expires"]
        if not isinstance(expires, datetime.date):
            problems.append(f"{where}: expires must be a date (YYYY-MM-DD)")
        elif expires < today:
            problems.append(f"{where}: expired on {expires}")
        elif expires > today + LONGEST:
            problems.append(f"{where}: expires more than {LONGEST.days} days ahead")
    return entries, problems


def checkov_findings(reports: list[str]) -> list[tuple[str, str, str]]:
    """(check id, resource, description) of every failed Checkov check."""
    findings = []
    for report in reports:
        data = json.loads(Path(report).read_text())
        # One object for one framework, a list for several; a scan with
        # nothing to check gives a summary without results.
        for result in data if isinstance(data, list) else [data]:
            for check in result.get("results", {}).get("failed_checks", []):
                findings.append(
                    (check["check_id"], check["resource"], check["check_name"])
                )
    return findings


def pip_audit_findings(report: str) -> list[tuple[str, str, str]]:
    """(vulnerability id, package, fixed versions) of every reported vulnerability."""
    data = json.loads(Path(report).read_text())
    findings = []
    for dependency in data.get("dependencies", []):
        for vulnerability in dependency.get("vulns", []):
            fixes = ", ".join(vulnerability.get("fix_versions") or []) or "no fix yet"
            package = f"{dependency['name']}=={dependency['version']}"
            findings.append((vulnerability["id"], package, f"fixed in: {fixes}"))
    return findings


def covering(entry: dict, tool: str, finding_id: str, resource: str) -> list[str]:
    """The entry's resource patterns that cover this finding."""
    if entry["tool"] != tool or entry["id"] != finding_id:
        return []
    return [
        pattern
        for pattern in entry["resources"]
        if fnmatch.fnmatchcase(resource, pattern)
    ]


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in TOOLS:
        print(__doc__, file=sys.stderr)
        return 2
    tool, reports = argv[0], argv[1:]
    today = datetime.date.today()
    entries, problems = load_exceptions(today)
    valid = [
        entry for entry in entries if isinstance(entry, dict) and set(entry) == FIELDS
    ]

    if tool == "checkov":
        findings = checkov_findings(reports)
    else:
        findings = pip_audit_findings(reports[0])

    # (entry, pattern) pairs that covered a finding: a pattern left over
    # would silently cover a future finding of the same kind.
    used = set()
    open_findings = []
    for finding_id, resource, description in findings:
        matched = False
        for i, entry in enumerate(valid):
            for pattern in covering(entry, tool, finding_id, resource):
                used.add((i, pattern))
                matched = True
        if not matched:
            open_findings.append(f"{finding_id} {resource}: {description}")

    for i, entry in enumerate(valid):
        if entry["tool"] != tool:
            continue
        for pattern in entry["resources"]:
            if (i, pattern) not in used:
                problems.append(
                    f"{tool} {entry['id']} {pattern}: covers nothing; remove it"
                )

    for line in open_findings:
        print(f"FINDING  {line}")
    for line in problems:
        print(f"EXCEPTIONS  {line}")
    total, still_open = len(findings), len(open_findings)
    print(f"{tool}: {total} findings, {total - still_open} excepted, {still_open} open")
    return 1 if open_findings or problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
