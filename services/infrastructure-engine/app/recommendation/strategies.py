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
        solution="Containerize the application to ensure consistent environments across development, testing, and production.",
        reasoning="No Dockerfile detected. Containers prevent 'it works on my machine' issues and are standard for modern deployments.",
        problem="Application runs directly on host OS.",
        impact="Application runs inside a Docker container.",
        estimated_effort="LOW"
    ))
    
    # 2. Local Development
    if needs_k8s:
        # Complex setup might still benefit from Compose locally, or Minikube/Skaffold
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Implement Local Kubernetes Dev Environment",
            solution="Use tools like Skaffold, Tilt, or Minikube to emulate the complex microservices environment locally.",
            reasoning="High service count or complex messaging requires a robust local emulator.",
            problem="No local orchestration.",
            impact="Skaffold/Tilt configured for local dev.",
            estimated_effort="HIGH"
        ))
    else:
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Implement Docker Compose for Local Development",
            solution="Create a docker-compose.yml to easily spin up the application and its dependencies (e.g. database).",
            reasoning="Simplifies developer onboarding.",
            problem="Developers must manually install databases and services.",
            impact="One-command startup via `docker-compose up`.",
            estimated_effort="LOW"
        ))
        
    # 3. CI/CD
    recommendations.append(InfrastructureRecommendation(
        category="deployment",
        priority="HIGH",
        title="Implement CI/CD Pipeline",
        solution="Add a GitHub Actions or GitLab CI pipeline to automate tests, security scanning, and builds.",
        reasoning="No automated pipelines detected.",
        problem="Manual builds and testing.",
        impact="Automated testing and container building on every push.",
        estimated_effort="MEDIUM"
    ))
    
    # 4. Orchestration
    if needs_k8s:
        recommendations.append(InfrastructureRecommendation(
            category="scalability",
            priority="HIGH",
            title="Adopt Kubernetes for Orchestration",
            solution="Deploy services using Kubernetes to handle the high complexity and scale of the system.",
            reasoning="The architecture's complexity and service count warrant a robust orchestrator.",
            problem="No orchestration defined.",
            impact="Kubernetes cluster (e.g., EKS, GKE) with Helm charts.",
            estimated_effort="HIGH"
        ))
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Use Helm for Kubernetes Package Management",
            solution="Define your Kubernetes resources as Helm charts for easier templating and versioning.",
            reasoning="Managing raw YAML across 10+ services is error-prone.",
            problem="No package management.",
            impact="Helm charts defining standard deployments.",
            estimated_effort="MEDIUM"
        ))
    else:
        recommendations.append(InfrastructureRecommendation(
            category="deployment",
            priority="MEDIUM",
            title="Adopt Managed PaaS or Serverless",
            solution="Deploy the container to a managed service like AWS App Runner, Google Cloud Run, or Heroku.",
            reasoning="Simple architectures don't need the overhead of Kubernetes.",
            problem="No deployment strategy defined.",
            impact="Automated deployment to a serverless container platform.",
            estimated_effort="LOW"
        ))
        
    # 5. Infrastructure as Code
    recommendations.append(InfrastructureRecommendation(
        category="maintainability",
        priority="LOW",
        title="Adopt Terraform for Infrastructure as Code",
        solution="Define your cloud resources (databases, networks) using Terraform.",
        reasoning="Manual cloud console clicks lead to configuration drift.",
        problem="Infrastructure created manually.",
        impact="Terraform state tracking all cloud resources.",
        estimated_effort="MEDIUM"
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
            solution="Containerize the application components.",
            reasoning="Missing containerization in an existing infrastructure setup.",
            problem="No Dockerfile detected.",
            impact="Dockerfiles for all services.",
            estimated_effort="LOW"
        ))
        
    if not arch.infrastructure.terraform:
        recommendations.append(InfrastructureRecommendation(
            category="maintainability",
            priority="MEDIUM",
            title="Adopt Infrastructure as Code",
            solution="Migrate existing cloud resources to Terraform.",
            reasoning="Missing IaC tooling.",
            problem="Resources managed manually or via scripts.",
            impact="Terraform modules managing infrastructure.",
            estimated_effort="HIGH"
        ))
        
    # Analyze findings to generate specific recommendations
    # For example, if there are CRITICAL security findings, recommend a security review
    critical_findings = [f for f in findings if f.severity == "CRITICAL"]
    if critical_findings:
        recommendations.append(InfrastructureRecommendation(
            category="security",
            priority="HIGH",
            title="Address Critical Security Vulnerabilities",
            solution=f"Fix the {len(critical_findings)} critical security findings detected in the static analysis.",
            reasoning="Critical vulnerabilities expose the system to immediate risk.",
            problem=f"{len(critical_findings)} critical findings.",
            impact="0 critical findings.",
            estimated_effort="MEDIUM"
        ))
        
    return recommendations
