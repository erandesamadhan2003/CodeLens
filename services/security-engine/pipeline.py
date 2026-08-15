"""Infilra stage-1 pipeline: clone, Semgrep, parse, persist."""

import json
import logging
import shutil
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

from config import (
    CLONE_TIMEOUT_SEC,
    CONTEXT_WINDOW_LINES,
    SEMGREP_CONFIGS,
    SEMGREP_RULE_TIMEOUT_SEC,
    SEMGREP_SUBPROCESS_TIMEOUT_SEC,
)
from models import RawFinding, RawSeverity, ScanResult
from persistence import get_repo_dir, get_scan_dir, save_findings

logger = logging.getLogger(__name__)


def process_scan(
    scan_id: str,
    repo_url: str,
    github_token: Optional[str] = None,
) -> ScanResult:
    """
    Run the Infilra raw scan pipeline for a single job.

    Clones the target repository, runs Semgrep, parses findings, persists them,
    and always removes the cloned source directory in a finally block.

    Args:
        scan_id: Unique identifier for this scan (maps to platform runId).
        repo_url: Repository URL to clone (maps to platform cloneUrl).
        github_token: Optional GitHub token for private repositories.

    Returns:
        ScanResult describing success or a specific failure reason.
    """
    logger.info("Infilra scan started: scan_id=%s repo_url=%s", scan_id, repo_url)

    try:
        repo_path = _clone_repo(scan_id, repo_url, github_token)
        semgrep_data = _run_semgrep(repo_path)
        findings = _parse_semgrep_results(semgrep_data)
        findings = _enrich_findings_with_context(repo_path, findings)
        findings_path = save_findings(scan_id, findings)
        summary = _summarize_findings(findings)

        logger.info(
            "Infilra scan completed: scan_id=%s %s path=%s",
            scan_id,
            summary,
            findings_path,
        )

        return ScanResult(
            scan_id=scan_id,
            status="completed",
            findings_count=len(findings),
            summary=summary,
            findings_path=str(findings_path),
            findings=findings,
        )
    except CloneError as exc:
        logger.error("Infilra scan failed: scan_id=%s reason=%s", scan_id, exc.reason)
        return ScanResult(scan_id=scan_id, status="failed", failure_reason=exc.reason)
    except SemgrepError as exc:
        logger.error("Infilra scan failed: scan_id=%s reason=%s", scan_id, exc.reason)
        return ScanResult(scan_id=scan_id, status="failed", failure_reason=exc.reason)
    except Exception:
        logger.exception("Infilra scan failed: scan_id=%s reason=internal_error", scan_id)
        return ScanResult(scan_id=scan_id, status="failed", failure_reason="internal_error")
    finally:
        _cleanup_repo(scan_id)


