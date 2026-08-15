import uuid
from typing import List, Optional
from pydantic import BaseModel, Field


class FileChange(BaseModel):
    """Represents a concrete change to a single file."""
    file_path: str          # relative path in repo, e.g. "Dockerfile" or ".github/workflows/ci.yml"
    action: str             # "modify" | "create" | "delete"
    original_content: Optional[str] = None
    new_content: str        # complete new file content after applying
    diff_summary: str       # short human explanation of what changed in this file


class FileRecommendation(BaseModel):
    """A single AI-powered, file-level recommendation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    priority: str           # HIGH | MEDIUM | LOW
    category: str           # security | reliability | performance | cost | maintainability | deployment
    title: str
    problem: str            # what is wrong — human-readable
    solution: str           # what to do — human-readable
    reasoning: str          # why this matters, with specific context from their repo
    impact: str             # measurable outcome: "Reduces image size from ~900MB to ~120MB"
    file_changes: List[FileChange] = Field(default_factory=list)
    estimated_effort: str   # "5 minutes" | "30 minutes" | "1 day" etc.
    applied: bool = False
    pr_url: Optional[str] = None


class InfrastructureRecommendationResult(BaseModel):
    """Full result from the recommendation engine."""
    overall_score: int = 100
    security_score: int = 100
    reliability_score: int = 100
    scalability_score: int = 100
    deployment_score: int = 100
    maintainability_score: int = 100
    cost_score: int = 100
    recommendations: List[FileRecommendation] = Field(default_factory=list)
    ai_powered: bool = False
    ai_model: str = ""


# Legacy compatibility — keep the old class name as an alias
class InfrastructureRecommendation(FileRecommendation):
    pass
