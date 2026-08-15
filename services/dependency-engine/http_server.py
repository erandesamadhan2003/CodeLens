"""
http_server.py — FastAPI HTTP wrapper for dependency-engine (depra).
Exposes POST /analyze for the API Gateway worker to call.
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
from typing import Optional

import asyncpg
import httpx
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("dependency-engine-http")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/codelens")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
OSV_BATCH_URL = "https://api.osv.dev/v1/querybatch"

app = FastAPI(title="dependency-engine")
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

    @property
    def run_id(self) -> str:
        return self.runId or str(uuid.uuid4())

    @property
    def repo_url(self) -> str:
        return self.repoUrl or self.cloneUrl or ""


# ── Parsers ───────────────────────────────────────────────────────────────────
_VER_RE = re.compile(r'^[^0-9a-zA-Z*]*')
_REQ_LINE = re.compile(r'^\s*([A-Za-z0-9_\-\.]+)(?:\s*[><=!~^]+\s*([^\s;#,]+))?')


def _parse_package_json(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text())
        deps = {}
        for key in ("dependencies", "devDependencies"):
            for name, ver in (data.get(key) or {}).items():
                deps[name] = _VER_RE.sub("", ver).strip() or "unknown"
        return deps
    except Exception:
        return {}


def _parse_requirements_txt(path: Path) -> dict[str, str]:
    deps = {}
    try:
        for line in path.read_text(errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            m = _REQ_LINE.match(line)
            if m:
                deps[m.group(1)] = m.group(2) or "unknown"
    except Exception:
        pass
    return deps


def _discover_manifests(workspace: str) -> list[dict]:
    base = Path(workspace)
    skip = {'node_modules', 'venv', '__pycache__', '.git'}
    manifests = []
    for f in base.rglob("*"):
        if any(p in skip for p in f.parts):
            continue
        if f.name == "package.json":
            deps = _parse_package_json(f)
            if deps:
                manifests.append({"file": str(f.relative_to(base)), "ecosystem": "npm", "deps": deps})
        elif f.name in ("requirements.txt", "requirements-dev.txt"):
            deps = _parse_requirements_txt(f)
            if deps:
                manifests.append({"file": str(f.relative_to(base)), "ecosystem": "PyPI", "deps": deps})
    return manifests


# ── OSV.dev batch query ───────────────────────────────────────────────────────
async def _query_osv(packages: list[dict]) -> dict[str, dict]:
    """Query OSV.dev for vulnerabilities. Returns {name: vuln_info}."""
    if not packages:
        return {}
    queries = [{"package": {"name": p["name"], "ecosystem": p["ecosystem"]}} for p in packages]
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(OSV_BATCH_URL, json={"queries": queries})
            resp.raise_for_status()
            results = resp.json().get("results", [])
    except Exception as e:
        logger.warning(f"OSV.dev query failed: {e}")
        return {}

    vuln_map = {}
    for pkg, res in zip(packages, results):
        vulns = res.get("vulns", [])
        if vulns:
            v = vulns[0]
            # Determine severity from CVSS
            severity = "UNKNOWN"
            score = None
            for sev in v.get("severity", []):
                if sev.get("type") == "CVSS_V3":
                    try:
                        score = float(sev.get("score", 0))
                        if score >= 9.0: severity = "CRITICAL"
                        elif score >= 7.0: severity = "HIGH"
                        elif score >= 4.0: severity = "MEDIUM"
                        else: severity = "LOW"
                    except Exception:
                        pass
            fix_version = None
            for affected in v.get("affected", []):
                for rng in affected.get("ranges", []):
                    for ev in rng.get("events", []):
                        if "fixed" in ev:
                            fix_version = ev["fixed"]
                            break
            vuln_map[pkg["name"]] = {
                "id": v.get("id", ""),
                "summary": v.get("summary", ""),
                "severity": severity,
                "cvssScore": score,
                "fixVersion": fix_version,
                "vulnCount": len(vulns),
                "aliases": v.get("aliases", [])[:3],
            }
    return vuln_map


async def _persist(run_id: str, result: dict):
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO engine_results (id, run_id, engine, status, result_data, completed_at)
                   VALUES ($1, $2, 'depra', 'completed', $3::jsonb, NOW())
                   ON CONFLICT (run_id, engine) DO UPDATE SET status='completed', result_data=$3::jsonb, completed_at=NOW()""",
                str(uuid.uuid4()), run_id, json.dumps(result)
            )
            await conn.execute(
                """UPDATE analysis_runs SET engines_completed = array_append(engines_completed, 'depra'::engine_name_enum)
                   WHERE id = $1 AND NOT ('depra'::engine_name_enum = ANY(engines_completed))""",
                run_id
            )
    except Exception as e:
        logger.error(f"Persist failed: {e}")


