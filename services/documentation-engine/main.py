"""
main.py — Single-file BullMQ worker for documentation-engine (docryx).

Architecture note: container previously ran uvicorn HTTP stub; this matches
dependency-engine as a Redis queue consumer (QUEUE_NAME=documentation-engine).

All scan logic lives in this one file — clone, checks, scoring, persistence.
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
from typing import Any, Literal

import asyncpg
import git
import httpx
from bullmq import Job, Worker
from groq import APIStatusError, AsyncGroq

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("documentation-engine")

# ── 1. CONFIGURATION ──────────────────────────────────────────────────────────
REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/codelens")
QUEUE_NAME: str = os.getenv("QUEUE_NAME", "documentation-engine")
WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
ENGINE_NAME: str = "docryx"
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_TIMEOUT_SECONDS: float = 10.0
_ENABLE_AI_RAW: str = os.getenv(
    "ENABLE_AI_SUGGESTIONS",
    "true" if GROQ_API_KEY else "false",
)
ENABLE_AI_SUGGESTIONS: bool = _ENABLE_AI_RAW.lower() in ("true", "1", "yes")

groq_client: AsyncGroq | None = (
    AsyncGroq(api_key=GROQ_API_KEY, timeout=GROQ_TIMEOUT_SECONDS)
    if GROQ_API_KEY and ENABLE_AI_SUGGESTIONS
    else None
)
_ai_startup_logged = False

README_NAMES = ("README.md", "README", "readme.md", "Readme.md")
LICENSE_NAMES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "License", "License.md")
README_SECTIONS = (
    (r"installation|setup", "Installation/Setup"),
    (r"usage|getting\s+started", "Usage/Getting Started"),
    (r"api|documentation", "API/Documentation"),
    (r"configuration|config", "Configuration"),
    (r"contributing", "Contributing"),
    (r"license", "License"),
    (r"examples?", "Examples"),
)
SOURCE_EXTENSIONS = {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs", ".py"}
SKIP_DIR_NAMES = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", ".next", "coverage", ".pytest_cache",
}
MAX_SOURCE_FILES = 200
GITHUB_API = "https://api.github.com"
CHECK_RUN_NAME = "docryx/documentation-check"

ROUTE_FILE_PATTERNS = (
    re.compile(r"(^|/)routes/", re.I),
    re.compile(r"(^|/)controllers/", re.I),
    re.compile(r"(^|/)api/", re.I),
    re.compile(r"\.controller\.", re.I),
    re.compile(r"\.route\.", re.I),
    re.compile(r"\.routes\.", re.I),
)
OPENAPI_FILENAMES = {
    "openapi.json", "openapi.yaml", "openapi.yml",
    "swagger.json", "swagger.yaml", "swagger.yml",
}
ENV_EXAMPLE_NAMES = (".env.example", ".env.sample", ".env.template")
CONFIG_FILES = {"docker-compose.yml", "docker-compose.yaml", ".env.example"}
LOCKFILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock"}

_JS_EXPORT_ADD = re.compile(
    r"^\+\s*(?:export\s+(?:async\s+)?function\s+(\w+)|export\s+class\s+(\w+)|"
    r"export\s+const\s+(\w+)\s*=|module\.exports\s*=|exports\.(\w+)\s*=)"
)
_JS_EXPORT_REMOVE = re.compile(
    r"^-\s*(?:export\s+(?:async\s+)?function\s+(\w+)|export\s+class\s+(\w+)|"
    r"export\s+const\s+(\w+)\s*=|module\.exports\s*=|exports\.(\w+)\s*=)"
)
_PY_DEF_ADD = re.compile(r"^\+\s*(?:async\s+)?def\s+(\w+)")
_PY_CLASS_ADD = re.compile(r"^\+\s*class\s+(\w+)")
_PY_DEF_REMOVE = re.compile(r"^-\s*(?:async\s+)?def\s+(\w+)")
_PY_CLASS_REMOVE = re.compile(r"^-\s*class\s+(\w+)")

FindingStatus = Literal["pass", "warn", "fail"]
Finding = dict[str, str]

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


# ── 2. REPO TRAVERSAL ─────────────────────────────────────────────────────────
def _iter_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIR_NAMES for part in path.parts):
            continue
        files.append(path)
    return files


def _collect_source_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for rel_dir in ("src", "lib"):
        d = root / rel_dir
        if d.is_dir():
            candidates.extend(
                p for p in d.rglob("*")
                if p.is_file() and p.suffix in SOURCE_EXTENSIONS
                and not any(part in SKIP_DIR_NAMES for part in p.parts)
            )
    for p in root.iterdir():
        if p.is_file() and p.suffix in SOURCE_EXTENSIONS:
            candidates.append(p)
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in candidates:
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique[:MAX_SOURCE_FILES]


# ── 3. DOCUMENTATION CHECKS ───────────────────────────────────────────────────
def _find_readme(root: Path) -> Path | None:
    for name in README_NAMES:
        p = root / name
        if p.is_file():
            return p
    return None


def _check_readme(root: Path) -> tuple[bool, int, Finding]:
    readme = _find_readme(root)
    if readme is None:
        return False, 0, {
            "check": "readme",
            "status": "fail",
            "detail": "No README file found at repository root.",
        }

    try:
        content = readme.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return True, 0, {
            "check": "readme",
            "status": "fail",
            "detail": f"README present but unreadable: {exc}",
        }

    if len(content.strip()) < 200:
        return True, min(20, _score_readme_sections(content)), {
            "check": "readme",
            "status": "warn",
            "detail": "README is present but very short (under 200 characters).",
        }

    score = _score_readme_sections(content)
    missing = _missing_readme_sections(content)
    status: FindingStatus = "pass" if score >= 70 else ("warn" if score >= 40 else "fail")
    detail = f"README score {score}/100."
    if missing:
        detail += f" Missing sections: {', '.join(missing)}."
    return True, score, {"check": "readme", "status": status, "detail": detail}


def _score_readme_sections(content: str) -> int:
    points_per = 100 // len(README_SECTIONS)
    score = 0
    for pattern, _label in README_SECTIONS:
        if re.search(rf"^#{{1,6}}\s*.*({pattern})", content, re.I | re.M):
            score += points_per
    return min(100, score)


def _missing_readme_sections(content: str) -> list[str]:
    missing: list[str] = []
    for pattern, label in README_SECTIONS:
        if not re.search(rf"^#{{1,6}}\s*.*({pattern})", content, re.I | re.M):
            missing.append(label)
    return missing


def _check_license(root: Path) -> tuple[bool, Finding]:
    for name in LICENSE_NAMES:
        if (root / name).is_file():
            return True, {
                "check": "license",
                "status": "pass",
                "detail": f"License file found: {name}",
            }

    pkg = root / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            if data.get("license"):
                return True, {
                    "check": "license",
                    "status": "pass",
                    "detail": f"License declared in package.json: {data['license']}",
                }
        except (json.JSONDecodeError, OSError):
            pass

    return False, {
        "check": "license",
        "status": "fail",
        "detail": "No LICENSE file or package.json license field found.",
    }


def _check_contributing(root: Path) -> tuple[bool, Finding]:
    paths = (root / "CONTRIBUTING.md", root / ".github" / "CONTRIBUTING.md")
    for p in paths:
        if p.is_file():
            return True, {
                "check": "contributing",
                "status": "pass",
                "detail": f"Contributing guide found: {p.relative_to(root).as_posix()}",
            }
    return False, {
        "check": "contributing",
        "status": "fail",
        "detail": "No CONTRIBUTING.md at root or .github/CONTRIBUTING.md.",
    }


def _check_docs_folder(root: Path) -> tuple[bool, Finding]:
    for dirname in ("docs", "documentation"):
        docs_dir = root / dirname
        if docs_dir.is_dir():
            md_files = list(docs_dir.rglob("*.md"))
            if md_files:
                return True, {
                    "check": "docs_folder",
                    "status": "pass",
                    "detail": f"Found {len(md_files)} markdown file(s) in {dirname}/.",
                }
            return False, {
                "check": "docs_folder",
                "status": "warn",
                "detail": f"{dirname}/ exists but contains no .md files.",
            }
    return False, {
        "check": "docs_folder",
        "status": "fail",
        "detail": "No docs/ or documentation/ folder with markdown files.",
    }


def _comment_ratio_for_file(path: Path) -> tuple[int, int]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return 0, 0

    ext = path.suffix.lower()
    comment_lines = 0
    non_blank = 0
    in_block = False

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        non_blank += 1

        if ext == ".py":
            if line.startswith("#"):
                comment_lines += 1
            continue

        if in_block:
            comment_lines += 1
            if "*/" in line:
                in_block = False
            continue

        if line.startswith("//"):
            comment_lines += 1
        elif line.startswith("/*"):
            comment_lines += 1
            if "*/" not in line:
                in_block = True
        elif "/*" in line and "*/" in line:
            comment_lines += 1

    return comment_lines, non_blank


def _check_code_comment_ratio(source_files: list[Path]) -> tuple[float, Finding]:
    if not source_files:
        return 0.0, {
            "check": "code_comment_ratio",
            "status": "warn",
            "detail": "No source files found for comment ratio analysis.",
        }

    total_comments = total_lines = 0
    for path in source_files:
        c, n = _comment_ratio_for_file(path)
        total_comments += c
        total_lines += n

    ratio = round((total_comments / total_lines) * 100, 2) if total_lines else 0.0
    status: FindingStatus = "pass" if ratio >= 15 else ("warn" if ratio >= 5 else "fail")
    return ratio, {
        "check": "code_comment_ratio",
        "status": status,
        "detail": f"Comment ratio {ratio}% across {len(source_files)} file(s).",
    }


def _js_exported_symbols(content: str) -> list[int]:
    """Return line indices (0-based) of exported functions/classes."""
    lines = content.splitlines()
    indices: list[int] = []
    patterns = (
        r"^\s*export\s+(async\s+)?function\s+\w+",
        r"^\s*export\s+class\s+\w+",
        r"^\s*export\s+const\s+\w+\s*=",
        r"^\s*module\.exports\s*=",
        r"^\s*exports\.\w+\s*=",
    )
    for i, line in enumerate(lines):
        if any(re.match(p, line) for p in patterns):
            indices.append(i)
    return indices


def _has_jsdoc_before(lines: list[str], line_idx: int) -> bool:
    for j in range(line_idx - 1, max(-1, line_idx - 8), -1):
        stripped = lines[j].strip()
        if not stripped:
            continue
        if stripped.endswith("*/"):
            for k in range(j, max(-1, j - 10), -1):
                if "/**" in lines[k]:
                    return True
            return False
        return False
    return False


def _python_top_level_defs(content: str) -> list[tuple[int, str]]:
    lines = content.splitlines()
    results: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if line.startswith((" ", "\t")):
            continue
        m = re.match(r"^(?:async\s+)?def\s+(\w+)|^class\s+(\w+)", line)
        if m:
            results.append((i, m.group(1) or m.group(2) or ""))
    return results


def _has_python_docstring(lines: list[str], def_line: int) -> bool:
    for j in range(def_line + 1, min(len(lines), def_line + 4)):
        stripped = lines[j].strip()
        if not stripped or stripped.startswith("#"):
            continue
        return stripped.startswith(('"""', "'''"))
    return False


