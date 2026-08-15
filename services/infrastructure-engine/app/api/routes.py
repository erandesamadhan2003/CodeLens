from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from app.schemas.job import JobPayload, ProgressEvent
from app.services.git_service import temporary_workspace, clone_repository, GitServiceError
from app.utils.logger import get_logger
from datetime import datetime, timezone
import json

logger = get_logger(__name__)
router = APIRouter()

async def analysis_stream(payload: JobPayload):
    # Emit Started
    yield json.dumps(ProgressEvent(runId=payload.runId, stage="analysis", status="started", progress=5, message="Starting infrastructure analysis", timestamp=datetime.now(timezone.utc).isoformat()).model_dump()) + "\n"
    
    try:
        async with temporary_workspace(payload.runId) as workspace_path:
            logger.info("Starting git clone", extra={"runId": payload.runId})
            # We don't have a specific event for 'clone', so we can reuse discovery or just not emit one here.
            # The prompt asks for: "Do not implement discovery yet. ... return success"
            
            clone_repository(
                repo_url=payload.repoUrl,
                workspace_path=workspace_path,
                commit_sha=payload.commitSha,
                timeout=60
            )
            
            # Yield discovery started
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "discovery",
                "status": "started",
                "progress": 10,
                "message": "Starting infrastructure discovery phase",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"
            
            # Run Discovery
            from app.discovery.scanner import InfrastructureScanner
            scanner = InfrastructureScanner(workspace_path)
            discovery = scanner.run_discovery()
            
            # Persist to DB
            from app.services.db_service import persist_discovery
            await persist_discovery(payload.runId, discovery)
            
            # Yield discovery completed
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "discovery",
                "status": "completed",
                "progress": 25,
                "message": "Infrastructure discovery completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            # 4. Architecture Stage
            # Yield architecture started
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "architecture",
                "status": "started",
                "progress": 30,
                "message": "Building infrastructure architecture model",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"

            from app.architecture.builder import build_architecture
            from app.architecture.graph import build_graph
            
            arch_model = build_architecture(discovery)
            build_graph(arch_model)
            
            # Persist architecture
            from app.services.db_service import persist_architecture
            await persist_architecture(payload.runId, arch_model)
            
            # Yield architecture completed
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "architecture",
                "status": "completed",
                "progress": 50,
                "message": "Architecture model building completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"
            
            # 5. Infrastructure Analysis Stage (Docker & Compose)
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "static_analysis",
                "status": "started",
                "progress": 55,
                "message": "Running static analysis on infrastructure files",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"
            
            from app.analyzers.docker_analyzer import DockerAnalyzer
            from app.analyzers.compose_analyzer import ComposeAnalyzer
            from app.analyzers.kubernetes_analyzer import KubernetesAnalyzer
            from app.analyzers.terraform_analyzer import TerraformAnalyzer
            from app.analyzers.cicd_analyzer import CicdAnalyzer
            
            docker_analyzer = DockerAnalyzer(workspace_path)
            compose_analyzer = ComposeAnalyzer(workspace_path)
            kubernetes_analyzer = KubernetesAnalyzer(workspace_path)
            terraform_analyzer = TerraformAnalyzer(workspace_path, arch_model)
            cicd_analyzer = CicdAnalyzer(workspace_path)
            
            all_findings = []
            all_findings.extend(docker_analyzer.analyze())
            all_findings.extend(compose_analyzer.analyze())
            all_findings.extend(kubernetes_analyzer.analyze())
            all_findings.extend(cicd_analyzer.analyze())
            
            tf_findings, tf_provider = terraform_analyzer.analyze()
            all_findings.extend(tf_findings)
            
            # Persist findings and terraform metadata
            from app.services.db_service import persist_findings, update_terraform_metadata
            await persist_findings(payload.runId, payload.repositoryId, all_findings)
            if tf_provider != "unknown" or arch_model.cloud_resources:
                await update_terraform_metadata(payload.runId, tf_provider, arch_model.cloud_resources)
            
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "static_analysis",
                "status": "completed",
                "progress": 85,
                "message": "Static analysis completed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }) + "\n"
            
            # --- STAGE 5A: RECOMMENDATION ENGINE ---
            logger.info("Starting Recommendation Engine phase", extra={"runId": payload.runId})
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "recommendation",
                "status": "started",
                "progress": 60,
                "message": "Generating infrastructure recommendations",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "eventName": "infra.recommendation.started"
                }
            }) + "\n"
            
            from app.recommendation.engine import RecommendationEngine
            recommendation_engine = RecommendationEngine(discovery, arch_model, all_findings)
            recommendation_result = recommendation_engine.generate()
            
            from app.services.db_service import update_recommendations
            await update_recommendations(payload.runId, recommendation_result.model_dump())
            
            yield json.dumps({
                "runId": payload.runId,
                "engine": "infrastructure",
                "stage": "recommendation",
                "status": "completed",
                "progress": 70,
                "message": "Recommendations generated",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "eventName": "infra.recommendation.completed"
                }
            }) + "\n"
            
            # --- FINAL RESULT ---
            result = {
                "final_result": {
                    "runId": payload.runId,
                    "engine": "infrastructure",
                    "stage": "analysis",
                    "status": "completed",
                    "progress": 100,
                    "message": "Infrastructure analysis completed",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "data": {
                        "discovery": discovery.model_dump(),
                        "architecture": arch_model.model_dump(),
                        "findingsCount": len(all_findings),
                        "recommendations": recommendation_result.model_dump()
                    },
                    "ai_tokens_used": 0
                }
            }
            yield json.dumps(result) + "\n"
            
    except GitServiceError as e:
        logger.error(f"Git Service Error: {e}", extra={"runId": payload.runId})
        error_result = {
            "runId": payload.runId,
            "engine": "infrastructure",
            "stage": "analysis",
            "status": "failed",
            "progress": 0,
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("Yielding first error line", extra={"runId": payload.runId})
        yield json.dumps(error_result) + "\n"
        logger.info("Yielding second error line", extra={"runId": payload.runId})
        yield json.dumps({"final_result": error_result}) + "\n"
        logger.info("Finished yielding error lines", extra={"runId": payload.runId})
    except Exception as e:
        logger.error(f"Unexpected Error: {e}", extra={"runId": payload.runId})
        error_result = {
            "runId": payload.runId,
            "engine": "infrastructure",
            "stage": "analysis",
            "status": "failed",
            "progress": 0,
            "message": "An internal error occurred during analysis.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield json.dumps(error_result) + "\n"
        yield json.dumps({"final_result": error_result}) + "\n"

@router.post("/analyze")
async def analyze_repository(payload: JobPayload):
    """
    Internal endpoint called by the Node.js API Gateway (BullMQ worker)
    to initiate infrastructure analysis for a given repository.
    Streams NDJSON events.
    """
    return StreamingResponse(analysis_stream(payload), media_type="application/x-ndjson")
