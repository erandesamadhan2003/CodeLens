from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

class DetectedService(BaseModel):
    name: str
    type: str  # 'database', 'cache', 'queue', 'app', 'web'
    technology: str  # 'postgresql', 'redis', 'node', 'python', etc.
    ports: List[int] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list) # files that indicated this service

class InfrastructureDiscovery(BaseModel):
    # Detection flags
    has_dockerfile: bool = False
    has_docker_compose: bool = False
    has_k8s_manifests: bool = False
    has_terraform: bool = False
    has_helm_charts: bool = False
    has_ci_config: bool = False
    has_pulumi: bool = False
    has_ansible: bool = False
    cloud_provider: str = 'unknown'

    # Detected Technology Stack
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    
    # Parsed architecture
    detected_services: List[DetectedService] = Field(default_factory=list)
    architecture_graph: Dict[str, Any] = Field(default_factory=dict)
    
    # Resources
    k8s_resources: List[Dict[str, Any]] = Field(default_factory=list)
    terraform_resources: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Raw paths
    infrastructure_files: List[str] = Field(default_factory=list)