def _check_documented_functions(source_files: list[Path]) -> tuple[float | None, Finding]:
    js_files = [p for p in source_files if p.suffix.lower() in {".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs"}]
    py_files = [p for p in source_files if p.suffix.lower() == ".py"]

    if not js_files and not py_files:
        return None, {
            "check": "documented_functions_ratio",
            "status": "warn",
            "detail": "No JS/TS or Python source files — function documentation check skipped.",
        }

    documented = total = 0

    for path in js_files:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.splitlines()
        for idx in _js_exported_symbols(content):
            total += 1
            if _has_jsdoc_before(lines, idx):
                documented += 1

    for path in py_files:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = content.splitlines()
        for def_line, _name in _python_top_level_defs(content):
            total += 1
            if _has_python_docstring(lines, def_line):
                documented += 1

    if total == 0:
        return None, {
            "check": "documented_functions_ratio",
            "status": "warn",
            "detail": "Source files found but no exportable functions/classes detected.",
        }

    ratio = round((documented / total) * 100, 2)
    status: FindingStatus = "pass" if ratio >= 60 else ("warn" if ratio >= 30 else "fail")
    return ratio, {
        "check": "documented_functions_ratio",
        "status": status,
        "detail": f"{documented}/{total} exported symbols documented ({ratio}%).",
    }


