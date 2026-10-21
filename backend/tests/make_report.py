"""
Build the Chapter 4 test evidence: runs the whole suite (with coverage if installed) and writes
    reports/test_report.md   – summary + one row per test case (ID, module, what it checks, result)
    reports/test_cases.csv   – the same table for Excel / the manuscript
Usage (from backend/):  python tests/make_report.py
"""
import csv
import datetime as dt
import importlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reports"
MODULES = {
    "test_public_api": "Module 1 – Citizen Reporting Portal",
    "test_workflow": "Module 2 – Case Management",
    "test_deadlines": "Module 2 – ARTA deadlines",
    "test_evidence": "Module 2 – Proof of work",
    "test_rbac_api": "Security – Role-based access",
    "test_classifier": "Module 3 – AI Classification",
    "test_priority": "Module 4 – Priority Scoring",
    "test_duplicates": "Module 4 – Duplicates & recurrence",
    "test_geo": "Module 5 – GIS (purok tagging)",
    "test_analytics": "Modules 6–7 – Analytics & Decision Support",
    "test_notifications": "Module 1 – Notifications (SMS/email/alerts)",
}
LINE = re.compile(r"^(test_\w+) \((tests\.(test_\w+)\.(\w+)\.test_\w+)\)(?:\n.*?)? \.\.\. (ok|FAIL|ERROR|skipped.*)$", re.M)


def humanize(name):
    return name.removeprefix("test_").replace("_", " ").capitalize()


def main():
    OUT.mkdir(exist_ok=True)
    has_cov = shutil.which("coverage") is not None
    base = [sys.executable, "-W", "ignore", "-m", "coverage", "run", "--source=apps",
            "--omit=*/migrations/*,*/synthetic/*,*/management/commands/generate_*"] if has_cov else [sys.executable, "-W", "ignore"]
    started = dt.datetime.now()
    proc = subprocess.run(base + ["manage.py", "test", "tests", "-v", "2"], cwd=ROOT, capture_output=True, text=True)
    log = proc.stderr + proc.stdout
    (OUT / "test_run.log").write_text(log, encoding="utf-8")
    sys.path.insert(0, str(ROOT))

    rows = []
    for i, m in enumerate(LINE.finditer(log), 1):
        test, dotted, mod, cls, res = m.groups()
        doc = ""
        try:
            import django  # noqa: F401
            obj = getattr(importlib.import_module(f"tests.{mod}"), cls)
            doc = (getattr(obj, test).__doc__ or "").strip().splitlines()[0] if getattr(obj, test).__doc__ else ""
        except Exception:  # noqa: BLE001
            pass
        rows.append({"id": f"TC-{i:03d}", "area": MODULES.get(mod, mod), "group": cls, "test": humanize(test),
                     "detail": doc, "result": "Pass" if res == "ok" else res.title()})

    coverage = ""
    if has_cov:
        coverage = subprocess.run([sys.executable, "-m", "coverage", "report", "--skip-empty"], cwd=ROOT,
                                  capture_output=True, text=True).stdout
    passed = sum(r["result"] == "Pass" for r in rows)
    ran = re.search(r"Ran (\d+) tests? in ([\d.]+)s", log)

    with (OUT / "test_cases.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["id"])
        w.writeheader()
        w.writerows(rows)

    md = [f"# CCADSS automated test report", "",
          f"Run on {started:%B %d, %Y %H:%M} · Django test runner · {ran.group(1) if ran else len(rows)} tests in "
          f"{ran.group(2) if ran else '?'} s · **{passed} passed, {len(rows) - passed} not passed**", ""]
    md += ["## By area", "", "| Area | Tests | Passed |", "|---|---|---|"]
    for area in dict.fromkeys(r["area"] for r in rows):
        sub = [r for r in rows if r["area"] == area]
        md.append(f"| {area} | {len(sub)} | {sum(r['result'] == 'Pass' for r in sub)} |")
    md += ["", "## Test cases", "", "| ID | Area | Test | Result |", "|---|---|---|---|"]
    md += [f"| {r['id']} | {r['area']} | {r['test']} | {r['result']} |" for r in rows]
    if coverage:
        md += ["", "## Code coverage (statement)", "", "```", coverage.strip(), "```"]
    md += ["", "Scope note: automated tests verify functional correctness (ISO/IEC 25010 functional suitability, "
           "security). Usability (SUS), UAT and performance are evaluated separately with users."]
    (OUT / "test_report.md").write_text("\n".join(md), encoding="utf-8")
    print(f"{passed}/{len(rows)} passed → {OUT / 'test_report.md'}")
    sys.exit(0 if proc.returncode == 0 else 1)


if __name__ == "__main__":
    main()
