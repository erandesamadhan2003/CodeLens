"""Local persistence for raw Infilra findings."""

import json
from pathlib import Path

from config import SCAN_BASE_DIR
from models import RawFinding


def get_scan_dir(scan_id: str) -> Path:
    """Return the per-scan working directory."""
    return Path(SCAN_BASE_DIR) / scan_id


def get_repo_dir(scan_id: str) -> Path:
    """Return the cloned repository path for a scan."""
    return get_scan_dir(scan_id) / "repo"


def get_findings_path(scan_id: str) -> Path:
    """Return the path where raw findings JSON is stored."""
    return get_scan_dir(scan_id) / "findings.json"


def save_findings(scan_id: str, findings: list[RawFinding]) -> Path:
    """Persist raw findings as JSON under the scan directory."""
    scan_dir = get_scan_dir(scan_id)
    scan_dir.mkdir(parents=True, exist_ok=True)
    findings_path = get_findings_path(scan_id)

    payload = [finding.model_dump(by_alias=True) for finding in findings]
    findings_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return findings_path