class CloneError(Exception):
    """Raised when repository cloning fails or times out."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class SemgrepError(Exception):
    """Raised when Semgrep produces no usable JSON output."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _build_clone_url(repo_url: str, github_token: Optional[str]) -> str:
    """Build an authenticated GitHub clone URL without logging the token."""
    if not github_token:
        return repo_url

    parsed = urlparse(repo_url)
    if parsed.hostname != "github.com":
        return repo_url

    netloc = f"x-access-token:{github_token}@github.com"
    return urlunparse(
        (
            parsed.scheme or "https",
            netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def _clone_repo(scan_id: str, repo_url: str, github_token: Optional[str]) -> Path:
    """Shallow-clone the repository into a scan-specific directory."""
    scan_dir = get_scan_dir(scan_id)
    repo_path = get_repo_dir(scan_id)

    if scan_dir.exists():
        shutil.rmtree(scan_dir, ignore_errors=True)

    scan_dir.mkdir(parents=True, exist_ok=True)
    clone_url = _build_clone_url(repo_url, github_token)

    try:
        completed = subprocess.run(
            ["git", "clone", "--depth=1", clone_url, str(repo_path)],
            capture_output=True,
            text=True,
            timeout=CLONE_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise CloneError("clone_timeout")

    if completed.returncode != 0:
        logger.warning(
            "Git clone failed: scan_id=%s exit_code=%s",
            scan_id,
            completed.returncode,
        )
        raise CloneError("clone_failed")

    return repo_path


def _run_semgrep(repo_path: Path) -> dict:
    """Run Semgrep against the cloned repository and return parsed JSON output."""
    command = ["semgrep"]
    for config in SEMGREP_CONFIGS:
        command.extend(["--config", config])
    command.extend(
        [
            "--json",
            f"--timeout={SEMGREP_RULE_TIMEOUT_SEC}",
            str(repo_path),
        ]
    )

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=SEMGREP_SUBPROCESS_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise SemgrepError("semgrep_failed")

    parsed = _parse_semgrep_stdout(completed.stdout)
    if parsed is None:
        logger.warning(
            "Semgrep produced no valid JSON: exit_code=%s",
            completed.returncode,
        )
        raise SemgrepError("semgrep_failed")

    return parsed


def _parse_semgrep_stdout(stdout: str) -> Optional[dict]:
    """Parse Semgrep stdout as JSON, tolerating occasional non-JSON prefix lines."""
    stdout = stdout.strip()
    if not stdout:
        return None

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        for line in reversed(stdout.splitlines()):
            candidate = line.strip()
            if not candidate.startswith("{") or not candidate.endswith("}"):
                continue
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    return None


def _parse_semgrep_results(data: dict) -> list[RawFinding]:
    """Convert Semgrep JSON results into typed RawFinding models."""
    findings: list[RawFinding] = []
    results = data.get("results", [])

    for entry in results:
        extra = entry.get("extra", {})
        start = entry.get("start", {})
        end = entry.get("end", {})
        severity = extra.get("severity", "INFO")

        if severity not in ("ERROR", "WARNING", "INFO"):
            severity = "INFO"

        findings.append(
            RawFinding(
                file=entry.get("path", ""),
                start_line=int(start.get("line", 0)),
                end_line=int(end.get("line", 0)),
                rule_id=entry.get("check_id", ""),
                message=extra.get("message", ""),
                raw_severity=severity,
                code_snippet=extra.get("lines", ""),
            )
        )

    return findings


def _enrich_findings_with_context(
    repo_path: Path, findings: list[RawFinding]
) -> list[RawFinding]:
    """Attach source context to each finding while the cloned repo is still present."""
    return [
        finding.model_copy(update={"context": _extract_context(repo_path, finding)})
        for finding in findings
    ]


def _extract_context(repo_path: Path, finding: RawFinding) -> str:
    """
    Extract surrounding source for a finding from the cloned repository.

    Prefers the containing function/block when detectable; otherwise returns a
    line window around the matched range.
    """
    file_path = _resolve_finding_file(repo_path, finding.file)
    if file_path is None:
        return ""

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    lines = text.splitlines()
    if not lines:
        return ""

    start_line = max(1, finding.start_line)
    end_line = max(start_line, finding.end_line)

    block_bounds = _find_containing_block(lines, start_line, end_line)
    if block_bounds is not None:
        start_idx, end_idx = block_bounds
        return "\n".join(lines[start_idx:end_idx])

    start_idx = max(0, start_line - 1 - CONTEXT_WINDOW_LINES)
    end_idx = min(len(lines), end_line + CONTEXT_WINDOW_LINES)
    return "\n".join(lines[start_idx:end_idx])


def _resolve_finding_file(repo_path: Path, file: str) -> Optional[Path]:
    """Resolve a Semgrep file path to an absolute path inside the cloned repo."""
    if not file:
        return None

    candidates = [
        Path(file),
        repo_path / file,
        repo_path / file.lstrip("./"),
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def _find_containing_block(
    lines: list[str], start_line: int, end_line: int
) -> Optional[tuple[int, int]]:
    """Return 0-based [start, end) line indices for a containing function/block."""
    start_idx = min(max(start_line - 1, 0), len(lines) - 1)
    end_idx = min(max(end_line - 1, 0), len(lines) - 1)

    python_start = _find_python_function_start(lines, start_idx)
    if python_start is not None:
        return (python_start, _find_python_function_end(lines, python_start))

    brace_bounds = _find_brace_block(lines, start_idx)
    if brace_bounds is not None:
        return brace_bounds

    return None


def _find_python_function_start(lines: list[str], idx: int) -> Optional[int]:
    """Walk upward to find a Python ``def`` / ``async def`` line."""
    for line_idx in range(idx, -1, -1):
        stripped = lines[line_idx].lstrip()
        if stripped.startswith("def ") or stripped.startswith("async def "):
            return line_idx
    return None


def _find_python_function_end(lines: list[str], start_idx: int) -> int:
    """Return the line index after the body of a Python function."""
    base_indent = len(lines[start_idx]) - len(lines[start_idx].lstrip())
    line_idx = start_idx + 1

    while line_idx < len(lines):
        line = lines[line_idx]
        if not line.strip():
            line_idx += 1
            continue

        indent = len(line) - len(line.lstrip())
        if indent <= base_indent:
            break
        line_idx += 1

    return line_idx


def _find_brace_block(lines: list[str], idx: int) -> Optional[tuple[int, int]]:
    """Find a brace-delimited block containing the target line."""
    search_start = max(0, idx - 20)

    for line_idx in range(idx, search_start - 1, -1):
        if "{" not in lines[line_idx]:
            continue

        depth = 0
        started = False
        for scan_idx in range(line_idx, len(lines)):
            for char in lines[scan_idx]:
                if char == "{":
                    depth += 1
                    started = True
                elif char == "}":
                    depth -= 1
                    if started and depth == 0:
                        return (line_idx, scan_idx + 1)
        break

    return None


def _summarize_findings(findings: list[RawFinding]) -> str:
    """Build a human-readable severity summary for logging and API responses."""
    error_count = sum(1 for f in findings if f.raw_severity == "ERROR")
    warning_count = sum(1 for f in findings if f.raw_severity == "WARNING")
    info_count = sum(1 for f in findings if f.raw_severity == "INFO")
    total = len(findings)
    return f"{total} findings: {error_count} ERROR, {warning_count} WARNING, {info_count} INFO"


def _cleanup_repo(scan_id: str) -> None:
    """Remove only the cloned repository directory, keeping persisted findings."""
    repo_path = get_repo_dir(scan_id)
    if repo_path.exists():
        try:
            shutil.rmtree(repo_path)
        except OSError:
            logger.warning("Failed to remove cloned repo: scan_id=%s", scan_id)
