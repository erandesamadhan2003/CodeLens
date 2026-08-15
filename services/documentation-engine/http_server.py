"""
http_server.py — FastAPI HTTP endpoint for documentation-engine.
The gateway's docryx.worker.js calls POST /analyze.
This file wraps the core doc analysis logic as a synchronous HTTP service.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

import asyncpg
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("documentation-engine-http")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/codelens")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

app = FastAPI(title="documentation-engine")
_pool: Optional[asyncpg.Pool] = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=DATABASE_URL, min_size=1, max_size=5)
    return _pool


class AnalyzeRequest(BaseModel):
    runId: Optional[str] = None
    repoUrl: Optional[str] = None
    cloneUrl: Optional[str] = None
    githubToken: Optional[str] = None
    repoFullName: Optional[str] = None

    @property
    def run_id(self) -> str:
        return self.runId or str(uuid.uuid4())

    @property
    def repo_url(self) -> str:
        return self.repoUrl or self.cloneUrl or ""


def _clone(run_id: str, repo_url: str, token: Optional[str]) -> str:
    workspace = tempfile.mkdtemp(prefix=f"docryx-{run_id}-")
    url = repo_url
    if token and "github.com" in repo_url:
        url = repo_url.replace("https://", f"https://x-access-token:{token}@")
    subprocess.run(["git", "clone", "--depth", "1", url, workspace], timeout=120, capture_output=True, check=True)
    return workspace


SKIP = {'.git', 'node_modules', 'venv', '__pycache__', 'dist', 'build'}

def _analyse_workspace(workspace: str) -> dict:
    base = Path(workspace)
    
    # Presence checks
    has_readme = any(base.glob("README*"))
    has_license = any(base.glob("LICENSE*"))
    has_contributing = any(base.glob("CONTRIBUTING*"))
    has_changelog = any(base.glob("CHANGELOG*"))
    has_docs_folder = (base / "docs").exists() or (base / "doc").exists()
    has_env_example = (base / ".env.example").exists() or (base / ".env.sample").exists()
    has_api_docs = any(base.glob("**/openapi*")) or any(base.glob("**/swagger*"))
    has_pr_template = (base / ".github" / "pull_request_template.md").exists()
    has_issue_template = (base / ".github" / "ISSUE_TEMPLATE").exists()
    has_codeowners = (base / ".github" / "CODEOWNERS").exists()
    has_ci_config = (base / ".github" / "workflows").exists() or (base / ".travis.yml").exists() or (base / "Jenkinsfile").exists()
    has_arch_doc = any(base.glob("**/ARCHITECTURE*")) or any(base.glob("**/architecture*"))

    # Code comment ratio + functions without docstrings
    total_lines = 0
    comment_lines = 0
    fn_count = 0
    fn_with_doc = 0
    missing_docs = []
    files_analyzed = 0

    for f in base.rglob("*.py"):
        if any(p in SKIP for p in f.parts): continue
        try:
            lines = f.read_text(errors="replace").splitlines()
            total_lines += len(lines)
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                    comment_lines += 1
            # Simple function detection
            for i, line in enumerate(lines):
                if line.strip().startswith("def "):
                    fn_count += 1
                    # Check if next non-empty line is docstring
                    for j in range(i+1, min(i+4, len(lines))):
                        nxt = lines[j].strip()
                        if nxt.startswith('"""') or nxt.startswith("'''"):
                            fn_with_doc += 1
                            break
                        elif nxt:
                            rel = str(f.relative_to(base))
                            if len(missing_docs) < 20:
                                fn_name = line.strip().split("(")[0].replace("def ", "")
                                missing_docs.append({"file": rel, "function": fn_name, "line": i+1})
                            break
            files_analyzed += 1
        except Exception:
            pass

    comment_ratio = round(comment_lines / total_lines, 3) if total_lines > 0 else 0
    doc_fn_ratio = round(fn_with_doc / fn_count, 3) if fn_count > 0 else 1.0

    # Score
    score = 0
    if has_readme: score += 25
    if has_license: score += 10
    if has_contributing: score += 5
    if has_docs_folder: score += 10
    if has_changelog: score += 5
    if has_env_example: score += 5
    if has_ci_config: score += 10
    if has_codeowners: score += 5
    score += int(comment_ratio * 15)
    score += int(doc_fn_ratio * 10)
    score = min(100, score)

    grade_map = [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "F")]
    grade = next(g for threshold, g in grade_map if score >= threshold)

    # Team readiness
    team_score = 0
    if has_readme: team_score += 20
    if has_contributing: team_score += 20
    if has_pr_template: team_score += 15
    if has_issue_template: team_score += 15
    if has_codeowners: team_score += 15
    if has_ci_config: team_score += 15
    team_grade_map = [(80, "A"), (60, "B"), (40, "C"), (20, "D"), (0, "F")]
    team_grade = next(g for t, g in team_grade_map if team_score >= t)

    findings = []
    if not has_readme:
        findings.append({"type": "missing", "severity": "HIGH", "message": "No README file found", "recommendation": "Add a README.md with setup instructions, usage, and description"})
    if not has_license:
        findings.append({"type": "missing", "severity": "MEDIUM", "message": "No LICENSE file found", "recommendation": "Add an appropriate open source license"})
    if not has_contributing:
        findings.append({"type": "missing", "severity": "LOW", "message": "No CONTRIBUTING.md found", "recommendation": "Add contribution guidelines for collaborators"})
    if comment_ratio < 0.1:
        findings.append({"type": "quality", "severity": "MEDIUM", "message": f"Low code comment ratio: {comment_ratio:.1%}", "recommendation": "Add inline comments explaining complex logic"})
    if doc_fn_ratio < 0.5 and fn_count > 0:
        findings.append({"type": "quality", "severity": "MEDIUM", "message": f"Only {doc_fn_ratio:.0%} of functions have docstrings ({fn_with_doc}/{fn_count})", "recommendation": "Add docstrings to Python functions"})
    if not has_env_example:
        findings.append({"type": "missing", "severity": "LOW", "message": "No .env.example file", "recommendation": "Add .env.example to document required environment variables"})

    return {
        "status": "completed",
        "hasReadme": has_readme,
        "readmeScore": 80 if has_readme else 0,
        "hasLicense": has_license,
        "hasContributing": has_contributing,
        "hasChangelog": has_changelog,
        "hasDocs": has_docs_folder,
        "hasApiDocs": has_api_docs,
        "hasEnvExample": has_env_example,
        "hasPrTemplate": has_pr_template,
        "hasIssueTemplate": has_issue_template,
        "hasCodeowners": has_codeowners,
        "hasCiConfig": has_ci_config,
        "hasArchDoc": has_arch_doc,
        "codeCommentRatio": comment_ratio,
        "docFunctionRatio": doc_fn_ratio,
        "functionsWithoutDocstring": fn_count - fn_with_doc,
        "filesAnalyzed": files_analyzed,
        "missingDocsCount": len(missing_docs),
        "missingDocs": missing_docs,
        "overallScore": score,
        "grade": grade,
        "teamReadinessScore": team_score,
        "teamReadinessGrade": team_grade,
        "findings": findings,
        "aiSummary": None,
        "aiStatus": "skipped",
    }


