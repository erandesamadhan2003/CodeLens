from app.architecture.models import ArchitectureModel, GraphNode, GraphEdge
import uuid

def build_graph(model: ArchitectureModel):
    """
    Constructs a deterministic node and edge graph based on the ArchitectureModel.
    Populates model.architecture_graph inline.
    """
    nodes = []
    edges = []

    # 1. Main Application Node
    app_id = f"app-{uuid.uuid4().hex[:8]}"
    
    # Simple heuristic for backend vs frontend
    if 'React' in model.application.frameworks or 'Vue' in model.application.frameworks or 'Angular' in model.application.frameworks:
        app_type = "frontend"
    else:
        app_type = "backend"
        
    nodes.append(GraphNode(
        id=app_id,
        type=app_type,
        label=f"{app_type.title()} App",
        metadata={
            "languages": model.application.languages,
            "frameworks": model.application.frameworks,
            "ports": model.application.ports
        }
    ))

    # 2. Containerization
    if model.infrastructure.docker or model.infrastructure.compose:
        container_id = f"container-{uuid.uuid4().hex[:8]}"
        nodes.append(GraphNode(
            id=container_id,
            type="container",
            label="Docker Container",
        ))
        edges.append(GraphEdge(
            source=container_id,
            target=app_id,
            type="contains"
        ))
        deployable_target = container_id
    else:
        deployable_target = app_id

    # 3. Orchestration
    if model.infrastructure.kubernetes:
        k8s_id = f"k8s-{uuid.uuid4().hex[:8]}"
        nodes.append(GraphNode(
            id=k8s_id,
            type="Kubernetes resource",
            label="K8s Cluster"
        ))
        edges.append(GraphEdge(
            source=k8s_id,
            target=deployable_target,
            type="deploys_to"
        ))

    # 4. Databases
    for db in model.databases:
        db_id = f"db-{uuid.uuid4().hex[:8]}"
        nodes.append(GraphNode(
            id=db_id,
            type="database",
            label=f"{db.type.title()} DB"
        ))
        edges.append(GraphEdge(
            source=app_id,
            target=db_id,
            type="database"
        ))

    # 5. Caches
    for cache in model.caches:
        cache_id = f"cache-{uuid.uuid4().hex[:8]}"
        nodes.append(GraphNode(
            id=cache_id,
            type="cache",
            label=f"{cache.type.title()} Cache"
        ))
        edges.append(GraphEdge(
            source=app_id,
            target=cache_id,
            type="cache"
        ))

    # 6. Queues
    for q in model.queues:
        q_id = f"queue-{uuid.uuid4().hex[:8]}"
        nodes.append(GraphNode(
            id=q_id,
            type="queue",
            label=f"{q.type.title()} Queue"
        ))
        edges.append(GraphEdge(
            source=app_id,
            target=q_id,
            type="queue"
        ))
        
    # 7. Services
    for svc in model.services:
        svc_id = f"svc-{uuid.uuid4().hex[:8]}"
        nodes.append(GraphNode(
            id=svc_id,
            type="service",
            label=svc.name
        ))
        edges.append(GraphEdge(
            source=app_id,
            target=svc_id,
            type="HTTP"
        ))

    model.architecture_graph.nodes = nodes
    model.architecture_graph.edges = edges
