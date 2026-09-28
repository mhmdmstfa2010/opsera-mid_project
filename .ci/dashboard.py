#!/usr/bin/env python3
import os
import re
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SUMMARY = os.environ.get("SUMMARY_FILE") or os.path.join(os.getcwd(), "dashboard.md")
PROJECT_KEY = os.environ.get("PROJECT_KEY", "opsera-mid_project")
SONAR_URL = (os.environ.get("SONAR_URL") or "").strip().rstrip("/")
SONAR_TOKEN = (os.environ.get("SONAR_TOKEN") or "").strip()
GH_TOKEN = (os.environ.get("GH_TOKEN") or "").strip()
GH_REPO = os.environ.get("GH_REPO", "")
GH_WORKFLOW = os.environ.get("GH_WORKFLOW", "ci.yml")
RUN_ID = os.environ.get("RUN_ID", "")
PREVIOUS_RUNS = int(os.environ.get("PREVIOUS_RUNS", "4") or 4)
COVERAGE = os.environ.get("COVERAGE_DIR", "coverage-raw")
CI_WORKFLOW = os.environ.get("CI_WORKFLOW", ".github/workflows/ci.yml")

JACOCO = os.path.join(COVERAGE, "backend/target/site/jacoco/jacoco.xml")
LCOV = os.path.join(COVERAGE, "frontend/coverage/lcov.info")

ICON = {"success": "✅", "failure": "❌", "cancelled": "⚪", "skipped": "⚪"}
BANDS = [(80.0, "🟢"), (60.0, "🟡"), (0.0, "🔴")]


def pct(hit, found):
    return (100.0 * hit / found) if found else None


def band(value):
    if value is None:
        return "⚪"
    for threshold, icon in BANDS:
        if value >= threshold:
            return icon
    return "🔴"


def fmt(value, digits=1):
    return "n/a" if value is None else f"{value:.{digits}f}%"


def cell(value, found):
    if not found:
        return "n/a"
    return f"{band(pct(value, found))} {fmt(pct(value, found))} ({value}/{found})"


def api_get(url, headers=None):
    request = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode())


def gh(path, params=None):
    if not GH_TOKEN or not GH_REPO:
        return None
    query = f"?{urllib.parse.urlencode(params)}" if params else ""
    return api_get(f"https://api.github.com{path}{query}", {
        "Authorization": f"Bearer {GH_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"})


