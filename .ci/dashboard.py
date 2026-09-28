#!/usr/bin/env python3
import os
import re
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

SUMMARY = os.environ.get("SUMMARY_FILE") or os.path.join(
    os.getcwd(), "dashboard.md")
PROJECT_KEY = os.environ.get("PROJECT_KEY", "opsera-mid_project")
SONAR_URL = (os.environ.get("SONAR_URL") or "").strip().rstrip("/")
SONAR_TOKEN = (os.environ.get("SONAR_TOKEN") or "").strip()
TEST_RESULT = os.environ.get("TEST_RESULT", "unknown")
SONAR_RESULT = os.environ.get("SONAR_RESULT", "unknown")

COVERAGE = os.environ.get("COVERAGE_DIR", "coverage-raw")
JACOCO = os.path.join(COVERAGE, "backend/target/site/jacoco/jacoco.xml")
LCOV = os.path.join(COVERAGE, "frontend/coverage/lcov.info")

VERDICT = {"success": ("✅", "pass"), "failure": ("❌", "fail"),
           "cancelled": ("⚪", "cancelled"), "skipped": ("⚪", "skipped")}
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
    """'82.4% (1404/1703)' or 'n/a' when the file was not produced."""
    if not found:
        return "n/a"
    p = pct(value, found) if value is not None else None
    return f"{band(p)} {fmt(p)} ({value}/{found})"

def verdict(result):
    icon, word = VERDICT.get(result, ("⚪", result or "unknown"))
    return f"{icon} {word}"

def parse_jacoco():
    """(counters, note) — overall counters from the top-level <report>."""
    if not os.path.isfile(JACOCO):
        return None, "artifact not produced"
    try:
        root = ET.parse(JACOCO).getroot()
    except ET.ParseError as exc:
        print(f"::warning::could not parse {JACOCO}: {exc}")
        return None, "unparseable XML"
    counters = {}
    for node in root.findall("counter"):
        kind = node.get("type")
        counters[kind] = (int(node.get("covered", 0)), int(node.get("missed", 0)))
    if not counters:
        return None, "no counters in report"
    return counters, None

def parse_lcov():
    """(totals, note) — sums LF/LH and BRF/BRH across every lcov record."""
    if not os.path.isfile(LCOV):
        return None, "artifact not produced"
    totals = {"LF": 0, "LH": 0, "BRF": 0, "BRH": 0, "FNF": 0, "FNH": 0}
    seen = False
    pattern = re.compile(r"^(LF|LH|BRF|BRH|FNF|FNH):(\d+)$")
    with open(LCOV, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            match = pattern.match(line.strip())
            if match:
                totals[match.group(1)] += int(match.group(2))
                seen = True
    if not seen:
        return None, "empty — no test files instrumented yet"
    return totals, None

def sonar_get(path, params):
    if not SONAR_URL or not SONAR_TOKEN:
        return None, "credentials/URL not configured"
    query = "&".join(f"{k}={urllib.parse.quote(str(v))}"
                     for k, v in params.items())
    url = f"{SONAR_URL}{path}?{query}"
    request = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {SONAR_TOKEN}"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode()), None
    except urllib.error.HTTPError as exc:
        return None, f"HTTP {exc.code}"
    except Exception as exc:                      # noqa: BLE001
        return None, str(exc)[:80]

def sonar_data():
    """(gate_status, {metric: value}, error). Never raises."""
    status, _ = sonar_get(
        "/api/qualitygates/project_status", {"projectKey": PROJECT_KEY})
    gate = (status or {}).get("projectStatus", {}).get("status")

    keys = ("coverage", "duplicated_lines_density", "ncloc", "bugs",
            "vulnerabilities", "code_smells", "security_hotspots")
    payload, error = sonar_get("/api/measures/component", {
        "component": PROJECT_KEY, "metricKeys": ",".join(keys)})
    if payload is None and error:
        return gate, {}, error
    measures = (payload or {}).get("component", {}).get("measures", [])
    values = {m["metric"]: m.get("value") for m in measures}
    return gate, values, None

def main():
    jacoco, jacoco_note = parse_jacoco()
    lcov, lcov_note = parse_lcov()
    gate, sonar, sonar_error = sonar_data()

    total_hit = total_found = 0
    if jacoco:
        total_hit += jacoco.get("LINE", (0, 0))[0]
        total_found += sum(jacoco.get("LINE", (0, 0)))
    if lcov:
        total_hit += lcov.get("LH", 0)
        total_found += lcov.get("LF", 0)
    overall = pct(total_hit, total_found)

    gate_icon = {"OK": "🟢", "ERROR": "🔴"}.get(gate, "⚪")

    out = []
    add = out.append

    add("## 📊 Test & quality results")
    add("")
    add(f"**{PROJECT_KEY}** · commit `{os.environ.get('GITHUB_SHA', '')[:12]}`")
    add("")

    add("### Gates")
    add("")
    add("| Stage | Result |")
    add("| --- | --- |")
    add(f"| Unit tests | {verdict(TEST_RESULT)} |")
    add(f"| Gate 2 · SonarQube Quality Gate | "
        f"{gate_icon} {gate or 'unavailable'} |")
    add(f"| SonarQube job | {verdict(SONAR_RESULT)} |")
    add("")

    add("### Code coverage")
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

    add(f"| **Overall** | **{cell(total_hit, total_found)}** | — |")
    add("")

    add("### SonarQube")
    add("")
    if sonar_error or not sonar:
        reason = sonar_error or "no measures returned"
        add(f"_SonarQube data unavailable ({reason})._")
    else:
        add("| Metric | Value |")
        add("| --- | --- |")
        rows = [
            ("Quality Gate", f"{gate_icon} {gate or 'n/a'}"),
            ("Coverage", fmt(float(sonar["coverage"]))
             if "coverage" in sonar else "n/a"),
            ("Lines of code (ncloc)", sonar.get("ncloc", "n/a")),
            ("Duplicated lines",
             fmt(float(sonar["duplicated_lines_density"]))
             if "duplicated_lines_density" in sonar else "n/a"),
            ("Bugs", sonar.get("bugs", "n/a")),
            ("Vulnerabilities", sonar.get("vulnerabilities", "n/a")),
            ("Security hotspots", sonar.get("security_hotspots", "n/a")),
            ("Code smells", sonar.get("code_smells", "n/a")),
        ]
        for name, value in rows:
            add(f"| {name} | {value} |")
    add("")

    add("---")
    add("")
    if TEST_RESULT == "success" and gate == "OK":
        add(f"### Overall: 🟢 {fmt(overall)} coverage, all gates green")
    else:
        add("### Overall: 🔴 see the failing stage above")
    add("")

    text = "\n".join(out)
    with open(SUMMARY, "a", encoding="utf-8") as handle:
        handle.write(text)
    print(text)
    print(f"::notice::overall line coverage {fmt(overall)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
