"""
main.py — Single-file BullMQ worker microservice for dependency-engine (depra).

Consolidates all logic (config, db, parser, OSV.dev client, caching, worker):
  1. Shallow-clones repo (depth=1).
  2. Parses manifests directly from disk (package.json / requirements.txt) — no package managers.
  3. Checks local Postgres vuln_cache first.
  4. Batch-queries OSV.dev for missing packages in a single HTTP POST.
  5. Degrades gracefully to status="unchecked" if OSV.dev or network fails.
  6. Upserts fresh OSV findings to Postgres vuln_cache.
  7. Persists dependency_reports + updates engine_results status in shared DB.
  8. Returns results for BullMQ -> api-gateway -> Socket.io relay.
"""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
import os
import re
import signal
import shutil
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import asyncpg
from bullmq import Job, Worker
import git
import httpx
from groq import AsyncGroq

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dependency-engine")

# ── 1. CONFIGURATION ──────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/codelens")
QUEUE_NAME: str = os.getenv("QUEUE_NAME", "dependency-engine")
WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
OSV_BATCH_URL: str = "https://api.osv.dev/v1/querybatch"
OSV_TIMEOUT_SECONDS: int = 10
ENGINE_NAME: str = "depra"
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_TIMEOUT_SECONDS: float = 8.0
GROQ_MODEL: str = "llama-3.3-70b-versatile"

groq_client: AsyncGroq | None = (
    AsyncGroq(api_key=GROQ_API_KEY, timeout=GROQ_TIMEOUT_SECONDS) if GROQ_API_KEY else None
)

# ── 2. DATABASE POOL (asyncpg) ────────────────────────────────────────────────
pool: asyncpg.Pool | None = None


async def init_pool() -> None:
    global pool
    pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


async def close_pool() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None


# ── 3. MANIFEST PARSING ───────────────────────────────────────────────────────
_VERSION_PREFIX_RE = re.compile(r"^[^0-9a-zA-Z*]*")
_REQUIREMENTS_LINE_RE = re.compile(r"^\s*([A-Za-z0-9_\-\.]+)(?:\s*[><=!~^]+\s*([^\s;#,]+))?")


def _strip_version_prefix(raw: str) -> str:
    cleaned = _VERSION_PREFIX_RE.sub("", raw).strip()
    return cleaned if cleaned else "unknown"


def parse_package_json(path: Path) -> Optional[dict[str, str]]:
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
    except Exception:  # noqa: BLE001
        return None

    deps: dict[str, str] = {}
    for section in ("dependencies", "devDependencies"):
        for name, version_raw in (data.get(section) or {}).items():
            if isinstance(version_raw, str):
                deps[name] = _strip_version_prefix(version_raw)

    return deps


def parse_requirements_txt(path: Path) -> Optional[dict[str, str]]:
    if not path.exists():
        return None
    deps: dict[str, str] = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except Exception:  # noqa: BLE001
        return None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split("#")[0].strip()
        m = _REQUIREMENTS_LINE_RE.match(line)
        if m:
            deps[m.group(1)] = (m.group(2) or "").strip() or "unknown"

    return deps


class ParsedManifests:
    def __init__(self) -> None:
        self.npm: dict[str, str] = {}
        self.pypi: dict[str, str] = {}

    @property
    def found_any(self) -> bool:
        return bool(self.npm or self.pypi)


def find_and_parse_manifests(repo_root: Path) -> ParsedManifests:
    result = ParsedManifests()
    npm_deps = parse_package_json(repo_root / "package.json")
    if npm_deps is not None:
        result.npm = npm_deps
    pypi_deps = parse_requirements_txt(repo_root / "requirements.txt")
    if pypi_deps is not None:
        result.pypi = pypi_deps
    return result


# ── 4. OSV.dev BATCH CLIENT ───────────────────────────────────────────────────
def _extract_severity(vuln: dict) -> Optional[str]:
    db_specific = vuln.get("database_specific") or {}
    if db_specific.get("severity"):
        return str(db_specific["severity"]).upper()
    return None


def _extract_fixed_version(vuln: dict) -> Optional[str]:
    for affected in vuln.get("affected") or []:
        for rng in affected.get("ranges") or []:
            for event in rng.get("events") or []:
                if "fixed" in event:
                    return event["fixed"]
    return None


def _normalise_vulns(raw_vulns: list[dict]) -> list[dict]:
    normalised = []
    for vuln in raw_vulns:
        normalised.append({
            "id": vuln.get("id", "UNKNOWN"),
            "severity": _extract_severity(vuln),
            "fixed_version": _extract_fixed_version(vuln),
        })
    return normalised


