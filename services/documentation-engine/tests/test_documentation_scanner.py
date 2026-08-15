"""Unit tests for documentation-engine scanner."""

from pathlib import Path

import pytest

from main import _compute_overall_score, _compute_team_readiness_score, scan_documentation

FIXTURES = Path(__file__).parent / "fixtures"


def test_good_repo_scores_high():
    result = scan_documentation(FIXTURES / "good_repo", "https://example.com/good")
    assert result["has_readme"] is True
    assert result["readme_score"] >= 70
    assert result["has_license"] is True
    assert result["has_contributing"] is True
    assert result["docs_folder_found"] is True
    assert result["overall_score"] >= 75
    assert result["grade"] in ("A", "B")
    assert len(result["findings"]) >= 5


def test_empty_repo_scores_f():
    result = scan_documentation(FIXTURES / "empty_repo", "https://example.com/empty")
    assert result["has_readme"] is False
    assert result["overall_score"] <= 20
    assert result["grade"] == "F"
    assert result["team_readiness_score"] == 0
    assert result["team_readiness_grade"] == "F"
    assert any(f["status"] == "fail" for f in result["findings"])


def test_team_ready_repo_scores_100():
    result = scan_documentation(FIXTURES / "team_ready_repo", "https://example.com/team")
    assert result["team_readiness_score"] == 100
    assert result["team_readiness_grade"] == "A"
    assert result["has_api_docs"] is True
    assert result["has_env_example"] is True
    assert result["has_codeowners"] is True
    assert result["has_pr_template"] is True
    assert result["has_issue_template"] is True
    assert result["has_changelog"] is True
    assert result["has_architecture_doc"] is True
    assert result["has_ci_config"] is True


def test_overall_score_hand_calculation():
    expected = _compute_overall_score(
        readme_score=70,
        has_license=True,
        has_contributing=True,
        docs_folder_found=True,
        code_comment_ratio=20.0,
        documented_functions_ratio=50.0,
    )
    manual = int(round(
        70 * 0.35
        + 100 * 0.10
        + 100 * 0.10
        + 100 * 0.10
        + 20 * 0.15
        + 50 * 0.20
    ))
    assert expected == manual
    assert _compute_team_readiness_score(True, True, True, True, True, True, True, True) == 100
