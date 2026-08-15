import os
import json
import asyncpg
from app.schemas.discovery import InfrastructureDiscovery
import logging

logger = logging.getLogger(__name__)

async def persist_discovery(run_id: str, discovery: InfrastructureDiscovery):
    """
    Persists the discovery results to the PostgreSQL database.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set, skipping persistence.")
        return

    try:
        conn = await asyncpg.connect(db_url)
        
        query = """
            INSERT INTO infra_analyses (
                run_id,
                has_dockerfile,
                has_docker_compose,
                has_k8s_manifests,
                has_terraform,
                has_helm_charts,
                has_ci_config,
                has_pulumi,
                has_ansible,
                cloud_provider,
                detected_services,
                architecture_graph,
                k8s_resources,
                terraform_resources
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11::jsonb, $12::jsonb, $13::jsonb, $14::jsonb
            )
            ON CONFLICT (run_id) DO UPDATE SET
                has_dockerfile = EXCLUDED.has_dockerfile,
                has_docker_compose = EXCLUDED.has_docker_compose,
                has_k8s_manifests = EXCLUDED.has_k8s_manifests,
                has_terraform = EXCLUDED.has_terraform,
                has_helm_charts = EXCLUDED.has_helm_charts,
                has_ci_config = EXCLUDED.has_ci_config,
                has_pulumi = EXCLUDED.has_pulumi,
                has_ansible = EXCLUDED.has_ansible,
                cloud_provider = EXCLUDED.cloud_provider,
                detected_services = EXCLUDED.detected_services,
                architecture_graph = EXCLUDED.architecture_graph,
                k8s_resources = EXCLUDED.k8s_resources,
                terraform_resources = EXCLUDED.terraform_resources
        """
        
        await conn.execute(
            query,
            run_id,
            discovery.has_dockerfile,
            discovery.has_docker_compose,
            discovery.has_k8s_manifests,
            discovery.has_terraform,
            discovery.has_helm_charts,
            discovery.has_ci_config,
            discovery.has_pulumi,
            discovery.has_ansible,
            discovery.cloud_provider,
            json.dumps([s.model_dump() for s in discovery.detected_services]),
            json.dumps(discovery.architecture_graph),
            json.dumps(discovery.k8s_resources),
            json.dumps(discovery.terraform_resources)
        )
        
        logger.info(f"Successfully persisted discovery results for run_id: {run_id}")
    except Exception as e:
        logger.error(f"Error persisting discovery for run_id {run_id}: {e}")
        if 'conn' in locals() and not conn.is_closed():
            await conn.close()

async def persist_architecture(run_id: str, model):
    """
    Persists the architecture graph to the PostgreSQL database.
    """
    from app.architecture.models import ArchitectureModel
    if not isinstance(model, ArchitectureModel):
        return

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set, skipping architecture persistence.")
        return

    try:
        conn = await asyncpg.connect(db_url)
        
        query = """
            UPDATE infra_analyses
            SET architecture_graph = $1::jsonb
            WHERE run_id = $2
        """
        
        await conn.execute(
            query,
            json.dumps(model.architecture_graph.model_dump()),
            run_id
        )
        
        logger.info(f"Successfully persisted architecture for run_id: {run_id}")
    except Exception as e:
        logger.error(f"Error persisting architecture for run_id {run_id}: {e}")
        if 'conn' in locals() and not conn.is_closed():
            await conn.close()

async def persist_findings(run_id: str, repo_id: str, findings):
    """
    Persists the findings to the PostgreSQL database.
    """
    if not findings:
        return
        
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set, skipping findings persistence.")
        return

    try:
        conn = await asyncpg.connect(db_url)
        
        query = """
            INSERT INTO infrastructure_findings (
                analysis_run_id,
                repository_id,
                rule_id,
                category,
                severity,
                title,
                description,
                file_path,
                line_number,
                evidence,
                recommendation,
                status
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 'open'
            )
        """
        
        # Batch insert for efficiency
        values = [
            (
                run_id,
                repo_id,
                f.ruleId,
                f.category,
                f.severity,
                f.title,
                f.description,
                f.filePath,
                f.lineNumber,
                f.evidence,
                f.recommendation
            )
            for f in findings
        ]
        
        await conn.executemany(query, values)
        logger.info(f"Successfully persisted {len(findings)} findings for run_id: {run_id}")
    except Exception as e:
        logger.error(f"Error persisting findings for run_id {run_id}: {e}")
        if 'conn' in locals() and not conn.is_closed():
            await conn.close()

async def update_terraform_metadata(run_id: str, cloud_provider: str, tf_resources: list):
    """
    Updates the terraform_resources and cloud_provider columns.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set, skipping terraform metadata update.")
        return

    try:
        conn = await asyncpg.connect(db_url)
        
        query = """
            UPDATE infra_analyses
            SET cloud_provider = $1,
                terraform_resources = $2::jsonb
            WHERE run_id = $3
        """
        
        # Format resources for JSONB
        formatted = [r.model_dump() for r in tf_resources]
        
        await conn.execute(
            query,
            cloud_provider,
            json.dumps(formatted),
            run_id
        )
        
        logger.info(f"Successfully updated terraform metadata for run_id: {run_id}")
    except Exception as e:
        logger.error(f"Error updating terraform metadata for run_id {run_id}: {e}")
    finally:
        if 'conn' in locals() and not conn.is_closed():
            await conn.close()