async def batch_query_osv(queries: list[tuple[str, str, str]]) -> Optional[list[list[dict]]]:
    if not queries:
        return []

    payload = {
        "queries": [
            {
                "version": version,
                "package": {"name": name, "ecosystem": ecosystem},
            }
            for name, version, ecosystem in queries
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=OSV_TIMEOUT_SECONDS) as client:
            response = await client.post(OSV_BATCH_URL, json=payload)
            response.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        logger.warning("OSV.dev request error: %s", exc)
        return None

    data = response.json()
    batch_results = data.get("results", [])

    while len(batch_results) < len(queries):
        batch_results.append({})

    unique_ids = set()
    for item in batch_results:
        for vuln in item.get("vulns", []):
            vid = vuln.get("id")
            if vid:
                unique_ids.add(vid)

    sem = asyncio.Semaphore(8)

    async def fetch_vuln(vuln_id: str) -> tuple[str, dict]:
        async with sem, httpx.AsyncClient(timeout=OSV_TIMEOUT_SECONDS) as client:
            try:
                r = await client.get(f"https://api.osv.dev/v1/vulns/{vuln_id}")
                r.raise_for_status()
                return vuln_id, r.json()
            except Exception as e:
                logger.warning("Failed to hydrate vuln %s: %s", vuln_id, e)
                return vuln_id, {"id": vuln_id}

    if unique_ids:
        hydrated = dict(await asyncio.gather(*(fetch_vuln(vid) for vid in unique_ids)))
    else:
        hydrated = {}

    results: list[list[dict]] = []
    for item in batch_results:
        hydrated_vulns = []
        for vuln in item.get("vulns", []):
            vid = vuln.get("id")
            if vid and vid in hydrated:
                hydrated_vulns.append(hydrated[vid])
        results.append(_normalise_vulns(hydrated_vulns))

    return results


# ── 5. VULNERABILITY CACHE & LOOKUP ───────────────────────────────────────────
async def lookup_vulnerabilities(packages: list[tuple[str, str, str]]) -> dict[str, Any]:
    if not packages:
        return {}

    result: dict[str, Any] = {}
    cache_hits, cache_misses = await _check_cache(packages)

    for (name, version, ecosystem), data in cache_hits.items():
        result[f"{name}@{version}"] = data

    if cache_misses:
        miss_list = list(cache_misses)
        osv_results = await batch_query_osv(miss_list)

        if osv_results is None:
            logger.warning("OSV.dev unavailable; marking %d packages unchecked", len(miss_list))
            for name, version, ecosystem in miss_list:
                result[f"{name}@{version}"] = {
                    "status": "unchecked",
                    "source": "unavailable",
                    "ecosystem": ecosystem,
                }
        else:
            to_cache: list[tuple] = []
            for (name, version, ecosystem), vulns in zip(miss_list, osv_results):
                result[f"{name}@{version}"] = {
                    "vulnerabilities": vulns,
                    "source": "osv",
                    "ecosystem": ecosystem,
                }
                to_cache.append((name, version, ecosystem, vulns))
            await _save_to_cache(to_cache)

    return result


async def _check_cache(packages: list[tuple[str, str, str]]) -> tuple[dict, set]:
    hits: dict = {}
    misses: set = set(packages)
    if pool is None:
        return hits, misses

    try:
        names = [p[0] for p in packages]
        versions = [p[1] for p in packages]
        ecosystems = [p[2] for p in packages]

        rows = await pool.fetch(
            """
            SELECT package, version, ecosystem, vulnerabilities
            FROM   vuln_cache
            WHERE  (package, version, ecosystem) IN (
                SELECT * FROM unnest($1::text[], $2::text[], $3::text[])
            )
            """,
            names, versions, ecosystems,
        )

        for row in rows:
            key = (row["package"], row["version"], row["ecosystem"])
            vulns = row["vulnerabilities"]
            if isinstance(vulns, str):
                vulns = json.loads(vulns)
            hits[key] = {
                "vulnerabilities": vulns,
                "source": "cache",
                "ecosystem": row["ecosystem"],
            }
            misses.discard(key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cache lookup failed: %s", exc)

    return hits, misses


async def _save_to_cache(rows: list[tuple[str, str, str, list]]) -> None:
    if not rows or pool is None:
        return
    try:
        now = datetime.datetime.utcnow()
        records = [
            (name, version, ecosystem, json.dumps(vulns), "osv", now)
            for name, version, ecosystem, vulns in rows
        ]
        await pool.executemany(
            """
            INSERT INTO vuln_cache (package, version, ecosystem, vulnerabilities, source, checked_at)
            VALUES ($1, $2, $3, $4::jsonb, $5, $6)
            ON CONFLICT (package, version, ecosystem)
            DO UPDATE SET
                vulnerabilities = EXCLUDED.vulnerabilities,
                source          = 'osv',
                checked_at      = EXCLUDED.checked_at
            """,
            records,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to save to vuln_cache: %s", exc)


# ── 6. WORKER PROCESSOR & SCAN RUNNER ─────────────────────────────────────────
async def process_job(job: Job, job_token: str) -> dict[str, Any]:
    data = job.data or {}
    repo_url = data.get("repoUrl", "")
    scan_id = data.get("scanId", "")
    triggered_by = data.get("triggeredBy", "manual")

    logger.info("Processing job %s — repo=%s scanId=%s", job.id, repo_url, scan_id)

    start_ts = datetime.datetime.utcnow()
    started_ms = time.monotonic()

    await _mark_engine(scan_id, "running", started_at=start_ts)

    try:
        result = await _run_scan(repo_url, scan_id, triggered_by)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in job %s: %s", job.id, exc)
        result = {"error": str(exc)}

    duration_ms = int((time.monotonic() - started_ms) * 1000)
    await _persist_results(scan_id, result, start_ts, duration_ms)

    logger.info("Job %s finished — scanId=%s (%dms)", job.id, scan_id, duration_ms)
    return result


async def _run_scan(repo_url: str, scan_id: str, triggered_by: str) -> dict[str, Any]:
    tmp_dir = tempfile.mkdtemp(prefix="dep-engine-")
    try:
        try:
            await asyncio.to_thread(git.Repo.clone_from, repo_url, tmp_dir, depth=1)
        except git.exc.GitCommandError as exc:
            logger.error("Clone failed: %s", exc)
            return {"error": f"clone_failed: {exc}"}

        manifests = find_and_parse_manifests(Path(tmp_dir))
        if not manifests.found_any:
            return {
                "skipped": True,
                "reason": "no supported manifest found",
                "run_id": scan_id,
                "triggered_by": triggered_by,
            }

        packages: list[tuple[str, str, str]] = []
        ecosystems: set[str] = set()
        for name, version in manifests.npm.items():
            packages.append((name, version, "npm"))
            ecosystems.add("npm")
        for name, version in manifests.pypi.items():
            packages.append((name, version, "PyPI"))
            ecosystems.add("PyPI")

        logger.info("Found %d npm + %d PyPI deps", len(manifests.npm), len(manifests.pypi))

        vuln_results = await lookup_vulnerabilities(packages)
        summary = _summary(vuln_results)
        cve_details = _cve_list(vuln_results)
        text_summary = await generate_text_summary(summary, cve_details)

        return {
            "run_id": scan_id,
            "repo_url": repo_url,
            "triggered_by": triggered_by,
            "scanned_at": datetime.datetime.utcnow().isoformat(),
            "ecosystems": sorted(ecosystems),
            "summary": summary,
            "dependencies": vuln_results,
            "cve_details": cve_details,
            "text_summary": text_summary,
        }
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def _persist_results(
    scan_id: str,
    result: dict[str, Any],
    started_at: datetime.datetime,
    duration_ms: int,
) -> None:
    if pool is None:
        return

    is_error = "error" in result
    completed_at = datetime.datetime.utcnow()

    try:
        run_uuid = str(uuid.UUID(scan_id)) if scan_id else str(uuid.uuid4())
    except ValueError:
        return

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if not is_error:
                    summary = result.get("summary", {})
                    deps = result.get("dependencies", {})
                    cve_list = result.get("cve_details", [])
                    ecosystems = result.get("ecosystems", [])

                    deps_list = [
                        {"package_at_version": k, **v}
                        for k, v in (deps.items() if isinstance(deps, dict) else [])
                    ]

                    await conn.execute(
                        """
                        INSERT INTO dependency_reports
                            (id, run_id, total_dependencies, vulnerable_count,
                             outdated_count, critical_cves, ecosystems,
                             dependencies, cve_details, text_summary, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb, $10, $11)
                        ON CONFLICT (run_id) DO UPDATE SET
                            total_dependencies = EXCLUDED.total_dependencies,
                            vulnerable_count   = EXCLUDED.vulnerable_count,
                            critical_cves      = EXCLUDED.critical_cves,
                            ecosystems         = EXCLUDED.ecosystems,
                            dependencies       = EXCLUDED.dependencies,
                            cve_details        = EXCLUDED.cve_details,
                            text_summary       = EXCLUDED.text_summary
                        """,
                        str(uuid.uuid4()),
                        run_uuid,
                        summary.get("total", 0),
                        summary.get("vulnerable", 0),
                        0,
                        _count_critical(cve_list),
                        ecosystems,
                        json.dumps(deps_list),
                        json.dumps(cve_list),
                        result.get("text_summary"),
                        completed_at,
                    )

                final_status = "failed" if is_error else "completed"
                error_msg = result.get("error") if is_error else None

                await conn.execute(
                    """
                    INSERT INTO engine_results
                        (id, run_id, engine, status, result_data,
                         error_message, duration_ms, started_at, completed_at)
                    VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9)
                    ON CONFLICT (run_id, engine) DO UPDATE SET
                        status        = EXCLUDED.status,
                        result_data   = EXCLUDED.result_data,
                        error_message = EXCLUDED.error_message,
                        duration_ms   = EXCLUDED.duration_ms,
                        completed_at  = EXCLUDED.completed_at
                    """,
                    str(uuid.uuid4()),
                    run_uuid,
                    ENGINE_NAME,
                    final_status,
                    json.dumps(result),
                    error_msg,
                    duration_ms,
                    started_at,
                    completed_at,
                )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to persist results: %s", exc)


async def _mark_engine(scan_id: str, status: str, started_at: datetime.datetime | None = None) -> None:
    if pool is None:
        return
    try:
        run_uuid = str(uuid.UUID(scan_id)) if scan_id else str(uuid.uuid4())
    except ValueError:
        return
    try:
        await pool.execute(
            """
            INSERT INTO engine_results (id, run_id, engine, status, started_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (run_id, engine) DO UPDATE SET
                status     = EXCLUDED.status,
                started_at = EXCLUDED.started_at
            """,
            str(uuid.uuid4()), run_uuid, ENGINE_NAME, status, started_at,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to mark engine status: %s", exc)


def _summary(vuln_results: dict[str, Any]) -> dict[str, int]:
    vulnerable = unchecked = clean = 0
    for info in vuln_results.values():
        if info.get("status") == "unchecked":
            unchecked += 1
        elif info.get("vulnerabilities"):
            vulnerable += 1
        else:
            clean += 1
    return {"total": len(vuln_results), "vulnerable": vulnerable, "clean": clean, "unchecked": unchecked}


def _cve_list(vuln_results: dict[str, Any]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for pkg_key, info in vuln_results.items():
        for vuln in info.get("vulnerabilities") or []:
            vid = vuln.get("id", "")
            if vid and vid not in seen:
                seen.add(vid)
                out.append({**vuln, "found_in": pkg_key})
    return out


def _count_critical(cve_list: list[dict]) -> int:
    return sum(
        1 for v in cve_list
        if isinstance(v.get("severity"), str) and "CRITICAL" in v["severity"].upper()
    )


def _fallback_text_summary(summary: dict) -> str:
    total = summary.get("total", 0)
    vulnerable = summary.get("vulnerable", 0)
    return f"Scanned {total} dependencies — {vulnerable} have known vulnerabilities."


async def generate_text_summary(summary: dict, cve_list: list[dict]) -> str:
    fallback = _fallback_text_summary(summary)
    if groq_client is None:
        return fallback

    total = summary.get("total", 0)
    vulnerable = summary.get("vulnerable", 0)
    cve_snippet = cve_list[:10]
    cve_lines = [
        f"- {v.get('id', 'UNKNOWN')} ({v.get('severity', 'unknown')}) in {v.get('found_in', '?')}"
        for v in cve_snippet
    ]
    cve_block = "\n".join(cve_lines) if cve_lines else "None"

    prompt = (
        f"Summarize this dependency scan in 1-2 plain-English sentences. "
        f"Mention severity if relevant. No preamble.\n\n"
        f"Total dependencies: {total}\n"
        f"Vulnerable: {vulnerable}\n"
        f"CVEs (sample):\n{cve_block}"
    )

    try:
        response = await groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
        )
        content = response.choices[0].message.content
        if content and content.strip():
            return content.strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Groq summary generation failed: %s", exc)

    return fallback


# ── 7. MAIN ENTRYPOINT ────────────────────────────────────────────────────────
async def main() -> None:
    logger.info("dependency-engine (depra) starting…")

    await init_pool()
    logger.info("Postgres pool ready.")

    worker = Worker(
        QUEUE_NAME,
        process_job,  # type: ignore[arg-type]
        {
            "connection": {"host": REDIS_HOST, "port": REDIS_PORT},
            "concurrency": WORKER_CONCURRENCY,
        },
    )

    logger.info("Listening on queue '%s' (concurrency=%d)", QUEUE_NAME, WORKER_CONCURRENCY)

    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:
            pass

    try:
        await stop_event.wait()
    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("Shutting down…")
    finally:
        await worker.close()
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