@app.get("/health")
def health():
    return {"status": "ok", "service": "dependency-engine"}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    run_id = req.run_id
    repo_url = req.repo_url
    logger.info(f"Dependency scan started: runId={run_id} repo={repo_url}")

    if not repo_url:
        return JSONResponse({"status": "failed", "error": "repoUrl required"}, status_code=400)

    workspace = None
    try:
        workspace = tempfile.mkdtemp(prefix=f"depra-{run_id}-")
        clone_url = repo_url
        if req.githubToken and "github.com" in repo_url:
            clone_url = repo_url.replace("https://", f"https://x-access-token:{req.githubToken}@")
        subprocess.run(["git", "clone", "--depth", "1", clone_url, workspace], timeout=120, capture_output=True, check=True)

        manifests = _discover_manifests(workspace)

        # Collect all unique packages
        all_packages = []
        for m in manifests:
            for name in m["deps"]:
                all_packages.append({"name": name, "ecosystem": m["ecosystem"]})

        # OSV query
        vuln_map = await _query_osv(all_packages[:100])  # cap at 100

        # Build dependency list
        all_deps = []
        for m in manifests:
            for name, version in m["deps"].items():
                vuln = vuln_map.get(name)
                dep = {
                    "name": name,
                    "version": version,
                    "ecosystem": m["ecosystem"],
                    "file": m["file"],
                    "vulnerable": vuln is not None,
                    "vuln": vuln,
                }
                all_deps.append(dep)

        # Stats
        vulnerable = [d for d in all_deps if d["vulnerable"]]
        sev_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "UNKNOWN": 0}
        for d in vulnerable:
            sev = d["vuln"].get("severity", "UNKNOWN") if d["vuln"] else "UNKNOWN"
            sev_counts[sev] = sev_counts.get(sev, 0) + 1

        risk_score = 100
        risk_score -= sev_counts["CRITICAL"] * 25
        risk_score -= sev_counts["HIGH"] * 15
        risk_score -= sev_counts["MEDIUM"] * 5
        risk_score -= sev_counts["LOW"] * 2
        risk_score = max(0, risk_score)

        ecosystems = {}
        for d in all_deps:
            eco = d["ecosystem"]
            ecosystems[eco] = ecosystems.get(eco, 0) + 1

        result = {
            "status": "completed",
            "runId": run_id,
            "totalDependencies": len(all_deps),
            "vulnerableCount": len(vulnerable),
            "riskScore": risk_score,
            "severityCounts": sev_counts,
            "ecosystems": ecosystems,
            "manifests": [{"file": m["file"], "ecosystem": m["ecosystem"], "count": len(m["deps"])} for m in manifests],
            "dependencies": all_deps[:200],  # cap for DB storage
        }

        await _persist(run_id, result)
        logger.info(f"Dependency scan complete: runId={run_id} total={len(all_deps)} vulnerable={len(vulnerable)}")
        return JSONResponse(result)

    except Exception as e:
        logger.exception(f"Dependency scan failed: {e}")
        return JSONResponse({"status": "failed", "error": str(e), "runId": run_id}, status_code=500)
    finally:
        if workspace:
            shutil.rmtree(workspace, ignore_errors=True)
