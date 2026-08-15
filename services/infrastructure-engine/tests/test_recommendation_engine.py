import pytest
from app.architecture.models import ArchitectureModel, ApplicationNode
from app.schemas.discovery import InfrastructureDiscovery
from app.schemas.finding import InfrastructureFinding
from app.recommendation.engine import RecommendationEngine

def test_greenfield_recommendations_simple():
    # Simple Node.js app
    arch = ArchitectureModel(
        application=ApplicationNode(languages=["javascript"], frameworks=["express"]),
        complexity=10
    )
    
    engine = RecommendationEngine(InfrastructureDiscovery(), arch, [])
    result = engine.generate()
    
    # Assert Docker, Compose, CI/CD, Serverless
    titles = [r.title for r in result.recommendations]
    assert "Implement Docker Containerization" in titles
    assert "Implement Docker Compose for Local Development" in titles
    assert "Adopt Managed PaaS or Serverless" in titles
    assert "Adopt Kubernetes for Orchestration" not in titles
    
    # Score should be perfect since no findings and gaps are handled by recommendations?
    # Wait, gaps reduce score. Containerization and deployment are missing in architecture gaps?
    # Right now, `arch.gaps` is empty in this mocked model.
    assert result.overall_score == 100

def test_greenfield_recommendations_complex():
    # Complex 15 microservices app
    arch = ArchitectureModel(
        services=[{"name": f"svc-{i}", "type": "web"} for i in range(15)],
        complexity=60
    )
    
    engine = RecommendationEngine(InfrastructureDiscovery(), arch, [])
    result = engine.generate()
    
    titles = [r.title for r in result.recommendations]
    assert "Adopt Kubernetes for Orchestration" in titles
    assert "Implement Local Kubernetes Dev Environment" in titles

def test_scoring_with_findings():
    arch = ArchitectureModel(
        gaps=["containerization", "deployment"] # -20, -20 from scalability/deployment, -30 from deployment
    )
    
    findings = [
        InfrastructureFinding(
            ruleId="TEST-001",
            category="security",
            severity="CRITICAL", # -15 security
            title="Test Critical",
            description="",
            reason="",
            filePath="",
            lineNumber=0,
            evidence="",
            recommendation=""
        ),
        InfrastructureFinding(
            ruleId="TEST-002",
            category="reliability",
            severity="HIGH", # -10 reliability
            title="Test High",
            description="",
            reason="",
            filePath="",
            lineNumber=0,
            evidence="",
            recommendation=""
        )
    ]
    
    engine = RecommendationEngine(InfrastructureDiscovery(), arch, findings)
    result = engine.generate()
    
    assert result.security_score == 85
    assert result.reliability_score == 90
    assert result.scalability_score == 80 # 100 - 20 containerization
    assert result.deployment_score == 50 # 100 - 20 containerization - 30 deployment
