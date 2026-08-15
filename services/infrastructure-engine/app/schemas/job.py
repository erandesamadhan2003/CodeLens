from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class JobPayload(BaseModel):
    runId: str
    repositoryId: str
    repoUrl: str
    commitSha: str
    branch: str



class ProgressEvent(BaseModel):
    runId: str
    engine: str = "infrastructure"
    stage: str
    status: str
    progress: int = Field(ge=0, le=100)
    message: str
    timestamp: str
