#!/usr/bin/env python3
"""Generate the combined CI quality summary for GitHub Actions and the README.

Reads machine-readable inputs only:
  * JUnit XML (Surefire, jest-junit) for test results
  * the SonarQube Web API for the Quality Gate and measures

Writes markdown to the job summary, an optional metrics JSON for run-to-run
comparison, and a generated block in README.md between the CI-QUALITY
markers. Every section is skipped rather than guessed when its input is
missing, so the output never contains invented numbers.

Usage:
  generate-ci-summary.py --junit backend=backend/target/surefire-reports/TEST-*.xml \
      --junit frontend=frontend/junit.xml \
      --sonar-project-key opsera-mid_project \
      --sonar-ce-task-file sonar-report-task.txt \
      --out-json ci-metrics.json \
      --update-readme README.md \
      --run-url https://github.com/owner/repo/actions/runs/1
"""
import argparse
import glob
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

START_MARKER = "<!-- CI-QUALITY-START -->"
END_MARKER = "<!-- CI-QUALITY-END -->"
# The markers must occupy a whole line of their own. Matching them anywhere
# would let a prose mention such as "between <!-- CI-QUALITY-START --> and
# ..." start the span and swallow the prose in between.
MARKER_BLOCK = re.compile(
    r"^[ \t]*<!--[ \t]*CI-QUALITY-START[ \t]*-->[ \t]*$.*?"
    r"^[ \t]*<!--[ \t]*CI-QUALITY-END[ \t]*-->[ \t]*$",
    re.S | re.M)
MAX_FAILURE_ROWS = 10
MAX_WAIT_SECONDS = 420

PERCENT_METRICS = ("coverage", "duplicated_lines_density")
SONAR_ROWS = (
    ("Bugs", "bugs", ""),
    ("Vulnerabilities", "vulnerabilities", ""),
    ("Code Smells", "code_smells", ""),
    ("Security Hotspots", "security_hotspots", ""),
    ("Coverage", "coverage", "%"),
    ("Duplications", "duplicated_lines_density", "%"),
    ("Lines of Code", "ncloc", ""),
)


def expand(pattern):
    return sorted(glob.glob(pattern, recursive=True))


def to_seconds(raw):
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def duration(seconds):
    if seconds is None:
        return "n/a"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, rest = divmod(int(round(seconds)), 60)
    if minutes < 60:
        return f"{minutes}m {rest:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m {rest:02d}s"


def parse_junit(groups):
    """Aggregate JUnit XML into per-suite rows and totals.

    Surefire and jest-junit both nest <testcase> inside <testsuite>, and
    jest wraps several <testsuite> in a <testsuites> root, so iterate the
    tree rather than assuming a shape. Totals prefer the suite-level
    attributes and fall back to counting testcases when absent.
    """
    suites = []
    seen_files = set()
    for group, pattern in groups:
        for path in expand(pattern):
            try:
                root = ET.parse(path).getroot()
            except (ET.ParseError, OSError) as exc:
                print(f"::warning::could not parse {path}: {exc}")
                continue
            seen_files.add(path)
            for node in root.iter("testsuite"):
                cases = node.findall("testcase")
                tests = to_seconds(node.get("tests")) or len(cases)
                tests = int(node.get("tests") or tests)
                failures = int(node.get("failures") or sum(
                    1 for c in cases if c.find("failure") is not None))
                errors = int(node.get("errors") or sum(
                    1 for c in cases if c.find("error") is not None))
                skipped = int(node.get("skipped") or sum(
                    1 for c in cases if c.find("skipped") is not None))
                if not tests and not cases:
                    continue
                suite_time = to_seconds(node.get("time"))
                if suite_time is None:
                    suite_time = sum(
                        to_seconds(c.get("time")) or 0.0 for c in cases)
                name = node.get("name") or os.path.basename(path)
                suites.append({
                    "group": group,
                    "name": name.split(".")[-1] if group == "backend" else name,
                    "tests": tests,
                    "failed": failures + errors,
                    "skipped": skipped,
                    "time": suite_time,
                    "cases": [
                        {
                            "name": (c.get("name") or "?"),
                            "classname": (c.get("classname") or name),
                            "failure": (
                                (c.find("failure").get("message") or "")
                                if c.find("failure") is not None else
                                ((c.find("error").get("message") or "")
                                 if c.find("error") is not None else "")),
                        }
                        for c in cases
                        if c.find("failure") is not None
                        or c.find("error") is not None
                    ],
                })
    totals = {
        "tests": sum(s["tests"] for s in suites),
        "failed": sum(s["failed"] for s in suites),
        "skipped": sum(s["skipped"] for s in suites),
        "time": sum(s["time"] for s in suites if s["time"]),
    }
    totals["passed"] = max(
        0, totals["tests"] - totals["failed"] - totals["skipped"])
    totals["suites"] = len(suites)
    totals["files"] = len(seen_files)
    return suites, totals