async def _get_ai_summary(analysis: dict) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        from groq import AsyncGroq
        client = AsyncGroq(api_key=GROQ_API_KEY, timeout=10.0)
        resp = await client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": f"""Summarize this repository's documentation quality in 2-3 sentences:
Score: {analysis['overallScore']}/100 (Grade: {analysis['grade']})
Has README: {analysis['hasReadme']}, Has License: {analysis['hasLicense']}, Has Contributing: {analysis['hasContributing']}
Code comment ratio: {analysis['codeCommentRatio']:.1%}, Functions with docstrings: {analysis['docFunctionRatio']:.0%}
Key issues: {', '.join(f['message'] for f in analysis['findings'][:3]) or 'None'}
Be specific and actionable."""}],
            max_tokens=200,
        )
        return resp.choices[0].message.content
    except Exception as e:
        logger.warning(f"AI summary failed: {e}")
        return None


async def _persist(run_id: str, result: dict):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO engine_results (id, run_id, engine, status, result_data, completed_at)
                   VALUES ($1, $2, 'docryx', 'completed', $3::jsonb, NOW())
                   ON CONFLICT (run_id, engine) DO UPDATE SET status='completed', result_data=$3::jsonb, completed_at=NOW()""",
                str(uuid.uuid4()), run_id, json.dumps(result)
            )
            await conn.execute(
                """UPDATE analysis_runs SET engines_completed = array_append(engines_completed, 'docryx'::engine_name_enum)
                   WHERE id = $1 AND NOT ('docryx'::engine_name_enum = ANY(engines_completed))""",
                run_id
            )
    except Exception as e:
        logger.error(f"Persist failed: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "documentation-engine"}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    run_id = req.run_id
    repo_url = req.repo_url
    logger.info(f"Doc scan started: runId={run_id} repo={repo_url}")

    if not repo_url:
        return JSONResponse({"status": "failed", "error": "repoUrl required"}, status_code=400)

    workspace = None
    try:
        workspace = _clone(run_id, repo_url, req.githubToken)
        result = _analyse_workspace(workspace)
        
        # AI summary
        ai_summary = await _get_ai_summary(result)
        if ai_summary:
            result["aiSummary"] = ai_summary
            result["aiStatus"] = "completed"

        result["runId"] = run_id
        await _persist(run_id, result)
        logger.info(f"Doc scan complete: runId={run_id} score={result['overallScore']} grade={result['grade']}")
        return JSONResponse(result)

    except Exception as e:
        logger.exception(f"Doc scan failed: {e}")
        return JSONResponse({"status": "failed", "error": str(e), "runId": run_id}, status_code=500)
    finally:
        if workspace:
            shutil.rmtree(workspace, ignore_errors=True)
