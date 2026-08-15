"""
security-engine (infilra) — FastAPI HTTP service.
Clones a repository, runs static analysis via pattern matching and Groq AI,
then returns structured security findings.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("security-engine")

# ── Config ────────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/codelens")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

app = FastAPI(title="security-engine")
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=5, command_timeout=30)
    return _pool


# ── Models ────────────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    runId: Optional[str] = None
    scanId: Optional[str] = None
    repoUrl: Optional[str] = None
    cloneUrl: Optional[str] = None
    githubToken: Optional[str] = None
    repoFullName: Optional[str] = None
    branch: Optional[str] = "main"

    @property
    def resolved_run_id(self) -> str:
        return self.runId or self.scanId or str(uuid.uuid4())

    @property
    def resolved_repo_url(self) -> str:
        return self.repoUrl or self.cloneUrl or ""


# ── Security Pattern Scanner ──────────────────────────────────────────────────
SECURITY_PATTERNS = [
    # Secrets
    (r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']{3,}["\']', "Hardcoded Password", "CRITICAL", "secrets"),
    (r'(?i)(api_key|apikey|api-key)\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded API Key", "CRITICAL", "secrets"),
    (r'(?i)(secret|token)\s*=\s*["\'][^"\']{10,}["\']', "Hardcoded Secret/Token", "HIGH", "secrets"),
    (r'(?i)aws_access_key_id\s*=\s*["\']?[A-Z0-9]{20}', "AWS Access Key Exposed", "CRITICAL", "secrets"),
    (r'(?i)private_key\s*=\s*["\']-----BEGIN', "Private Key Exposed", "CRITICAL", "secrets"),
    # Injection
    (r'(?i)eval\s*\(.*\$_(GET|POST|REQUEST|COOKIE)', "Code Injection via eval()", "CRITICAL", "injection"),
    (r'(?i)exec\s*\(.*\$_(GET|POST|REQUEST)', "OS Command Injection", "HIGH", "injection"),
    (r'(?i)sql\s*=.*\+.*input|query\s*=.*\+.*request', "SQL Injection Risk", "HIGH", "injection"),
    (r'(?i)innerHTML\s*=\s*.*\+|document\.write\s*\(.*\+', "XSS via innerHTML", "HIGH", "xss"),
    # Auth
    (r'(?i)verify\s*=\s*false|ssl_verify\s*=\s*false|CURLOPT_SSL_VERIFYPEER.*false', "SSL Verification Disabled", "HIGH", "tls"),
    (r'(?i)md5\s*\(|hashlib\.md5', "Weak Hashing Algorithm (MD5)", "MEDIUM", "cryptography"),
    (r'(?i)sha1\s*\(|hashlib\.sha1', "Weak Hashing Algorithm (SHA1)", "MEDIUM", "cryptography"),
    # Config
    (r'(?i)debug\s*=\s*true|DEBUG\s*=\s*True', "Debug Mode Enabled", "MEDIUM", "config"),
    (r'(?i)allow_origins.*\*|CORS.*origin.*\*', "CORS Wildcard Allowed", "MEDIUM", "config"),
    (r'(?i)http://(?!localhost|127\.|10\.|192\.168)', "Insecure HTTP Usage", "LOW", "tls"),
]

SKIP_DIRS = {'.git', 'node_modules', 'venv', '__pycache__', '.pytest_cache', 'dist', 'build', '.next'}
SCAN_EXTENSIONS = {'.py', '.js', '.ts', '.jsx', '.tsx', '.php', '.rb', '.go', '.java', '.env', '.yml', '.yaml', '.json', '.tf'}


def _scan_file(file_path: Path, base: Path) -> list[dict]:
    findings = []
    rel = str(file_path.relative_to(base))
    try:
        content = file_path.read_text(encoding='utf-8', errors='replace')
        lines = content.splitlines()
        for pattern, title, severity, category in SECURITY_PATTERNS:
            for i, line in enumerate(lines, 1):
                if re.search(pattern, line):
                    snippet = line.strip()[:200]
                    # Get context
                    start = max(0, i - 3)
                    end = min(len(lines), i + 3)
                    context = '\n'.join(f"{start+j+1}: {lines[start+j]}" for j in range(end - start))
                    findings.append({
                        "id": str(uuid.uuid4()),
                        "file": rel,
                        "line": i,
                        "title": title,
                        "severity": severity,
                        "category": category,
                        "snippet": snippet,
                        "context": context,
                        "message": f"{title} detected at {rel}:{i}",
                    })
    except Exception:
        pass
    return findings


def _scan_repository(workspace: str) -> list[dict]:
    """Scan all relevant files in the cloned repository."""
    base = Path(workspace)
    all_findings = []
    file_count = 0

    for item in base.rglob("*"):
        if item.is_dir():
            continue
        if any(part in SKIP_DIRS for part in item.parts):
            continue
        if item.suffix.lower() not in SCAN_EXTENSIONS and item.name not in {'.env', '.env.example'}:
            continue
        if item.stat().st_size > 500_000:  # skip files > 500KB
            continue
        all_findings.extend(_scan_file(item, base))
        file_count += 1
        if file_count > 200:  # cap at 200 files
            break

    return all_findings


def _clone_repo(run_id: str, repo_url: str, github_token: Optional[str]) -> str:
    """Shallow clone the repository and return the workspace path."""
    workspace = tempfile.mkdtemp(prefix=f"security-{run_id}-")
    clone_url = repo_url
    if github_token and "github.com" in repo_url:
        clone_url = repo_url.replace("https://", f"https://x-access-token:{github_token}@")
    
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, workspace],
            timeout=120,
            capture_output=True,
            check=True,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(workspace, ignore_errors=True)
        raise RuntimeError("Repository clone timed out")
    except subprocess.CalledProcessError as e:
        shutil.rmtree(workspace, ignore_errors=True)
        raise RuntimeError(f"Clone failed: {e.stderr.decode()[:200]}")
    
    return workspace


async def _get_ai_summary(findings: list[dict]) -> Optional[str]:
    """Use Groq to generate a plain-English security summary."""
    if not GROQ_API_KEY or not findings:
        return None
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_API_KEY, timeout=15.0)
        critical = [f for f in findings if f["severity"] == "CRITICAL"]
        high = [f for f in findings if f["severity"] == "HIGH"]
        sample = (critical + high)[:5]
        sample_text = "\n".join(f"- [{f['severity']}] {f['title']} in {f['file']}:{f['line']}" for f in sample)
        
        resp = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{
                "role": "user",
                "content": f"""Analyze these security findings and provide a brief, actionable summary (3-4 sentences):
{sample_text}
Total: {len(findings)} findings ({len(critical)} critical, {len(high)} high)
Focus on the most critical risks and immediate actions needed."""
            }],
            max_tokens=300,
            temperature=0.3,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.warning(f"AI summary failed: {e}")
        return None


async def _persist_results(run_id: str, result: dict) -> None:
    """Persist security findings to engine_results."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO engine_results (id, run_id, engine, status, result_data, completed_at)
                VALUES ($1, $2, 'infilra', 'completed', $3::jsonb, NOW())
                ON CONFLICT (run_id, engine) DO UPDATE
                SET status = 'completed', result_data = $3::jsonb, completed_at = NOW()
                """,
                str(uuid.uuid4()), run_id, json.dumps(result)
            )
            await conn.execute(
                """
                UPDATE analysis_runs 
                SET engines_completed = array_append(engines_completed, 'infilra'::engine_name_enum)
                WHERE id = $1 AND NOT ('infilra'::engine_name_enum = ANY(engines_completed))
                """,
                run_id
            )
    except Exception as e:
        logger.error(f"Failed to persist results: {e}")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "service": "security-engine"}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    run_id = req.resolved_run_id
    repo_url = req.resolved_repo_url
    start = time.monotonic()

    logger.info(f"Security scan started: runId={run_id} repo={repo_url}")

    if not repo_url:
        return JSONResponse({"status": "failed", "error": "repoUrl is required"}, status_code=400)

    workspace = None
    try:
        workspace = _clone_repo(run_id, repo_url, req.githubToken)
        findings = _scan_repository(workspace)
        
        # Get AI summary async
        ai_summary = await _get_ai_summary(findings)

        # Compute severity counts
        sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
        for f in findings:
            sev_counts[f.get("severity", "LOW")] = sev_counts.get(f.get("severity", "LOW"), 0) + 1

        # Score: start at 100, deduct per severity
        score = 100
        score -= sev_counts["CRITICAL"] * 20
        score -= sev_counts["HIGH"] * 10
        score -= sev_counts["MEDIUM"] * 3
        score -= sev_counts["LOW"] * 1
        score = max(0, score)

        duration_ms = int((time.monotonic() - start) * 1000)
        result = {
            "status": "completed",
            "runId": run_id,
            "findingsCount": len(findings),
            "findings": findings,
            "severityCounts": sev_counts,
            "securityScore": score,
            "aiSummary": ai_summary,
            "durationMs": duration_ms,
        }

        await _persist_results(run_id, result)
        logger.info(f"Security scan complete: runId={run_id} findings={len(findings)} score={score}")
        return JSONResponse(result)

    except Exception as e:
        logger.exception(f"Security scan failed: runId={run_id} error={e}")
        return JSONResponse({"status": "failed", "error": str(e), "runId": run_id}, status_code=500)
    finally:
        if workspace:
            shutil.rmtree(workspace, ignore_errors=True)