def sonar_call(url, token, path, params):
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{url}{path}?{query}",
        headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def read_ce_task(path):
    """sonar-scanner writes .scannerwork/report-task.txt as 'ceTaskId=...'."""
    if not path or not os.path.isfile(path):
        return None
    match = re.search(r"ceTaskId=([A-Za-z0-9_-]+)",
                      open(path, encoding="utf-8", errors="replace").read())
    return match.group(1) if match else None


def wait_for_ce_task(url, token, task_id, verbose=True):
    """Block until the Compute Engine task leaves PENDING.

    Querying measures before the analysis is processed returns the previous
    run's numbers, which is the race this avoids.
    """
    if not task_id:
        return None
    deadline = time.time() + MAX_WAIT_SECONDS
    while time.time() < deadline:
        try:
            status = sonar_call(url, token, "/api/ce/task",
                                {"id": task_id})["task"]["status"]
        except Exception as exc:
            if verbose:
                print(f"::warning::CE task check failed: {exc}")
            return None
        if status != "PENDING":
            if verbose:
                print(f"CE task {task_id} finished with status {status}")
            return status
        if verbose:
            print(f"CE task {task_id} still {status}, waiting...")
        time.sleep(5)
    if verbose:
        print(f"::warning::CE task {task_id} did not finish in time")
    return None


def fetch_sonar(url, token, key, ce_task):
    if not url or not token or not key:
        return None
    url = url.strip().rstrip("/")
    try:
        wait_for_ce_task(url, token, ce_task)
        status = sonar_call(url, token, "/api/qualitygates/project_status",
                            {"projectKey": key})
        gate = (status.get("projectStatus") or {}).get("status", "UNKNOWN")
        keys = ",".join(m for _, m, _ in SONAR_ROWS)
        payload = sonar_call(url, token, "/api/measures/component", {
            "component": key, "metricKeys": keys})
        measures = {
            m["metric"]: m.get("value")
            for m in (payload.get("component") or {}).get("measures", [])
        }
        conditions = fetch_conditions(url, token, key)
        return {"gate": gate, "measures": measures,
                "conditions": conditions, "url": url, "key": key}
    except Exception as exc:
        print(f"::warning::SonarQube query failed: {exc}")
        return None


def fetch_conditions(url, token, key):
    """Failed quality-gate conditions, where the edition exposes them."""
    for path, params in (("/api/qualitygates/get_by_project", {"project": key}),
                         ("/api/qualitygates/project_status",
                          {"projectKey": key, "additionalFields": "conditions"})):
        try:
            payload = sonar_call(url, token, path, params)
        except Exception:
            continue
        conditions = payload.get("conditions")
        if conditions:
            return conditions
    return []


def sonar_value(raw, suffix):
    if raw in (None, "", "N/A"):
        return "N/A"
    return f"{raw}{suffix}"


