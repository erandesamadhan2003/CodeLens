"""Runtime configuration for the Infilra security scan pipeline."""

import os

SCAN_BASE_DIR: str = os.environ.get("SCAN_BASE_DIR", "/tmp/scans")
CLONE_TIMEOUT_SEC: int = int(os.environ.get("CLONE_TIMEOUT_SEC", "60"))
SEMGREP_SUBPROCESS_TIMEOUT_SEC: int = int(os.environ.get("SEMGREP_SUBPROCESS_TIMEOUT_SEC", "180"))
SEMGREP_RULE_TIMEOUT_SEC: int = int(os.environ.get("SEMGREP_RULE_TIMEOUT_SEC", "120"))
SEMGREP_CONFIGS: list[str] = [
    "p/security-audit",
    "p/secrets",
    "p/owasp-top-ten",
]
CONTEXT_WINDOW_LINES: int = int(os.environ.get("CONTEXT_WINDOW_LINES", "10"))
