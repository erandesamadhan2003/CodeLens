from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Optional
from app.schemas.job import JobPayload, ProgressEvent
from app.services.git_service import temporary_workspace, clone_repository, GitServiceError
from app.utils.logger import get_logger
from datetime import datetime, timezone
import json

logger = get_logger(__name__)
router = APIRouter()


class ApplyPayload(BaseModel):
    runId: str
    recommendationId: str
    recommendationTitle: str
    fileChanges: List[Dict]       # [{file_path, action, new_content, diff_summary}]
    githubToken: str
    repoFullName: str
    baseBranch: str = "main"


async def analysis_stream(payload: JobPayload):
    # Emit Started
    yield json.dumps(ProgressEvent(runId=payload.runId, stage="analysis", status="started", progress=5, message="Starting infrastructure analysis", timestamp=datetime.now(timezone.utc).isoformat()).model_dump()) + "\n"

    try:
        async with temporary_workspace(payload.runId) as workspace_path:
            logger.info("Starting git clone", extra={"runId": payload.runId})

            clone_repository(
                repo_url=payload.repoUrl,
                workspace_path=workspace_path,
                commit_sha=payload.commitSha,
                timeout=60
            )

            # ── Discovery ─────────────────────────────────────────────────────
            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "discovery", "status": "started", "progress": 10,
                "message": "Starting infrastructure discovery phase",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            from app.discovery.scanner import InfrastructureScanner
            scanner = InfrastructureScanner(workspace_path)
            discovery = scanner.run_discovery()

            from app.services.db_service import persist_discovery
            await persist_discovery(payload.runId, discovery)

            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "discovery", "status": "completed", "progress": 25,
                "message": f"Discovery complete. Found: {', '.join(discovery.languages) or 'unknown stack'}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            # ── Architecture ──────────────────────────────────────────────────
            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "architecture", "status": "started", "progress": 30,
                "message": "Building infrastructure architecture model",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            from app.architecture.builder import build_architecture
            from app.architecture.graph import build_graph

            arch_model = build_architecture(discovery)
            build_graph(arch_model)

            from app.services.db_service import persist_architecture
            await persist_architecture(payload.runId, arch_model)

            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "architecture", "status": "completed", "progress": 50,
                "message": "Architecture model built successfully",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            # ── Static Analysis ───────────────────────────────────────────────
            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "static_analysis", "status": "started", "progress": 55,
                "message": "Running static analysis on infrastructure files",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            from app.analyzers.docker_analyzer import DockerAnalyzer
            from app.analyzers.compose_analyzer import ComposeAnalyzer
            from app.analyzers.kubernetes_analyzer import KubernetesAnalyzer
            from app.analyzers.terraform_analyzer import TerraformAnalyzer
            from app.analyzers.cicd_analyzer import CicdAnalyzer

            all_findings = []
            all_findings.extend(DockerAnalyzer(workspace_path).analyze())
            all_findings.extend(ComposeAnalyzer(workspace_path).analyze())
            all_findings.extend(KubernetesAnalyzer(workspace_path).analyze())
            all_findings.extend(CicdAnalyzer(workspace_path).analyze())

            tf_findings, tf_provider = TerraformAnalyzer(workspace_path, arch_model).analyze()
            all_findings.extend(tf_findings)

            from app.services.db_service import persist_findings, update_terraform_metadata
            await persist_findings(payload.runId, payload.repositoryId, all_findings)
            if tf_provider != "unknown" or arch_model.cloud_resources:
                await update_terraform_metadata(payload.runId, tf_provider, arch_model.cloud_resources)

            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "static_analysis", "status": "completed", "progress": 70,
                "message": f"Static analysis complete. {len(all_findings)} findings.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            # ── AI Recommendation Engine ──────────────────────────────────────
            logger.info("Starting AI Recommendation Engine", extra={"runId": payload.runId})
            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "recommendation", "status": "started", "progress": 75,
                "message": "Calling Groq AI to generate file-level recommendations...",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            from app.recommendation.engine import RecommendationEngine
            recommendation_engine = RecommendationEngine(
                discovery=discovery,
                arch=arch_model,
                findings=all_findings,
                workspace_path=workspace_path,  # ← pass workspace so AI can read files
            )
            recommendation_result = recommendation_engine.generate()

            from app.services.db_service import update_recommendations
            await update_recommendations(payload.runId, recommendation_result.model_dump())

            ai_label = "AI-powered" if recommendation_result.ai_powered else "rule-based"
            yield json.dumps({
                "runId": payload.runId, "engine": "infrastructure",
                "stage": "recommendation", "status": "completed", "progress": 95,
                "message": f"Generated {len(recommendation_result.recommendations)} {ai_label} recommendations",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            # ── Final Result ──────────────────────────────────────────────────
            result = {
                "final_result": {
                    "runId": payload.runId, "engine": "infrastructure",
                    "stage": "analysis", "status": "completed", "progress": 100,
                    "message": "Infrastructure analysis completed successfully",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "discovery": discovery.model_dump(),
                        "architecture": arch_model.model_dump(),
                        "findingsCount": len(all_findings),
                        "recommendations": recommendation_result.model_dump(),
                        "ai_powered": recommendation_result.ai_powered,
                    },
                    "ai_tokens_used": 0
                }
            }
            yield json.dumps(result) + "\n"

    except GitServiceError as e:
        logger.error(f"Git Service Error: {e}", extra={"runId": payload.runId})
        error_result = {
            "runId": payload.runId, "engine": "infrastructure",
            "stage": "analysis", "status": "failed", "progress": 0,
            "message": str(e), "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield json.dumps(error_result) + "\n"
        yield json.dumps({"final_result": error_result}) + "\n"

    except Exception as e:
        logger.error(f"Unexpected Error: {e}", extra={"runId": payload.runId})
        error_result = {
            "runId": payload.runId, "engine": "infrastructure",
            "stage": "analysis", "status": "failed", "progress": 0,
            "message": "An internal error occurred during analysis.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield json.dumps(error_result) + "\n"
        yield json.dumps({"final_result": error_result}) + "\n"


@router.post("/analyze")
async def analyze_repository(payload: JobPayload):
    """
    Internal endpoint called by the Node.js API Gateway (BullMQ worker).
    Streams NDJSON progress events.
    """
    return StreamingResponse(analysis_stream(payload), media_type="application/x-ndjson")


@router.post("/apply")
async def apply_recommendation(payload: ApplyPayload):
    """
    Applies a recommendation's file changes to GitHub by creating a PR.
    Called by the API Gateway when a user clicks 'Apply to GitHub'.
    """
    if not payload.fileChanges:
        raise HTTPException(status_code=400, detail="No file changes to apply")

    if not payload.githubToken:
        raise HTTPException(status_code=400, detail="GitHub token is required")

    logger.info(
        f"Applying recommendation '{payload.recommendationTitle}' to {payload.repoFullName}",
        extra={"runId": payload.runId, "recId": payload.recommendationId}
    )

    from app.services.github_service import apply_recommendation_as_pr
    try:
        pr_url = apply_recommendation_as_pr(
            github_token=payload.githubToken,
            repo_full_name=payload.repoFullName,
            base_branch=payload.baseBranch,
            recommendation_title=payload.recommendationTitle,
            recommendation_id=payload.recommendationId,
            file_changes=payload.fileChanges,
        )
        return {"success": True, "pr_url": pr_url}
    except Exception as e:
        logger.error(f"Failed to apply recommendation: {e}")
        raise HTTPException(status_code=500, detail=str(e))
