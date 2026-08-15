import uuid
from typing import List, Optional
from pydantic import BaseModel, Field

class InfrastructureRecommendation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    category: str
    priority: str # HIGH, MEDIUM, LOW
    title: str
    description: str
    reason: str
    currentState: str
    recommendedState: str
    estimatedComplexity: str # LOW, MEDIUM, HIGH

class InfrastructureRecommendationResult(BaseModel):
    overall_score: int = 100
    security_score: int = 100
    reliability_score: int = 100
    scalability_score: int = 100
    deployment_score: int = 100
    maintainability_score: int = 100
    cost_score: int = 100
    recommendations: List[InfrastructureRecommendation] = Field(default_factory=list)