# ── 4. SCORING ────────────────────────────────────────────────────────────────
def _compute_overall_score(
    readme_score: int,
    has_license: bool,
    has_contributing: bool,
    docs_folder_found: bool,
    code_comment_ratio: float,
    documented_functions_ratio: float | None,
) -> int:
    weights = {
        "readme": 35.0,
        "license": 10.0,
        "contributing": 10.0,
        "docs_folder": 10.0,
        "comment": 15.0,
        "functions": 20.0,
    }

    if documented_functions_ratio is None:
        total_w = sum(v for k, v in weights.items() if k != "functions")
        weights = {k: (v / total_w) * 100 for k, v in weights.items() if k != "functions"}

    score = (
        readme_score * weights.get("readme", 0) / 100
        + (100 if has_license else 0) * weights.get("license", 0) / 100
        + (100 if has_contributing else 0) * weights.get("contributing", 0) / 100
        + (100 if docs_folder_found else 0) * weights.get("docs_folder", 0) / 100
        + code_comment_ratio * weights.get("comment", 0) / 100
    )
    if documented_functions_ratio is not None:
        score += documented_functions_ratio * weights.get("functions", 0) / 100

    return int(round(score))


def _grade_from_score(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 40:
        return "D"
    return "F"


def _readme_has_section(content: str, pattern: str) -> bool:
    return bool(re.search(rf"^#{{1,6}}\s*.*({pattern})", content, re.I | re.M))


def _relative_depth(root: Path, path: Path) -> int:
    try:
        return len(path.relative_to(root).parts) - 1
    except ValueError:
        return 99


def _check_api_docs(root: Path) -> tuple[bool, str | None, Finding]:
    for path in _iter_files(root):
        if _relative_depth(root, path) > 2:
            continue
        name_lower = path.name.lower()
        rel = path.relative_to(root).as_posix().lower()
        if name_lower in OPENAPI_FILENAMES or (
            ("openapi" in name_lower or "swagger" in name_lower)
            and path.suffix.lower() in (".json", ".yaml", ".yml")
        ):
            return True, "openapi", {
                "check": "api_docs",
                "status": "pass",
                "detail": f"OpenAPI/Swagger spec found: {rel}",
            }
        if name_lower.endswith(".postman_collection.json") and _relative_depth(root, path) <= 2:
            return True, "postman", {
                "check": "api_docs",
                "status": "pass",
                "detail": f"Postman collection found: {rel}",
            }

    for candidate in (root / "docs" / "api.md", root / "API.md"):
        if candidate.is_file():
            return True, "markdown", {
                "check": "api_docs",
                "status": "pass",
                "detail": f"Markdown API docs found: {candidate.relative_to(root).as_posix()}",
            }
    api_md_dir = root / "docs" / "api"
    if api_md_dir.is_dir() and list(api_md_dir.glob("*.md")):
        return True, "markdown", {
            "check": "api_docs",
            "status": "pass",
            "detail": "Markdown API docs found under docs/api/",
        }

    return False, None, {
        "check": "api_docs",
        "status": "fail",
        "detail": "No OpenAPI, Postman, or markdown API documentation found.",
    }


def _check_env_example(root: Path) -> tuple[bool, Finding]:
    for name in ENV_EXAMPLE_NAMES:
        if (root / name).is_file():
            return True, {
                "check": "env_example",
                "status": "pass",
                "detail": f"Environment template found: {name}",
            }
    readme = _find_readme(root)
    if readme is not None:
        try:
            content = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        if _readme_has_section(content, r"environment\s+variables|env(ironment)?\s+setup"):
            return True, {
                "check": "env_example",
                "status": "pass",
                "detail": "README includes an Environment Variables section.",
            }
    return False, {
        "check": "env_example",
        "status": "fail",
        "detail": "No .env.example/.env.sample/.env.template or README env section found.",
    }


def _check_codeowners(root: Path) -> tuple[bool, Finding]:
    for rel in ("CODEOWNERS", ".github/CODEOWNERS", "docs/CODEOWNERS"):
        if (root / rel).is_file():
            return True, {
                "check": "codeowners",
                "status": "pass",
                "detail": f"CODEOWNERS found: {rel}",
            }
    return False, {
        "check": "codeowners",
        "status": "fail",
        "detail": "No CODEOWNERS file found.",
    }


def _check_pr_template(root: Path) -> tuple[bool, Finding]:
    single = root / ".github" / "PULL_REQUEST_TEMPLATE.md"
    if single.is_file():
        return True, {
            "check": "pr_template",
            "status": "pass",
            "detail": "PR template found at .github/PULL_REQUEST_TEMPLATE.md",
        }
    tpl_dir = root / ".github" / "PULL_REQUEST_TEMPLATE"
    if tpl_dir.is_dir() and any(tpl_dir.iterdir()):
        return True, {
            "check": "pr_template",
            "status": "pass",
            "detail": "PR template directory found at .github/PULL_REQUEST_TEMPLATE/",
        }
    return False, {
        "check": "pr_template",
        "status": "fail",
        "detail": "No GitHub PR template found.",
    }


def _check_issue_template(root: Path) -> tuple[bool, Finding]:
    single = root / ".github" / "ISSUE_TEMPLATE.md"
    if single.is_file():
        return True, {
            "check": "issue_template",
            "status": "pass",
            "detail": "Issue template found at .github/ISSUE_TEMPLATE.md",
        }
    tpl_dir = root / ".github" / "ISSUE_TEMPLATE"
    if tpl_dir.is_dir() and any(tpl_dir.iterdir()):
        return True, {
            "check": "issue_template",
            "status": "pass",
            "detail": "Issue template directory found at .github/ISSUE_TEMPLATE/",
        }
    return False, {
        "check": "issue_template",
        "status": "fail",
        "detail": "No GitHub issue template found.",
    }


def _check_changelog(root: Path) -> tuple[bool, Finding]:
    if (root / "CHANGELOG.md").is_file():
        return True, {
            "check": "changelog",
            "status": "pass",
            "detail": "CHANGELOG.md found at repository root.",
        }
    return False, {
        "check": "changelog",
        "status": "fail",
        "detail": "No CHANGELOG.md at repository root.",
    }


def _check_architecture_doc(root: Path) -> tuple[bool, Finding]:
    for rel in ("ARCHITECTURE.md", "docs/architecture.md"):
        if (root / rel).is_file():
            return True, {
                "check": "architecture_doc",
                "status": "pass",
                "detail": f"Architecture documentation found: {rel}",
            }
    readme = _find_readme(root)
    if readme is not None:
        try:
            content = readme.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        if _readme_has_section(content, r"architecture|system\s+design"):
            return True, {
                "check": "architecture_doc",
                "status": "pass",
                "detail": "README includes an Architecture section.",
            }
    return False, {
        "check": "architecture_doc",
        "status": "fail",
        "detail": "No ARCHITECTURE.md, docs/architecture.md, or README architecture section.",
    }


def _check_ci_config(root: Path) -> tuple[bool, Finding]:
    wf_dir = root / ".github" / "workflows"
    if wf_dir.is_dir() and list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml")):
        return True, {
            "check": "ci_config",
            "status": "pass",
            "detail": "GitHub Actions workflow(s) found.",
        }
    for rel in (".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml"):
        if (root / rel).is_file():
            return True, {
                "check": "ci_config",
                "status": "pass",
                "detail": f"CI configuration found: {rel}",
            }
    return False, {
        "check": "ci_config",
        "status": "fail",
        "detail": "No CI configuration found (GitHub Actions, GitLab CI, Jenkins, or CircleCI).",
    }


def _compute_team_readiness_score(
    has_api_docs: bool,
    has_env_example: bool,
    has_codeowners: bool,
    has_pr_template: bool,
    has_issue_template: bool,
    has_changelog: bool,
    has_architecture_doc: bool,
    has_ci_config: bool,
) -> int:
    checks = (
        has_api_docs,
        has_env_example,
        has_codeowners,
        has_pr_template,
        has_issue_template,
        has_changelog,
        has_architecture_doc,
        has_ci_config,
    )
    return int(round(sum(12.5 for flag in checks if flag)))


def _run_team_readiness_checks(repo_path: Path) -> dict[str, Any]:
    findings: list[Finding] = []

    has_api_docs, api_docs_type, api_finding = _check_api_docs(repo_path)
    findings.append(api_finding)

    has_env_example, env_finding = _check_env_example(repo_path)
    findings.append(env_finding)

    has_codeowners, codeowners_finding = _check_codeowners(repo_path)
    findings.append(codeowners_finding)

    has_pr_template, pr_finding = _check_pr_template(repo_path)
    findings.append(pr_finding)

    has_issue_template, issue_finding = _check_issue_template(repo_path)
    findings.append(issue_finding)

    has_changelog, changelog_finding = _check_changelog(repo_path)
    findings.append(changelog_finding)

    has_architecture_doc, arch_finding = _check_architecture_doc(repo_path)
    findings.append(arch_finding)

    has_ci_config, ci_finding = _check_ci_config(repo_path)
    findings.append(ci_finding)

    team_score = _compute_team_readiness_score(
        has_api_docs,
        has_env_example,
        has_codeowners,
        has_pr_template,
        has_issue_template,
        has_changelog,
        has_architecture_doc,
        has_ci_config,
    )

    return {
        "has_api_docs": has_api_docs,
        "api_docs_type": api_docs_type,
        "has_env_example": has_env_example,
        "has_codeowners": has_codeowners,
        "has_pr_template": has_pr_template,
        "has_issue_template": has_issue_template,
        "has_changelog": has_changelog,
        "has_architecture_doc": has_architecture_doc,
        "has_ci_config": has_ci_config,
        "team_readiness_score": team_score,
        "team_readiness_grade": _grade_from_score(team_score),
        "team_readiness_findings": findings,
    }


# ── 5. SCAN RUNNER ────────────────────────────────────────────────────────────
def scan_documentation(repo_path: Path, repo_url: str = "") -> dict[str, Any]:
    """Run all documentation checks against an on-disk repo folder."""
    findings: list[Finding] = []

    has_readme, readme_score, readme_finding = _check_readme(repo_path)
    findings.append(readme_finding)

    has_license, license_finding = _check_license(repo_path)
    findings.append(license_finding)

    has_contributing, contributing_finding = _check_contributing(repo_path)
    findings.append(contributing_finding)

    docs_folder_found, docs_finding = _check_docs_folder(repo_path)
    findings.append(docs_finding)

    source_files = _collect_source_files(repo_path)
    comment_ratio, comment_finding = _check_code_comment_ratio(source_files)
    findings.append(comment_finding)

    doc_fn_ratio, doc_fn_finding = _check_documented_functions(source_files)
    findings.append(doc_fn_finding)

    overall = _compute_overall_score(
        readme_score, has_license, has_contributing,
        docs_folder_found, comment_ratio, doc_fn_ratio,
    )
    grade = _grade_from_score(overall)

    team = _run_team_readiness_checks(repo_path)
    findings.extend(team.pop("team_readiness_findings"))

    fail_count = sum(1 for f in findings if f["status"] == "fail")
    undocumented = 0
    if doc_fn_finding.get("detail") and "/" in doc_fn_finding["detail"]:
        m = re.match(r"(\d+)/(\d+)", doc_fn_finding["detail"])
        if m:
            documented, total = int(m.group(1)), int(m.group(2))
            undocumented = total - documented

    return {
        "repo_url": repo_url,
        "has_readme": has_readme,
        "readme_score": readme_score,
        "has_license": has_license,
        "has_contributing": has_contributing,
        "docs_folder_found": docs_folder_found,
        "code_comment_ratio": comment_ratio,
        "documented_functions_ratio": doc_fn_ratio,
        "overall_score": overall,
        "grade": grade,
        "findings": findings,
        "files_analyzed": len(source_files),
        "missing_docs_count": fail_count,
        "functions_without_docstring": undocumented,
        **team,
    }


def _clone_failure_result(repo_url: str, scan_id: str, detail: str) -> dict[str, Any]:
    return {
        "run_id": scan_id,
        "repo_url": repo_url,
        "has_readme": False,
        "readme_score": 0,
        "has_license": False,
        "has_contributing": False,
        "docs_folder_found": False,
        "code_comment_ratio": 0.0,
        "documented_functions_ratio": None,
        "overall_score": 0,
        "grade": "F",
        "has_api_docs": False,
        "api_docs_type": None,
        "has_env_example": False,
        "has_codeowners": False,
        "has_pr_template": False,
        "has_issue_template": False,
        "has_changelog": False,
        "has_architecture_doc": False,
        "has_ci_config": False,
        "team_readiness_score": 0,
        "team_readiness_grade": "F",
        "findings": [{"check": "clone", "status": "fail", "detail": detail}],
        "files_analyzed": 0,
        "missing_docs_count": 1,
        "functions_without_docstring": 0,
        "ai_summary": None,
        "ai_suggestions": [],
        "ai_status": "skipped",
    }


def _ai_skipped() -> dict[str, Any]:
    return {"ai_summary": None, "ai_suggestions": [], "ai_status": "skipped"}


def _ai_failed() -> dict[str, Any]:
    return {"ai_summary": None, "ai_suggestions": [], "ai_status": "failed"}


def _build_ai_prompt(scan: dict[str, Any]) -> str:
    doc_fn = scan.get("documented_functions_ratio")
    doc_fn_str = f"{doc_fn}%" if doc_fn is not None else "N/A (unsupported or no source files)"
    drift_lines = ""
    if scan.get("api_docs_drift_detected") is not None:
        drift_lines += (
            f"- API doc drift detected: {scan.get('api_docs_drift_detected')}\n"
            f"- Drift files: {scan.get('api_docs_drift_files') or []}\n"
        )
    if scan.get("meaningful_changes_undocumented") is not None:
        drift_lines += (
            f"- Meaningful undocumented changes: {scan.get('meaningful_changes_undocumented') or []}\n"
        )
    drift_section = f"\nCommit-scoped drift:\n{drift_lines}" if drift_lines else ""

    return (
        "You are reviewing documentation quality for a code repository.\n"
        f"Overall score: {scan.get('overall_score', 0)}/100 (grade {scan.get('grade', 'F')})\n"
        f"Team readiness score: {scan.get('team_readiness_score', 0)}/100 "
        f"(grade {scan.get('team_readiness_grade', 'F')})\n"
        "Overall documentation inputs:\n"
        f"- README: {scan.get('has_readme')}, section score {scan.get('readme_score', 0)}/100\n"
        f"- License present: {scan.get('has_license')}\n"
        f"- Contributing guide present: {scan.get('has_contributing')}\n"
        f"- Docs folder present: {scan.get('docs_folder_found')}\n"
        f"- Code comment ratio: {scan.get('code_comment_ratio', 0)}%\n"
        f"- Documented functions ratio: {doc_fn_str}\n"
        "Team readiness inputs:\n"
        f"- API docs: {scan.get('has_api_docs')} ({scan.get('api_docs_type') or 'none'})\n"
        f"- Env example: {scan.get('has_env_example')}\n"
        f"- CODEOWNERS: {scan.get('has_codeowners')}\n"
        f"- PR template: {scan.get('has_pr_template')}\n"
        f"- Issue template: {scan.get('has_issue_template')}\n"
        f"- Changelog: {scan.get('has_changelog')}\n"
        f"- Architecture doc: {scan.get('has_architecture_doc')}\n"
        f"- CI config: {scan.get('has_ci_config')}\n"
        f"{drift_section}\n"
        "Given only this information, respond in JSON with:\n"
        "{\n"
        '  "summary": "<2-3 sentence plain-English summary of documentation health>",\n'
        '  "suggestions": [\n'
        '    { "area": "readme" | "license" | "contributing" | "docs" | "comments" | '
        '"team_readiness" | "api_docs" | "drift", '
        '"priority": "high" | "medium" | "low", '
        '"suggestion": "<concrete, actionable text, 1-2 sentences>" }\n'
        "  ]\n"
        "}\n"
        "Return 3-6 suggestions, ordered by priority. When drift data is present, "
        "include at least one high-priority suggestion about it. Only JSON, no other text."
    )


def _parse_ai_json(content: str) -> dict[str, Any] | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    summary = data.get("summary")
    suggestions = data.get("suggestions")
    if not isinstance(summary, str) or not isinstance(suggestions, list):
        return None
    cleaned: list[dict[str, str]] = []
    for item in suggestions:
        if not isinstance(item, dict):
            continue
        area = item.get("area")
        priority = item.get("priority")
        suggestion = item.get("suggestion")
        if isinstance(area, str) and isinstance(priority, str) and isinstance(suggestion, str):
            cleaned.append({"area": area, "priority": priority, "suggestion": suggestion})
    if not summary.strip() or not cleaned:
        return None
    return {"summary": summary.strip(), "suggestions": cleaned}


def _log_ai_startup_once() -> None:
    global _ai_startup_logged
    if _ai_startup_logged:
        return
    _ai_startup_logged = True
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY not set, AI suggestions disabled")
    elif not ENABLE_AI_SUGGESTIONS:
        logger.warning("ENABLE_AI_SUGGESTIONS is off, AI suggestions disabled")


async def _call_groq_once(prompt: str) -> str:
    if groq_client is None:
        raise RuntimeError("Groq client not configured")
    response = await groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.3,
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("Empty Groq response")
    return content


async def generate_ai_suggestions(scan: dict[str, Any]) -> dict[str, Any]:
    """Best-effort Groq suggestions from deterministic scan results only."""
    _log_ai_startup_once()

    if groq_client is None:
        return _ai_skipped()

    prompt = _build_ai_prompt(scan)
    last_exc: Exception | None = None

    for attempt in range(2):
        try:
            content = await asyncio.wait_for(_call_groq_once(prompt), timeout=GROQ_TIMEOUT_SECONDS)
            parsed = _parse_ai_json(content)
            if parsed is None:
                logger.warning("Groq response JSON parse failed")
                return _ai_failed()
            return {
                "ai_summary": parsed["summary"],
                "ai_suggestions": parsed["suggestions"],
                "ai_status": "success",
            }
        except asyncio.TimeoutError:
            logger.warning("Groq suggestions timed out after %.0fs", GROQ_TIMEOUT_SECONDS)
            return _ai_failed()
        except APIStatusError as exc:
            last_exc = exc
            status = exc.status_code
            logger.warning("Groq API error (status %s): %s", status, exc.message)
            if status and 400 <= status < 500 and status != 429:
                return _ai_failed()
            if attempt == 0 and status in (429, 500, 502, 503, 504):
                await asyncio.sleep(1)
                continue
            return _ai_failed()
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("Groq suggestions generation failed: %s", exc)
            return _ai_failed()

    logger.warning("Groq suggestions failed after retry: %s", last_exc)
    return _ai_failed()


# ── 5b. WEBHOOK DRIFT DETECTION (patch heuristics) ───────────────────────────
def _is_test_file(filename: str) -> bool:
    lower = filename.replace("\\", "/").lower()
    name = Path(lower).name
    return (
        "__tests__" in lower
        or "/test/" in lower
        or "/tests/" in lower
        or name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in lower
        or ".spec." in lower
    )


def _is_source_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SOURCE_EXTENSIONS and not _is_test_file(filename)


def _is_api_route_file(filename: str) -> bool:
    normalized = filename.replace("\\", "/")
    return any(pattern.search(normalized) for pattern in ROUTE_FILE_PATTERNS)


def _is_api_doc_file(filename: str) -> bool:
    lower = filename.replace("\\", "/").lower()
    name = Path(lower).name
    if name in OPENAPI_FILENAMES:
        return True
    if "openapi" in name or "swagger" in name:
        return name.endswith((".json", ".yaml", ".yml"))
    if name.endswith(".postman_collection.json"):
        return True
    if lower.endswith("docs/api.md") or lower.endswith("/api.md"):
        return True
    if "/docs/api/" in lower and lower.endswith(".md"):
        return True
    return False


def _extract_export_name(match: re.Match[str]) -> str:
    for g in match.groups():
        if g:
            return g
    return "export"


def _has_doc_on_added_lines(patch_lines: list[str], export_line_idx: int) -> bool:
    for j in range(export_line_idx - 1, max(-1, export_line_idx - 6), -1):
        line = patch_lines[j]
        if not line.startswith("+"):
            continue
        body = line[1:].strip()
        if not body:
            continue
        if body.startswith(("/**", "/*", "*", '"""', "'''")):
            return True
        return False
    return False


def _patch_lines_from_diffs(diffs: list[dict[str, Any]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in diffs:
        filename = item.get("filename") or ""
        patch = item.get("patch") or ""
        if filename:
            out[filename] = patch.splitlines()
    return out


def _detect_api_docs_drift(changed_files: list[str]) -> list[str]:
    api_changed = [f for f in changed_files if _is_api_route_file(f)]
    if not api_changed:
        return []
    doc_touched = any(_is_api_doc_file(f) for f in changed_files)
    if doc_touched:
        return []
    return api_changed


def _detect_meaningful_changes(diffs: list[dict[str, Any]]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []

    for item in diffs:
        filename = item.get("filename") or ""
        status = item.get("status") or "modified"
        patch = item.get("patch") or ""
        lines = patch.splitlines() if patch else []

        if status == "added" and _is_source_file(filename):
            changes.append({
                "file": filename,
                "kind": "new_file",
                "detail": f"New source file {filename} added",
            })

        lower = filename.replace("\\", "/").lower()
        if lower in CONFIG_FILES or lower.startswith("config/"):
            changes.append({
                "file": filename,
                "kind": "config_change",
                "detail": f"Configuration file {filename} changed",
            })
        elif lower.endswith("package.json") and patch:
            if re.search(r'^[\+\-]\s*"(scripts|dependencies)"\s*:', patch, re.M):
                changes.append({
                    "file": filename,
                    "kind": "config_change",
                    "detail": f"package.json scripts/dependencies changed",
                })

        if not lines:
            continue

        for idx, line in enumerate(lines):
            for pattern, kind in (
                (_JS_EXPORT_ADD, "new_function"),
                (_PY_DEF_ADD, "new_function"),
                (_PY_CLASS_ADD, "new_function"),
            ):
                m = pattern.search(line)
                if m and kind == "new_function" and not _has_doc_on_added_lines(lines, idx):
                    name = _extract_export_name(m)
                    changes.append({
                        "file": filename,
                        "kind": "new_function",
                        "detail": f"New exported symbol `{name}` in {filename} has no docstring/JSDoc",
                    })

            for pattern in (_JS_EXPORT_REMOVE, _PY_DEF_REMOVE, _PY_CLASS_REMOVE):
                m = pattern.search(line)
                if m:
                    name = _extract_export_name(m)
                    changes.append({
                        "file": filename,
                        "kind": "removed_function",
                        "detail": f"Removed exported symbol `{name}` from {filename}",
                    })

    return changes


def _normalize_changed_files(changed_files: list[str]) -> set[str]:
    return {f.replace("\\", "/").lower() for f in changed_files}


def _apply_changelog_finding(
    findings: list[Finding],
    meaningful_changes: list[dict[str, str]] | None,
    changed_files: list[str],
) -> None:
    if meaningful_changes is None:
        return
    normalized = _normalize_changed_files(changed_files)
    changelog_touched = any(
        f.endswith("changelog.md") for f in normalized
    )
    if meaningful_changes and not changelog_touched:
        findings.append({
            "check": "changelog_sync",
            "status": "fail",
            "detail": (
                f"{len(meaningful_changes)} meaningful change(s) shipped "
                "without a CHANGELOG.md update"
            ),
        })
    elif meaningful_changes:
        findings.append({
            "check": "changelog_sync",
            "status": "pass",
            "detail": "CHANGELOG.md updated alongside meaningful changes",
        })


def analyze_webhook_drift(
    diffs: list[dict[str, Any]] | None,
    changed_files: list[str] | None,
) -> dict[str, Any]:
    """Commit-scoped drift checks — only when webhook provides context."""
    if diffs is None and changed_files is None:
        return {
            "meaningful_changes_undocumented": None,
            "api_docs_drift_detected": None,
            "api_docs_drift_files": None,
        }

    changed = changed_files or []
    findings_extra: list[Finding] = []

    if changed_files is not None:
        api_drift_files = _detect_api_docs_drift(changed)
        api_drift_detected = bool(api_drift_files)
    else:
        api_drift_files = None
        api_drift_detected = None

    if diffs is None:
        meaningful = None
    elif not diffs:
        meaningful = None
        findings_extra.append({
            "check": "diff_data",
            "status": "warn",
            "detail": "Insufficient diff data — meaningful-change checks skipped",
        })
    else:
        meaningful = _detect_meaningful_changes(diffs)

    return {
        "meaningful_changes_undocumented": meaningful,
        "api_docs_drift_detected": api_drift_detected,
        "api_docs_drift_files": api_drift_files if changed_files is not None else None,
        "findings_extra": findings_extra,
    }


def _build_check_run_output(result: dict[str, Any]) -> tuple[str, str, str]:
    """Return (conclusion, title, summary_markdown)."""
    api_drift_detected = result.get("api_docs_drift_detected")
    api_drift = result.get("api_docs_drift_files") or []
    meaningful = result.get("meaningful_changes_undocumented")
    if meaningful is None:
        meaningful_list: list = []
    else:
        meaningful_list = meaningful

    changelog_fail = any(
        f.get("check") == "changelog_sync" and f.get("status") == "fail"
        for f in result.get("findings", [])
    )

    issue_count = (
        (1 if api_drift_detected else 0)
        + len(meaningful_list)
        + (1 if changelog_fail else 0)
    )
    if issue_count == 0:
        return (
            "success",
            "Docs look up to date",
            "No drift or undocumented changes detected in this push.",
        )

    title = f"{issue_count} documentation issue(s) found"
    parts: list[str] = []

    if api_drift_detected:
        parts.append("### API Doc Drift")
        for path in api_drift:
            parts.append(f"- {path} changed without an API documentation update")

    if meaningful_list:
        parts.append("\n### Undocumented Changes")
        for item in meaningful_list:
            parts.append(f"- {item.get('detail', item.get('file', 'unknown'))}")

    team_score = result.get("team_readiness_score")
    if team_score is not None:
        parts.append(
            f"\n### Team Readiness\n"
            f"- Repository team readiness score: {team_score}/100 "
            f"(grade {result.get('team_readiness_grade', 'F')})"
        )

    changelog_findings = [
        f for f in result.get("findings", []) if f.get("check") == "changelog_sync"
    ]
    if changelog_findings:
        parts.append("\n### Changelog")
        for f in changelog_findings:
            parts.append(f"- {f.get('detail', '')}")

    return ("neutral", title, "\n".join(parts).strip())


async def post_github_check_run(
    repo_full_name: str,
    commit_sha: str,
    github_token: str,
    result: dict[str, Any],
) -> None:
    if not repo_full_name or not commit_sha or not github_token:
        return

    conclusion, title, summary = _build_check_run_output(result)
    url = f"{GITHUB_API}/repos/{repo_full_name}/check-runs"
    payload = {
        "name": CHECK_RUN_NAME,
        "head_sha": commit_sha,
        "status": "completed",
        "conclusion": conclusion,
        "output": {"title": title, "summary": summary},
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            logger.info(
                "GitHub Check Run created for %s@%s (conclusion=%s)",
                repo_full_name, commit_sha[:7], conclusion,
            )
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "GitHub Check Run failed (status %s): %s",
            exc.response.status_code,
            exc.response.text[:200],
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("GitHub Check Run failed: %s", exc)


async def _run_scan(
    repo_url: str,
    scan_id: str,
    triggered_by: str,
    webhook_ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not repo_url or not repo_url.startswith(("http://", "https://", "git@")):
        result = _clone_failure_result(repo_url, scan_id, f"Invalid repository URL: {repo_url!r}")
        result.update(await generate_ai_suggestions(result))
        return result

    tmp_dir = tempfile.mkdtemp(prefix="docryx-")
    try:
        try:
            await asyncio.to_thread(git.Repo.clone_from, repo_url, tmp_dir, depth=1)
        except git.exc.GitCommandError as exc:
            logger.warning("Clone failed for %s: %s", repo_url, exc)
            result = _clone_failure_result(repo_url, scan_id, f"Clone failed: {exc}")
            result.update(await generate_ai_suggestions(result))
            return result

        result = scan_documentation(Path(tmp_dir), repo_url)
        result["run_id"] = scan_id
        result["triggered_by"] = triggered_by
        result["scanned_at"] = datetime.datetime.utcnow().isoformat()

        if triggered_by == "webhook" and webhook_ctx:
            drift = analyze_webhook_drift(
                webhook_ctx.get("diffs"),
                webhook_ctx.get("changedFiles") or [],
            )
            result["meaningful_changes_undocumented"] = drift.get("meaningful_changes_undocumented")
            result["api_docs_drift_detected"] = drift.get("api_docs_drift_detected")
            result["api_docs_drift_files"] = drift.get("api_docs_drift_files")
            for extra in drift.get("findings_extra") or []:
                result.setdefault("findings", []).append(extra)
            _apply_changelog_finding(
                result["findings"],
                result["meaningful_changes_undocumented"],
                webhook_ctx.get("changedFiles") or [],
            )
            result["commitSha"] = webhook_ctx.get("commitSha")
            result["repoFullName"] = webhook_ctx.get("repoFullName")

        ai_fields = await generate_ai_suggestions(result)
        result.update(ai_fields)
        return result
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ── 6. PERSISTENCE ────────────────────────────────────────────────────────────
async def _mark_engine(scan_id: str, status: str, started_at: datetime.datetime | None = None) -> None:
    if pool is None:
        return
    try:
        run_uuid = str(uuid.UUID(scan_id))
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


async def _persist_results(
    scan_id: str,
    result: dict[str, Any],
    started_at: datetime.datetime,
    duration_ms: int,
) -> None:
    if pool is None:
        return

    try:
        run_uuid = str(uuid.UUID(scan_id))
    except ValueError:
        return

    completed_at = datetime.datetime.utcnow()
    is_hard_error = "error" in result and "overall_score" not in result

    try:
        async with pool.acquire() as conn:
            async with conn.transaction():
                if not is_hard_error:
                    doc_fn_ratio = result.get("documented_functions_ratio")
                    findings = result.get("findings", [])

                    await conn.execute(
                        """
                        INSERT INTO doc_reports
                            (id, run_id, repo_url, has_readme, readme_score,
                             has_license, has_contributing, docs_folder_found,
                             code_comment_ratio, documented_functions_ratio,
                             overall_score, grade, findings,
                             has_api_docs, api_docs_type, has_env_example,
                             has_codeowners, has_pr_template, has_issue_template,
                             has_changelog, has_architecture_doc, has_ci_config,
                             team_readiness_score, team_readiness_grade,
                             files_analyzed, missing_docs_count,
                             functions_without_docstring, doc_suggestions,
                             ai_summary, ai_suggestions, ai_status,
                             meaningful_changes_undocumented, api_docs_drift_detected,
                             api_docs_drift_files, created_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                                $11, $12, $13::jsonb, $14, $15, $16, $17, $18, $19,
                                $20, $21, $22, $23, $24, $25, $26, $27, $28::jsonb,
                                $29, $30::jsonb, $31, $32::jsonb, $33, $34::jsonb, $35)
                        ON CONFLICT (run_id) DO UPDATE SET
                            repo_url                   = EXCLUDED.repo_url,
                            has_readme                 = EXCLUDED.has_readme,
                            readme_score               = EXCLUDED.readme_score,
                            has_license                = EXCLUDED.has_license,
                            has_contributing           = EXCLUDED.has_contributing,
                            docs_folder_found          = EXCLUDED.docs_folder_found,
                            code_comment_ratio         = EXCLUDED.code_comment_ratio,
                            documented_functions_ratio = EXCLUDED.documented_functions_ratio,
                            overall_score              = EXCLUDED.overall_score,
                            grade                      = EXCLUDED.grade,
                            findings                   = EXCLUDED.findings,
                            has_api_docs               = EXCLUDED.has_api_docs,
                            api_docs_type              = EXCLUDED.api_docs_type,
                            has_env_example            = EXCLUDED.has_env_example,
                            has_codeowners             = EXCLUDED.has_codeowners,
                            has_pr_template            = EXCLUDED.has_pr_template,
                            has_issue_template         = EXCLUDED.has_issue_template,
                            has_changelog              = EXCLUDED.has_changelog,
                            has_architecture_doc       = EXCLUDED.has_architecture_doc,
                            has_ci_config              = EXCLUDED.has_ci_config,
                            team_readiness_score       = EXCLUDED.team_readiness_score,
                            team_readiness_grade       = EXCLUDED.team_readiness_grade,
                            files_analyzed             = EXCLUDED.files_analyzed,
                            missing_docs_count         = EXCLUDED.missing_docs_count,
                            functions_without_docstring = EXCLUDED.functions_without_docstring,
                            doc_suggestions            = EXCLUDED.doc_suggestions,
                            ai_summary                 = EXCLUDED.ai_summary,
                            ai_suggestions             = EXCLUDED.ai_suggestions,
                            ai_status                  = EXCLUDED.ai_status,
                            meaningful_changes_undocumented = EXCLUDED.meaningful_changes_undocumented,
                            api_docs_drift_detected    = EXCLUDED.api_docs_drift_detected,
                            api_docs_drift_files       = EXCLUDED.api_docs_drift_files
                        """,
                        str(uuid.uuid4()),
                        run_uuid,
                        result.get("repo_url"),
                        result.get("has_readme", False),
                        result.get("readme_score", 0),
                        result.get("has_license", False),
                        result.get("has_contributing", False),
                        result.get("docs_folder_found", False),
                        result.get("code_comment_ratio", 0),
                        doc_fn_ratio,
                        result.get("overall_score", 0),
                        result.get("grade", "F"),
                        json.dumps(findings),
                        result.get("has_api_docs", False),
                        result.get("api_docs_type"),
                        result.get("has_env_example", False),
                        result.get("has_codeowners", False),
                        result.get("has_pr_template", False),
                        result.get("has_issue_template", False),
                        result.get("has_changelog", False),
                        result.get("has_architecture_doc", False),
                        result.get("has_ci_config", False),
                        result.get("team_readiness_score", 0),
                        result.get("team_readiness_grade", "F"),
                        result.get("files_analyzed", 0),
                        result.get("missing_docs_count", 0),
                        result.get("functions_without_docstring", 0),
                        json.dumps(findings),
                        result.get("ai_summary"),
                        json.dumps(result.get("ai_suggestions") or []),
                        result.get("ai_status", "skipped"),
                        json.dumps(result.get("meaningful_changes_undocumented"))
                        if result.get("meaningful_changes_undocumented") is not None else None,
                        result.get("api_docs_drift_detected"),
                        json.dumps(result.get("api_docs_drift_files"))
                        if result.get("api_docs_drift_files") is not None else None,
                        completed_at,
                    )

                final_status = "failed" if is_hard_error else "completed"
                error_msg = result.get("error") if is_hard_error else None

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


# ── 7. QUEUE CONSUMER ─────────────────────────────────────────────────────────
async def process_job(job: Job, job_token: str) -> dict[str, Any]:
    data = job.data or {}
    repo_url = data.get("repoUrl", "")
    scan_id = data.get("scanId", "")
    triggered_by = data.get("triggeredBy", "manual")

    webhook_ctx = None
    if triggered_by == "webhook":
        webhook_ctx = {
            "changedFiles": data.get("changedFiles") or [],
            "commitSha": data.get("commitSha"),
            "diffs": data.get("diffs"),
            "repoFullName": data.get("repoFullName"),
            "githubToken": data.get("githubToken"),
        }

    logger.info("Processing job %s — repo=%s scanId=%s", job.id, repo_url, scan_id)

    start_ts = datetime.datetime.utcnow()
    started_ms = time.monotonic()

    await _mark_engine(scan_id, "running", started_at=start_ts)

    try:
        result = await _run_scan(repo_url, scan_id, triggered_by, webhook_ctx)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unhandled error in job %s: %s", job.id, exc)
        result = {"error": str(exc)}

    duration_ms = int((time.monotonic() - started_ms) * 1000)
    await _persist_results(scan_id, result, start_ts, duration_ms)

    if triggered_by == "webhook" and webhook_ctx and "error" not in result:
        await post_github_check_run(
            webhook_ctx.get("repoFullName") or result.get("repoFullName", ""),
            webhook_ctx.get("commitSha") or result.get("commitSha", ""),
            webhook_ctx.get("githubToken") or "",
            result,
        )

    logger.info(
        "Job %s finished — scanId=%s grade=%s score=%s (%dms)",
        job.id, scan_id, result.get("grade", "?"), result.get("overall_score", "?"), duration_ms,
    )
    return result


# ── 8. MAIN ENTRYPOINT ────────────────────────────────────────────────────────
async def main() -> None:
    logger.info("documentation-engine (docryx) starting…")
    _log_ai_startup_once()

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