def sonar_get(path, params):
    if not SONAR_URL or not SONAR_TOKEN:
        return None, "credentials/URL not configured"
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}"
                     for k, v in params.items())
    request = urllib.request.Request(
        f"{SONAR_URL}{path}?{query}",
        headers={"Authorization": f"Bearer {SONAR_TOKEN}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode()), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, str(exc)[:80]


def stage_order():
    if not os.path.isfile(CI_WORKFLOW):
        return []
    jobs = []
    pending = None
    for line in open(CI_WORKFLOW, encoding="utf-8"):
        head = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if head:
            pending = head.group(1)
            continue
        named = re.match(r"^    name: (.+?)\s*$", line)
        if named and pending:
            jobs.append((pending, named.group(1).strip("'\"")))
            pending = None
    return jobs


def previous_runs():
    if not GH_TOKEN or not GH_REPO:
        return []
    try:
        listing = gh(
            f"/repos/{GH_REPO}/actions/workflows/{GH_WORKFLOW}/runs",
            {"per_page": PREVIOUS_RUNS + 2,
             "exclude_pull_requests": "true"})
    except Exception as exc:
        print(f"::warning::could not list previous runs: {exc}")
        return []
    out = []
    for run in (listing or {}).get("workflow_runs", []):
        if str(run.get("id")) == str(RUN_ID):
            continue
        if len(out) >= PREVIOUS_RUNS:
            break
        try:
            jobs = gh(f"/repos/{GH_REPO}/actions/runs/{run['id']}/jobs",
                      {"per_page": 100})
        except Exception:
            jobs = None
        out.append({"sha": (run.get("head_sha") or "")[:7],
                    "url": run.get("html_url", ""),
                    "jobs": (jobs or {}).get("jobs", [])})
    return out


def job_conclusion(jobs, prefix):
    matched = [j for j in jobs
               if j.get("name", "").startswith(f"{prefix} /")
               or j.get("name", "") == prefix]
    if not matched:
        return None
    for job in matched:
        if job.get("conclusion") not in ("success", "skipped"):
            return job.get("conclusion")
    return matched[0].get("conclusion")


def parse_jacoco():
    if not os.path.isfile(JACOCO):
        return None, "artifact not produced"
    try:
        root = ET.parse(JACOCO).getroot()
    except ET.ParseError as exc:
        print(f"::warning::could not parse {JACOCO}: {exc}")
        return None, "unparseable XML"
    counters = {}
    for node in root.findall("counter"):
        counters[node.get("type")] = (int(node.get("covered", 0)),
                                      int(node.get("missed", 0)))
    return (counters, None) if counters else (None, "no counters in report")


def parse_lcov():
    if not os.path.isfile(LCOV):
        return None, "artifact not produced"
    totals = {"LF": 0, "LH": 0, "BRF": 0, "BRH": 0}
    seen = False
    pattern = re.compile(r"^(LF|LH|BRF|BRH):(\d+)$")
    with open(LCOV, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = pattern.match(line.strip())
            if match:
                totals[match.group(1)] += int(match.group(2))
                seen = True
    return (totals, None) if seen else (None, "empty — no test files instrumented yet")


def sonar_data():
    status, _ = sonar_get("/api/qualitygates/project_status",
                           {"projectKey": PROJECT_KEY})
    gate = (status or {}).get("projectStatus", {}).get("status")
    keys = ("coverage", "duplicated_lines_density", "ncloc", "bugs",
            "vulnerabilities", "code_smells", "security_hotspots")
    payload, error = sonar_get("/api/measures/component", {
        "component": PROJECT_KEY, "metricKeys": ",".join(keys)})
    if payload is None and error:
        return gate, {}, error
    measures = (payload or {}).get("component", {}).get("measures", [])
    return gate, {m["metric"]: m.get("value") for m in measures}, None


def main():
    stages = stage_order()
    try:
        current = json.loads(os.environ.get("STAGE_RESULTS", "{}") or "{}")
    except json.JSONDecodeError:
        current = {}
    history = previous_runs()
    jacoco, jacoco_note = parse_jacoco()
    lcov, lcov_note = parse_lcov()

    hit = found = 0
    if jacoco:
        line = jacoco.get("LINE", (0, 0))
        hit += line[0]
        found += sum(line)
    if lcov:
        hit += lcov["LH"]
        found += lcov["LF"]
    overall = pct(hit, found)
    gate, sonar, sonar_error = sonar_data()

    out = []
    add = out.append

    add("## 📊 Pipeline results")
    add("")
    release = (current.get("scope") or {}).get("outputs", {}).get("release")
    mode = ("release" if release == "true"
            else "analysis only" if release == "false" else "unknown")
    add(f"commit `{os.environ.get('GITHUB_SHA', '')[:7]}` · mode **{mode}**")
    add("")

    add("### Stages")
    add("")
    header, divider = "| Stage | This run |", "| --- | --- |"
    for run in reversed(history):
        header += f" [`{run['sha']}`]({run['url']}) |"
        divider += " --- |"
    add(header)
    add(divider)

    failed = []
    green = 0
    for job_id, label in stages:
        if job_id == "dashboard":
            continue
        result = (current.get(job_id) or {}).get("result")
        if result == "success":
            green += 1
        if result in ("failure", "cancelled"):
            failed.append(label)
        mark = ICON.get(result, "▪️")
        mark += f" {result}" if result else " not run"
        row = f"| {label} | {mark} |"
        for run in history:
            row += f" {ICON.get(job_conclusion(run['jobs'], label), '▪️')} |"
        add(row)
    add("")
    if history:
        add(f"_{green}/{len(stages) - 1} stages green this run · last "
            f"{len(history)} run{'s' if len(history) != 1 else ''} alongside._")
        add("")

    add("### Coverage")
    add("")
    add("| Component | Lines | Branches |")
    add("| --- | --- | --- |")
    if jacoco:
        line = jacoco.get("LINE", (0, 0))
        branch = jacoco.get("BRANCH")
        add(f"| Backend (JaCoCo) | {cell(line[0], sum(line))} | "
            f"{cell(branch[0], sum(branch)) if branch else 'n/a'} |")
    else:
        add(f"| Backend (JaCoCo) | n/a — {jacoco_note} | n/a |")
    if lcov:
        add(f"| Frontend (lcov) | {cell(lcov['LH'], lcov['LF'])} | "
            f"{cell(lcov['BRH'], lcov['BRF'])} |")
    else:
        add(f"| Frontend (lcov) | n/a — {lcov_note} | n/a |")
    add(f"| **Overall** | **{cell(hit, found)}** | — |")
    add("")

    add("### SonarQube")
    add("")
    if sonar_error or not sonar:
        add(f"_unavailable ({sonar_error or 'no measures'})_")
    else:
        add("| Metric | Value |")
        add("| --- | --- |")
        add(f"| Quality Gate | "
            f"{ {'OK': '🟢', 'ERROR': '🔴'}.get(gate, '⚪') } {gate or 'n/a'} |")
        for label, key in (("Coverage", "coverage"),
                           ("Lines of code (ncloc)", "ncloc"),
                           ("Duplicated lines", "duplicated_lines_density"),
                           ("Bugs", "bugs"),
                           ("Vulnerabilities", "vulnerabilities"),
                           ("Security hotspots", "security_hotspots"),
                           ("Code smells", "code_smells")):
            if key not in sonar:
                add(f"| {label} | n/a |")
            elif key in ("coverage", "duplicated_lines_density"):
                add(f"| {label} | {fmt(float(sonar[key]))} |")
            else:
                add(f"| {label} | {sonar[key]} |")
    add("")

    add("---")
    add("")
    if failed:
        add("### ❌ Failed: " + ", ".join(failed))
    elif current:
        add(f"### 🟢 all stages passed · {fmt(overall)} coverage")
    else:
        add("### ⚪ no stage results were passed to this dashboard")
    add("")

    text = "\n".join(out)
    with open(SUMMARY, "a", encoding="utf-8") as handle:
        handle.write(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
