from typing import List
from app.schemas.discovery import InfrastructureDiscovery
from app.architecture.models import ArchitectureModel
from app.schemas.recommendation import InfrastructureRecommendation

def should_recommend_kubernetes(arch: ArchitectureModel) -> bool:
    """Heuristic to determine if Kubernetes is appropriate."""
    # Already has Kubernetes
    if arch.infrastructure.kubernetes or arch.infrastructure.helm:
        return True
    
    # 10+ services implies complex microservices
    if len(arch.services) >= 10:
        return True
        
    # High throughput or message queues imply complex async architecture
    if any(q.type in ['kafka', 'rabbitmq'] for q in arch.queues):
        return True
        
    # If the complexity score was calculated to be very high
    if arch.complexity >= 50:
        return True
        
    return False

def generate_greenfield_recommendations(arch: ArchitectureModel) -> List[InfrastructureRecommendation]:
    """Generates recommendations for an application with no infrastructure defined."""
    recommendations = []
    
    needs_k8s = should_recommend_kubernetes(arch)
    
    # 1. Containerization
    recommendations.append(InfrastructureRecommendation(
        category="scalability",
        priority="HIGH",
        title="Implement Docker Containerization",
        description="Containerize the application to ensure consistent environments across development, testing, and production.",
        reason="No Dockerfile detected. Containers prevent 'it works on my machine' issues and are standard for modern deployments.",
        currentState="Application runs directly on host OS.",
        recommendedState="Application runs inside a Docker container.",
        estimatedComplexity="LOW"
    ))
    
    # 2. Local Development
    if needs_k8s:
        # Complex setup might still benefit from Compose locally, or Minikube/Skaffold
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Implement Local Kubernetes Dev Environment",
            description="Use tools like Skaffold, Tilt, or Minikube to emulate the complex microservices environment locally.",
            reason="High service count or complex messaging requires a robust local emulator.",
            currentState="No local orchestration.",
            recommendedState="Skaffold/Tilt configured for local dev.",
            estimatedComplexity="HIGH"
        ))
    else:
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Implement Docker Compose for Local Development",
            description="Create a docker-compose.yml to easily spin up the application and its dependencies (e.g. database).",
            reason="Simplifies developer onboarding.",
            currentState="Developers must manually install databases and services.",
            recommendedState="One-command startup via `docker-compose up`.",
            estimatedComplexity="LOW"
        ))
        
    # 3. CI/CD
    recommendations.append(InfrastructureRecommendation(
        category="deployment",
        priority="HIGH",
        title="Implement CI/CD Pipeline",
        description="Add a GitHub Actions or GitLab CI pipeline to automate tests, security scanning, and builds.",
        reason="No automated pipelines detected.",
        currentState="Manual builds and testing.",
        recommendedState="Automated testing and container building on every push.",
        estimatedComplexity="MEDIUM"
    ))
    
    # 4. Orchestration
    if needs_k8s:
        recommendations.append(InfrastructureRecommendation(
            category="scalability",
            priority="HIGH",
            title="Adopt Kubernetes for Orchestration",
            description="Deploy services using Kubernetes to handle the high complexity and scale of the system.",
            reason="The architecture's complexity and service count warrant a robust orchestrator.",
            currentState="No orchestration defined.",
            recommendedState="Kubernetes cluster (e.g., EKS, GKE) with Helm charts.",
            estimatedComplexity="HIGH"
        ))
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Use Helm for Kubernetes Package Management",
            description="Define your Kubernetes resources as Helm charts for easier templating and versioning.",
            reason="Managing raw YAML across 10+ services is error-prone.",
            currentState="No package management.",
            recommendedState="Helm charts defining standard deployments.",
            estimatedComplexity="MEDIUM"
        ))
    else:
        recommendations.append(InfrastructureRecommendation(
            category="deployment",
            priority="MEDIUM",
            title="Adopt Managed PaaS or Serverless",
            description="Deploy the container to a managed service like AWS App Runner, Google Cloud Run, or Heroku.",
            reason="Simple architectures don't need the overhead of Kubernetes.",
            currentState="No deployment strategy defined.",
            recommendedState="Automated deployment to a serverless container platform.",
            estimatedComplexity="LOW"
        ))
        
    # 5. Infrastructure as Code
    recommendations.append(InfrastructureRecommendation(
        category="maintainability",
        priority="LOW",
        title="Adopt Terraform for Infrastructure as Code",
        description="Define your cloud resources (databases, networks) using Terraform.",
        reason="Manual cloud console clicks lead to configuration drift.",
        currentState="Infrastructure created manually.",
        recommendedState="Terraform state tracking all cloud resources.",
        estimatedComplexity="MEDIUM"
    ))
    
    return recommendations

def generate_brownfield_recommendations(arch: ArchitectureModel, findings: list) -> List[InfrastructureRecommendation]:
    """Generates recommendations for an application that already has some infrastructure."""
    recommendations = []
    
    # Check for gaps in the architecture model
    if not arch.infrastructure.docker:
        recommendations.append(InfrastructureRecommendation(
            category="scalability",
            priority="HIGH",
            title="Implement Docker Containerization",
            description="Containerize the application components.",
            reason="Missing containerization in an existing infrastructure setup.",
            currentState="No Dockerfile detected.",
            recommendedState="Dockerfiles for all services.",
            estimatedComplexity="LOW"
        ))
        
    if not arch.infrastructure.terraform:
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Adopt Infrastructure as Code",
            description="Migrate existing cloud resources to Terraform.",
            reason="Missing IaC tooling.",
            currentState="Resources managed manually or via scripts.",
            recommendedState="Terraform modules managing infrastructure.",
            estimatedComplexity="HIGH"
        ))
        
    # Analyze findings to generate specific recommendations
    # For example, if there are CRITICAL security findings, recommend a security review
    critical_findings = [f for f in findings if f.severity == "CRITICAL"]
    if critical_findings:
        recommendations.append(InfrastructureRecommendation(
            category="security",
            priority="HIGH",
            title="Address Critical Security Vulnerabilities",
            description=f"Fix the {len(critical_findings)} critical security findings detected in the static analysis.",
            reason="Critical vulnerabilities expose the system to immediate risk.",
            currentState=f"{len(critical_findings)} critical findings.",
            recommendedState="0 critical findings.",
            estimatedComplexity="MEDIUM"
        ))
        
    return recommendations