def render_tests(suites, totals, compare):
    out = ["## 🧪 Tests", ""]
    if not suites:
        out += ["_No test reports were found._", ""]
        return out

    passed = totals["passed"]
    rate = (100.0 * passed / totals["tests"]) if totals["tests"] else 0.0
    verdict = "🟢 PASSED" if totals["failed"] == 0 else "🔴 FAILED"
    out += [f"### {verdict}", ""]
    out += [f"**{passed} / {totals['tests']} tests passed — {rate:.1f}%**", ""]
    out += ["| Metric | Result |", "| :--- | ---: |",
            f"| Tests | {totals['tests']} |",
            f"| Passed | ✅ {passed} |",
            f"| Failed | {'❌' if totals['failed'] else '✅'} {totals['failed']} |",
            f"| Skipped | ⏭️ {totals['skipped']} |",
            f"| Suites | {totals['suites']} |",
            f"| Test Files | {totals['files']} |",
            f"| Duration | ⏱️ {duration(totals['time'])} |",
            ""]

    out += ["### 🧩 Test Suites", "",
            "| Suite | Group | Status | Passed | Failed | Skipped | Duration |",
            "| :--- | :--- | :---: | ---: | ---: | ---: | ---: |"]
    for suite in suites:
        status = "✅" if suite["failed"] == 0 else "❌"
        out.append(
            f"| {suite['name']} | {suite['group']} | {status} | "
            f"{max(0, suite['tests'] - suite['failed'] - suite['skipped'])} | "
            f"{suite['failed']} | {suite['skipped']} | "
            f"{duration(suite['time'])} |")
    out.append("")

    if compare:
        out += render_comparison(totals, compare)

    failures = [(s, c) for s in suites for c in s["cases"]]
    out += ["### 🚨 Failed Tests", ""]
    if not failures:
        out += ["No failing tests 🎉", ""]
    else:
        out += ["| Test | Suite | Error |", "| :--- | :--- | :--- |"]
        for suite, case in failures[:MAX_FAILURE_ROWS]:
            message = (case["failure"] or "").strip().replace("|", "\\|")
            message = (message[:90] + "…") if len(message) > 90 else message
            out.append(f"| `{case['name']}` | {suite['group']} | {message} |")
        if len(failures) > MAX_FAILURE_ROWS:
            out.append("")
            out.append(f"_{len(failures) - MAX_FAILURE_ROWS} more "
                       f"— see the test report artifact._")
        out.append("")
    return out


def render_comparison(totals, previous):
    previous = previous.get("tests") or {}
    if not previous:
        return []
    rows = []
    for label, key in (("Tests", "tests"), ("Passed", "passed"),
                       ("Failed", "failed"), ("Skipped", "skipped")):
        if key in previous and key in totals:
            delta = totals[key] - previous[key]
            sign = f"{delta:+d}" if delta else "0"
            rows.append(f"| {label} | {previous[key]} | {totals[key]} | {sign} |")
    if "time" in previous and previous["time"]:
        delta = totals["time"] - previous["time"]
        sign = f"{delta:+.1f}s"
        rows.append(
            f"| Duration | {duration(previous['time'])} | "
            f"{duration(totals['time'])} | {sign} |")
    if not rows:
        return []
    return (["### 📈 Changes vs previous run", "",
             "| Metric | Previous | Current | Δ |",
             "| :--- | ---: | ---: | ---: |", *rows, ""])


def render_sonar(sonar):
    if not sonar:
        return []
    gate = sonar["gate"]
    verdict = "🟢 PASSED" if gate == "OK" else "🔴 FAILED"
    out = ["## 🔍 SonarQube", "", f"### {verdict} — Quality Gate `{gate}`", ""]
    if gate != "OK":
        out[2] = f"### 🔴 FAILED — Quality Gate `{gate}`"
    out += ["| Metric | Result |", "| :--- | ---: |"]
    for label, metric, suffix in SONAR_ROWS:
        out.append(f"| {label} | "
                   f"{sonar_value(sonar['measures'].get(metric), suffix)} |")
    out.append("")
    failed = [c for c in sonar.get("conditions") or []
              if str(c.get("status", "")).upper() not in ("OK", "PASSED", "")]
    if failed:
        out += ["#### Failed conditions", ""]
        for condition in failed[:MAX_FAILURE_ROWS]:
            out.append(f"- {condition.get('metricKey', 'condition')}: "
                       f"`{condition.get('status', '?')}`")
        out.append("")
    out += [f"🔗 [Open the SonarQube project]"
            f"({sonar['url']}/dashboard?id={sonar['key']})", ""]
    return out


