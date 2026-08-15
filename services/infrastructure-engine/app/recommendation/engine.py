"""
AI-powered infrastructure recommendation engine.
Uses Groq (llama-3.3-70b-versatile) to generate file-level, actionable recommendations
with exact code changes that can be applied directly to GitHub via PR.
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional

from app.schemas.discovery import InfrastructureDiscovery
from app.architecture.models import ArchitectureModel
from app.schemas.finding import InfrastructureFinding
from app.schemas.recommendation import (
    InfrastructureRecommendationResult,
    FileRecommendation,
    FileChange,
)
from app.recommendation.scoring import calculate_scores
from app.recommendation.groq_client import call_groq_json

logger = logging.getLogger(__name__)

# Infrastructure-relevant file extensions and names to read
INFRA_FILE_PATTERNS = [
    "Dockerfile", "dockerfile", ".dockerignore",
    "docker-compose.yml", "docker-compose.yaml",
    "docker-compose.dev.yml", "docker-compose.prod.yml",
    ".github", "*.yml", "*.yaml", "*.tf", "*.tfvars",
    "Makefile", "nginx.conf", "*.conf", "requirements.txt",
    "package.json", "Pipfile", "pyproject.toml",
    ".env.example", ".env.sample",
]

MAX_FILE_SIZE = 8000   # chars — truncate large files
MAX_FILES = 20         # cap total files sent to AI


def _read_infra_files(workspace_path: str) -> Dict[str, str]:
    """
    Walk the workspace and collect all infrastructure-relevant file contents.
    Returns {relative_path: content}.
    """
    base = Path(workspace_path)
    files = {}
    ignore_dirs = {'.git', 'node_modules', 'venv', '__pycache__', '.pytest_cache', 'dist', 'build'}

    try:
        for item in base.rglob("*"):
            if item.is_dir():
                continue
            # Skip large binary / ignored dirs
            if any(part in ignore_dirs for part in item.parts):
                continue
            
            rel = str(item.relative_to(base))
            name = item.name.lower()
            ext = item.suffix.lower()

            is_infra = (
                name in {"dockerfile", ".dockerignore", "makefile", "nginx.conf"}
                or ext in {".yml", ".yaml", ".tf", ".tfvars", ".conf", ".toml"}
                or name in {"docker-compose.yml", "docker-compose.yaml"}
                or (name == "package.json" and "node_modules" not in rel)
                or name in {"requirements.txt", "pipfile", "pyproject.toml"}
                or name in {".env.example", ".env.sample"}
                or ".github" in rel.lower()
            )

            if not is_infra:
                continue

            try:
                content = item.read_text(encoding="utf-8", errors="replace")
                if len(content) > MAX_FILE_SIZE:
                    content = content[:MAX_FILE_SIZE] + f"\n\n... [truncated — full file is {len(content)} chars]"
                files[rel] = content
                if len(files) >= MAX_FILES:
                    break
            except Exception:
                pass

    except Exception as e:
        logger.warning(f"Error reading workspace files: {e}")

    return files


def _build_prompt(
    discovery: InfrastructureDiscovery,
    arch: ArchitectureModel,
    findings: List[InfrastructureFinding],
    file_contents: Dict[str, str],
) -> str:
    """Build the structured prompt for the Groq API call."""

    # Format file contents block
    files_block = ""
    for path, content in file_contents.items():
        files_block += f"\n\n### FILE: {path}\n```\n{content}\n```"

    if not files_block:
        files_block = "\n\n(No infrastructure files detected in the repository)"

    # Format findings
    findings_block = ""
    for f in findings[:15]:  # cap at 15
        findings_block += f"\n- [{f.severity}] {f.title} in {f.filePath}: {f.description}"

    # Format discovery flags
    flags = []
    if discovery.has_dockerfile: flags.append("Dockerfile ✓")
    if discovery.has_docker_compose: flags.append("Docker Compose ✓")
    if discovery.has_k8s_manifests: flags.append("Kubernetes ✓")
    if discovery.has_terraform: flags.append("Terraform ✓")
    if discovery.has_ci_config: flags.append("CI/CD ✓")
    if not flags: flags.append("No infrastructure files detected")

    services = ", ".join([s.name for s in discovery.detected_services]) or "None detected"
    languages = ", ".join(discovery.languages) or "Unknown"

    return f"""You are an expert DevOps and infrastructure engineer conducting a thorough code review.

