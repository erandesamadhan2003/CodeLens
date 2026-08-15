from typing import List
from app.schemas.discovery import InfrastructureDiscovery
from app.architecture.models import ArchitectureModel
from app.schemas.finding import InfrastructureFinding
from app.schemas.recommendation import InfrastructureRecommendationResult
from app.recommendation.scoring import calculate_scores
from app.recommendation.strategies import generate_greenfield_recommendations, generate_brownfield_recommendations

class RecommendationEngine:
    def __init__(self, discovery: InfrastructureDiscovery, arch: ArchitectureModel, findings: List[InfrastructureFinding]):
        self.discovery = discovery
        self.arch = arch
        self.findings = findings
        
    def generate(self) -> InfrastructureRecommendationResult:
        # 1. Calculate Scores
        scores = calculate_scores(self.arch, self.findings)
        
        # 2. Determine Strategy
        has_infra = (
            self.arch.infrastructure.docker or 
            self.arch.infrastructure.compose or 
            self.arch.infrastructure.kubernetes or 
            self.arch.infrastructure.terraform or 
            self.arch.infrastructure.helm
        )
        
        if not has_infra:
            recommendations = generate_greenfield_recommendations(self.arch)
        else:
            recommendations = generate_brownfield_recommendations(self.arch, self.findings)
            
        return InfrastructureRecommendationResult(
            overall_score=scores["overall_score"],
            security_score=scores["security_score"],
            reliability_score=scores["reliability_score"],
            scalability_score=scores["scalability_score"],
            deployment_score=scores["deployment_score"],
            maintainability_score=scores["maintainability_score"],
            cost_score=scores["cost_score"],
            recommendations=recommendations
        )
