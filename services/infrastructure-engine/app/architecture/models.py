from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class ApplicationNode(BaseModel):
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    ports: List[int] = Field(default_factory=list)

class ServiceNode(BaseModel):
    name: str
    type: str

class DatabaseNode(BaseModel):
    type: str

class CacheNode(BaseModel):
    type: str

class QueueNode(BaseModel):
    type: str

class InfrastructureState(BaseModel):
    docker: bool = False
    compose: bool = False
    kubernetes: bool = False
    terraform: bool = False
    helm: bool = False
    pulumi: bool = False
    ansible: bool = False

class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    source: str
    target: str
    type: str

class ArchitectureGraph(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)

class CloudResourceNode(BaseModel):
    id: str
    provider: str
    type: str
    name: str

class ArchitectureModel(BaseModel):
    application: ApplicationNode = Field(default_factory=ApplicationNode)
    services: List[ServiceNode] = Field(default_factory=list)
    databases: List[DatabaseNode] = Field(default_factory=list)
    caches: List[CacheNode] = Field(default_factory=list)
    queues: List[QueueNode] = Field(default_factory=list)
    infrastructure: InfrastructureState = Field(default_factory=InfrastructureState)
    cloud_resources: List[CloudResourceNode] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)
    complexity: int = 0
    architecture_graph: ArchitectureGraph = Field(default_factory=ArchitectureGraph)