## Repository Context

**Languages:** {languages}
**Detected Services:** {services}
**Infrastructure Files Present:** {", ".join(flags)}
**Cloud Provider:** {discovery.cloud_provider}

## Static Analysis Findings
{findings_block or "No findings from static analysis."}

## Infrastructure Files
{files_block}

## Your Task

Analyze the repository's infrastructure files above and generate **highly specific, actionable recommendations**.

Each recommendation MUST:
1. Reference **actual file names and line numbers** from the files above
2. Include the **complete new file content** (not a snippet — the full file) that the user can apply to fix the issue
3. Be **human-readable** with clear problem/solution/reasoning
4. Prioritize real issues found in the files, not generic advice

Generate between 3 and 8 recommendations ordered by priority (HIGH first).

Return a single JSON object with this exact structure:
{{
  "overall_score": <integer 0-100>,
  "security_score": <integer 0-100>,
  "reliability_score": <integer 0-100>,
  "scalability_score": <integer 0-100>,
  "deployment_score": <integer 0-100>,
  "maintainability_score": <integer 0-100>,
  "cost_score": <integer 0-100>,
  "recommendations": [
    {{
      "priority": "HIGH",
      "category": "security",
      "title": "Short title (max 60 chars)",
      "problem": "Clear description of what is wrong, referencing specific file/line. E.g.: 'In Dockerfile line 3, the image node:18 is used instead of node:18-alpine, resulting in a 900MB base image.'",
      "solution": "What to do step by step. E.g.: 'Change the FROM line in Dockerfile to use node:18-alpine. This multi-stage build approach will...'",
      "reasoning": "Why this matters for this specific repo. Mention observed patterns.",
      "impact": "Quantified outcome. E.g.: 'Reduces Docker image size from ~900MB to ~120MB, cutting cloud egress costs and speeding up deployments by 5x.'",
      "estimated_effort": "5 minutes",
      "file_changes": [
        {{
          "file_path": "Dockerfile",
          "action": "modify",
          "original_content": null,
          "new_content": "FROM node:18-alpine AS builder\\n\\nWORKDIR /app\\nCOPY package*.json ./\\nRUN npm ci --only=production\\n\\nCOPY . .\\nRUN npm run build\\n\\nFROM node:18-alpine\\nWORKDIR /app\\nCOPY --from=builder /app/dist ./dist\\nCOPY --from=builder /app/node_modules ./node_modules\\n\\nEXPOSE 3000\\nCMD [\\"node\\", \\"dist/index.js\\"]",
          "diff_summary": "Switched from node:18 (900MB) to node:18-alpine (120MB) with multi-stage build"
        }}
      ]
    }}
  ]
}}

