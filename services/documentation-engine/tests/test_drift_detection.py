"""Unit tests for webhook drift detection and Check Run summary."""

from main import (
    _apply_changelog_finding,
    _build_check_run_output,
    _detect_api_docs_drift,
    _detect_meaningful_changes,
    analyze_webhook_drift,
)


def test_new_export_without_docstring():
    diffs = [{
        "filename": "src/pricing.ts",
        "status": "modified",
        "patch": "\n".join([
            "@@ -1,3 +1,6 @@",
            " export function old() {}",
            "+export function calculateDiscount() {",
            "+  return 0;",
            "+}",
        ]),
    }]
    changes = _detect_meaningful_changes(diffs)
    assert any(c["kind"] == "new_function" and "calculateDiscount" in c["detail"] for c in changes)


def test_changelog_fail_when_meaningful_changes_without_changelog():
    findings = []
    meaningful = [{"file": "src/a.ts", "kind": "new_file", "detail": "added"}]
    _apply_changelog_finding(findings, meaningful, ["src/a.ts"])
    assert any(f["check"] == "changelog_sync" and f["status"] == "fail" for f in findings)


def test_changelog_pass_when_changelog_touched():
    findings = []
    meaningful = [{"file": "src/a.ts", "kind": "new_file", "detail": "added"}]
    _apply_changelog_finding(findings, meaningful, ["CHANGELOG.md", "src/a.ts"])
    assert any(f["check"] == "changelog_sync" and f["status"] == "pass" for f in findings)


def test_api_docs_drift():
    drift = _detect_api_docs_drift(["routes/orders.js", "README.md"])
    assert drift == ["routes/orders.js"]


def test_no_api_drift_when_docs_updated():
    drift = _detect_api_docs_drift(["routes/orders.js", "openapi.yaml"])
    assert drift == []


def test_empty_diffs_skips_meaningful_but_runs_api_drift():
    out = analyze_webhook_drift([], ["routes/users.js"])
    assert out["meaningful_changes_undocumented"] is None
    assert out["api_docs_drift_detected"] is True
    assert out["api_docs_drift_files"] == ["routes/users.js"]
    assert out["findings_extra"][0]["check"] == "diff_data"


def test_webhook_drift_with_diffs_sets_booleans():
    out = analyze_webhook_drift(
        [{"filename": "routes/x.js", "status": "modified", "patch": "+export function x() {}"}],
        ["routes/x.js"],
    )
    assert out["meaningful_changes_undocumented"] is not None
    assert out["api_docs_drift_detected"] is True
    assert out["api_docs_drift_files"] == ["routes/x.js"]


def test_clean_commit_check_run_success():
    result = {
        "findings": [],
        "meaningful_changes_undocumented": [],
        "api_docs_drift_files": [],
    }
    conclusion, title, _summary = _build_check_run_output(result)
    assert conclusion == "success"
    assert "up to date" in title.lower() or "up to date" in _summary.lower()


def test_issues_check_run_neutral():
    result = {
        "findings": [{"check": "changelog_sync", "status": "fail", "detail": "no changelog"}],
        "meaningful_changes_undocumented": [
            {"file": "src/x.ts", "kind": "new_file", "detail": "New source file src/x.ts added"},
        ],
        "api_docs_drift_detected": False,
        "api_docs_drift_files": [],
        "team_readiness_score": 25,
        "team_readiness_grade": "F",
    }
    conclusion, title, summary = _build_check_run_output(result)
    assert conclusion == "neutral"
    assert "issue" in title.lower()
    assert "Undocumented Changes" in summary
    assert "Team Readiness" in summary
