from typing import Optional
from pydantic import BaseModel, Field

class InfrastructureFinding(BaseModel):
    ruleId: str
    category: str # "security", "reliability", "performance", "cost"
    severity: str # "CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"
    title: str
    description: str
    filePath: str
    lineNumber: int = 0
    evidence: str
    recommendation: str