IMPORTANT: 
- If there are no infra files, create recommendations to ADD them (with full file content in new_content)
- If a file exists, only modify what's needed — provide the COMPLETE updated file in new_content
- new_content must be a valid, complete file ready to commit to GitHub
- Do not include any text outside the JSON object
"""


SYSTEM_PROMPT = """You are an expert infrastructure engineer and DevSecOps consultant. 
You analyze repository infrastructure files and provide highly specific, actionable recommendations 
with exact code changes. You always respond with valid JSON only — no markdown, no explanations outside the JSON."""


class RecommendationEngine:
    def __init__(
        self,
        discovery: InfrastructureDiscovery,
        arch: ArchitectureModel,
        findings: List[InfrastructureFinding],
        workspace_path: Optional[str] = None,
    ):
        self.discovery = discovery
        self.arch = arch
        self.findings = findings
        self.workspace_path = workspace_path

    def generate(self) -> InfrastructureRecommendationResult:
        # 1. Calculate scores
        scores = calculate_scores(self.arch, self.findings)

        # 2. Try AI-powered recommendations
        if self.workspace_path:
            result = self._generate_ai_recommendations(scores)
            if result:
                return result

        # 3. Fall back to rule-based
        logger.info("Falling back to rule-based recommendations")
        return self._generate_rule_based(scores)

    def _generate_ai_recommendations(self, scores: dict) -> Optional[InfrastructureRecommendationResult]:
        """Use Groq to generate file-level AI recommendations."""
        try:
            logger.info("Reading infra files from workspace for AI analysis")
            file_contents = _read_infra_files(self.workspace_path)
            logger.info(f"Found {len(file_contents)} infrastructure files: {list(file_contents.keys())}")

            prompt = _build_prompt(self.discovery, self.arch, self.findings, file_contents)
            logger.info("Calling Groq API for recommendations")

            response, tokens_used = call_groq_json(prompt, SYSTEM_PROMPT, max_tokens=8000)
            if not response:
                return None

            # Parse recommendations
            raw_recs = response.get("recommendations", [])
            recommendations = []

            for raw in raw_recs:
                try:
                    # Parse file changes
                    file_changes = []
                    for fc in raw.get("file_changes", []):
                        file_changes.append(FileChange(
                            file_path=fc.get("file_path", "unknown"),
                            action=fc.get("action", "modify"),
                            original_content=fc.get("original_content"),
                            new_content=fc.get("new_content", ""),
                            diff_summary=fc.get("diff_summary", ""),
                        ))

                    rec = FileRecommendation(
                        priority=raw.get("priority", "MEDIUM"),
                        category=raw.get("category", "maintainability"),
                        title=raw.get("title", "Infrastructure Improvement"),
                        problem=raw.get("problem", ""),
                        solution=raw.get("solution", ""),
                        reasoning=raw.get("reasoning", ""),
                        impact=raw.get("impact", ""),
                        file_changes=file_changes,
                        estimated_effort=raw.get("estimated_effort", "Unknown"),
                    )
                    recommendations.append(rec)
                except Exception as e:
                    logger.warning(f"Failed to parse recommendation: {e}")
                    continue

            if not recommendations:
                logger.warning("Groq returned no parseable recommendations")
                return None

            logger.info(f"Generated {len(recommendations)} AI recommendations using {tokens_used} tokens")

            return InfrastructureRecommendationResult(
                overall_score=response.get("overall_score", scores["overall_score"]),
                security_score=response.get("security_score", scores["security_score"]),
                reliability_score=response.get("reliability_score", scores["reliability_score"]),
                scalability_score=response.get("scalability_score", scores["scalability_score"]),
                deployment_score=response.get("deployment_score", scores["deployment_score"]),
                maintainability_score=response.get("maintainability_score", scores["maintainability_score"]),
                cost_score=response.get("cost_score", scores["cost_score"]),
                recommendations=recommendations,
                ai_powered=True,
                ai_model="llama-3.3-70b-versatile",
            )

        except Exception as e:
            logger.error(f"AI recommendation generation failed: {e}", exc_info=True)
            return None

    def _generate_rule_based(self, scores: dict) -> InfrastructureRecommendationResult:
        """Fallback rule-based recommendations when Groq is unavailable."""
        from app.recommendation.strategies import (
            generate_greenfield_recommendations,
            generate_brownfield_recommendations,
        )

        has_infra = (
            self.arch.infrastructure.docker
            or self.arch.infrastructure.compose
            or self.arch.infrastructure.kubernetes
            or self.arch.infrastructure.terraform
            or self.arch.infrastructure.helm
        )

        if not has_infra:
            recs = generate_greenfield_recommendations(self.arch)
        else:
            recs = generate_brownfield_recommendations(self.arch, self.findings)

        return InfrastructureRecommendationResult(
            overall_score=scores["overall_score"],
            security_score=scores["security_score"],
            reliability_score=scores["reliability_score"],
            scalability_score=scores["scalability_score"],
            deployment_score=scores["deployment_score"],
            maintainability_score=scores["maintainability_score"],
            cost_score=scores["cost_score"],
            recommendations=recs,
            ai_powered=False,
            ai_model="rule-based",
        )
