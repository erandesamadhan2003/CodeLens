from app.schemas.discovery import InfrastructureDiscovery
from app.architecture.models import ArchitectureModel, ApplicationNode, DatabaseNode, CacheNode, QueueNode, ServiceNode
from app.architecture.complexity import calculate_complexity

def build_architecture(discovery: InfrastructureDiscovery) -> ArchitectureModel:
    model = ArchitectureModel()
    
    # Map Application
    model.application.languages = discovery.languages
    model.application.frameworks = discovery.frameworks
    
    # Map Infrastructure Flags
    model.infrastructure.docker = discovery.has_dockerfile
    model.infrastructure.compose = discovery.has_docker_compose
    model.infrastructure.kubernetes = discovery.has_k8s_manifests
    model.infrastructure.terraform = discovery.has_terraform
    model.infrastructure.helm = discovery.has_helm_charts
    model.infrastructure.pulumi = discovery.has_pulumi
    model.infrastructure.ansible = discovery.has_ansible
    
    # Map Services
    for svc in discovery.detected_services:
        if svc.type == 'database':
            model.databases.append(DatabaseNode(type=svc.technology))
        elif svc.type == 'cache':
            model.caches.append(CacheNode(type=svc.technology))
        elif svc.type == 'queue':
            model.queues.append(QueueNode(type=svc.technology))
        else:
            model.services.append(ServiceNode(name=svc.name, type=svc.technology))
            
        # Collect ports for application if it's the main app, but for now we just collect all ports to app
        # This is a naive approach but fits the requested format
        if svc.type in ('app', 'web'):
            for p in svc.ports:
                if p not in model.application.ports:
                    model.application.ports.append(p)
                    
    # Map Gaps
    if not (discovery.has_dockerfile or discovery.has_docker_compose or discovery.has_k8s_manifests):
        model.gaps.append("containerization")
        
    if not discovery.has_ci_config:
        model.gaps.append("deployment")
        
    if not (discovery.has_terraform or discovery.has_pulumi or discovery.has_ansible or discovery.has_helm_charts):
        model.gaps.append("infrastructure_as_code")

    # Complexity
    model.complexity = calculate_complexity(model)
    
    return model