def render_readme(totals, sonar, commit):
    """Compact variant for README.md — same data, less ceremony."""
    out = ["## 📊 CI Quality", ""]
    if commit:
        out += [f"_Generated by CI from commit `{commit}`._", ""]

    out += ["### 🧪 Tests", ""]
    if totals["suites"]:
        rate = (100.0 * totals["passed"] / totals["tests"]
                if totals["tests"] else 0.0)
        out += ["| Metric | Value |", "| :--- | ---: |",
                f"| Tests | {totals['tests']} |",
                f"| Passed | {totals['passed']} |",
                f"| Failed | {totals['failed']} |",
                f"| Skipped | {totals['skipped']} |",
                f"| Pass Rate | {rate:.1f}% |",
                f"| Duration | {duration(totals['time'])} |", ""]
    else:
        out += ["_No test reports were produced by the last run._", ""]

    out += ["### 🔍 SonarQube", ""]
    if sonar:
        gate = sonar["gate"]
        out += ["| Metric | Value |", "| :--- | ---: |",
                f"| Quality Gate | "
                f"{'🟢 Passed' if gate == 'OK' else '🔴 Failed'} |"]
        for label, metric, suffix in SONAR_ROWS:
            if metric == "ncloc":
                continue
            out.append(f"| {label} | "
                       f"{sonar_value(sonar['measures'].get(metric), suffix)} |")
        out += ["",
                f"[View the SonarQube project]"
                f"({sonar['url']}/dashboard?id={sonar['key']})", ""]
    else:
        out += ["_No SonarQube data was returned by the last run._", ""]
    return out


# TODO(validate) the field names below against a real
# acs-report-<component> artifact. reports[].scan.results.policyViolations[]
# is the documented roxctl shape; the summary variant and a recursive
# fallback are also tried so an unexpected layout degrades to "unparsed"
# rather than to a false "no violations".
def acs_violations(path):
    """(rows, error) — one row per violated policy occurrence."""
    if not path or not os.path.isfile(path):
        return None, "report not available"
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"unreadable ({exc})"

    policies = []
    for entry in data.get("reports") or []:
        scan = entry.get("scan") or entry
        results = scan.get("results") or {}
        summary = scan.get("summary") or {}
        policies.extend(results.get("policyViolations") or [])
        policies.extend(summary.get("policyViolations") or [])
    if not policies:
        policies = [node for node in walk_objects(data)
                    if "policy" in node and "violations" in node]

    rows = []
    for policy in policies:
        for violation in policy.get("violations") or []:
            rows.append({
                "policy": policy.get("policy") or "unknown policy",
                "severity": violation.get("severity")
                            or policy.get("severity") or "—",
                "message": violation.get("message") or violation.get("cve")
                           or "no message",
            })
    if not rows and policies:
        rows = [{"policy": p.get("policy") or "unknown policy",
                 "severity": "—",
                 "message": "reported without detail"} for p in policies]
    return rows, None


def walk_objects(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_objects(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk_objects(item)


def render_acs(reports):
    if not reports:
        return []
    out = ["## 🛡️ RHACS image check", ""]
    for component, path in reports:
        rows, error = acs_violations(path)
        if error:
            out += [f"**{component}** — _{error}_", ""]
            continue
        if not rows:
            out += [f"**{component}** — 🟢 no policy violations", ""]
            continue
        out += [f"**{component}** — ❌ {len(rows)} violation(s)", "",
                "| Policy | Severity | Violation |", "| :--- | :--- | :--- |"]
        for row in rows[:MAX_FAILURE_ROWS]:
            message = (row["message"] or "").replace("|", "&#124;")
            if len(message) > 120:
                message = message[:120] + "…"
            out.append(f"| {row['policy']} | {row['severity']} | {message} |")
        if len(rows) > MAX_FAILURE_ROWS:
            out += ["",
                    f"…and {len(rows) - MAX_FAILURE_ROWS} more — see the "
                    f"`acs-report-{component}` artifact."]
        out.append("")
    return out


def render_reports(run_url, has_sonar, sonar):
    # The clickable per-report links are written by the "Add report links"
    # step in ci.yml, which has the artifact-url outputs; this only adds the
    # links the generator can build itself.
    out = ["## 📦 Reports", ""]
    if sonar:
        out.append(f"- [SonarQube project]({sonar['url']}/dashboard?id={sonar['key']})")
    if run_url:
        out.append(f"- [All artifacts and logs for this run]({run_url})")
    out.append("")
    return out


def update_readme(path, body):
    if not os.path.isfile(path):
        print(f"::warning::{path} not found, skipping README update")
        return False
    content = open(path, encoding="utf-8").read()
    block = f"{START_MARKER}\n\n{body.rstrip()}\n\n{END_MARKER}"
    if MARKER_BLOCK.search(content):
        updated = MARKER_BLOCK.sub(lambda _: block, content)
    else:
        anchor = "\n## License"
        if anchor in content:
            updated = content.replace(anchor, f"\n{block}\n{anchor}", 1)
        else:
            updated = content.rstrip() + "\n\n" + block + "\n"
    if updated == content:
        print("README CI quality section already up to date")
        return False
    open(path, "w", encoding="utf-8").write(updated)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--junit", action="append", default=[],
                        metavar="GROUP=GLOB")
    parser.add_argument("--acs-report", action="append", default=[],
                        metavar="COMPONENT=PATH",
                        help="path to a roxctl image-check JSON report")
    parser.add_argument("--compare-json", default=None)
    parser.add_argument("--sonar-url", default=None)
    parser.add_argument("--sonar-token", default=None)
    parser.add_argument("--sonar-project-key", default=None)
    parser.add_argument("--sonar-ce-task-file", default=None)
    parser.add_argument("--out-summary", default=None)
    parser.add_argument("--out-json", default=None)
    parser.add_argument("--update-readme", default=None)
    parser.add_argument("--run-url", default=None)
    parser.add_argument("--commit", default=None)
    args = parser.parse_args()

    groups = []
    for entry in args.junit:
        group, _, pattern = entry.partition("=")
        if not pattern:
            group, pattern = "tests", group
        groups.append((group, pattern))

    acs_reports = []
    for entry in args.acs_report:
        component, _, path = entry.partition("=")
        acs_reports.append((component or "image", path))

    suites, totals = parse_junit(groups)

    compare = None
    if args.compare_json and os.path.isfile(args.compare_json):
        try:
            compare = json.load(open(args.compare_json, encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"::warning::could not read comparison file: {exc}")

    url = args.sonar_url or os.environ.get("SONAR_HOST_URL")
    token = args.sonar_token or os.environ.get("SONAR_TOKEN")
    sonar = fetch_sonar(url, token, args.sonar_project_key,
                        read_ce_task(args.sonar_ce_task_file))

    body = "\n".join([
        "# 🚀 CI Pipeline Summary",
        "",
        f"Commit: `{args.commit or os.environ.get('GITHUB_SHA', '')[:12]}`",
        "",
        "---",
        "",
        *render_tests(suites, totals, compare),
        "---",
        "",
        *render_sonar(sonar),
        *render_acs(acs_reports),
        *render_reports(args.run_url, bool(sonar), sonar),
    ])

    target = args.out_summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if target:
        with open(target, "a", encoding="utf-8") as handle:
            handle.write(body + "\n")
    print(body)

    if args.out_json:
        with open(args.out_json, "w", encoding="utf-8") as handle:
            json.dump({"tests": totals, "suites": suites,
                       "sonar": ({"gate": sonar["gate"],
                                  "measures": sonar["measures"]}
                                 if sonar else None),
                       "commit": args.commit}, handle, indent=2)

    if args.update_readme:
        readme_body = "\n".join(
            render_readme(totals, sonar, args.commit))
        if update_readme(args.update_readme, readme_body):
            print("README CI quality section updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
