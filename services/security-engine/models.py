"""Pydantic models for Infilra job intake and raw Semgrep findings."""

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AnalyzeJobRequest(BaseModel):
    """Incoming job payload from the API gateway BullMQ worker or direct callers."""

    model_config = ConfigDict(populate_by_name=True)

    scan_id: Optional[str] = Field(default=None, alias="scanId")
    run_id: Optional[str] = Field(default=None, alias="runId")
    repo_url: Optional[str] = Field(default=None, alias="repoUrl")
    clone_url: Optional[str] = Field(default=None, alias="cloneUrl")
    github_token: Optional[str] = Field(default=None, alias="githubToken")

    @model_validator(mode="after")
    def validate_required_fields(self) -> "AnalyzeJobRequest":
        if not (self.scan_id or self.run_id):
            raise ValueError("scanId or runId is required")
        if not (self.repo_url or self.clone_url):
            raise ValueError("repoUrl or cloneUrl is required")
        return self

    @property
    def resolved_scan_id(self) -> str:
        return self.scan_id or self.run_id or ""

    @property
    def resolved_repo_url(self) -> str:
        return self.repo_url or self.clone_url or ""


RawSeverity = Literal["ERROR", "WARNING", "INFO"]
ScanStatus = Literal["completed", "failed"]


class RawFinding(BaseModel):
    """Structured raw finding produced by Semgrep for the downstream AI stage."""

    model_config = ConfigDict(populate_by_name=True)

    file: str
    start_line: int = Field(serialization_alias="startLine")
    end_line: int = Field(serialization_alias="endLine")
    rule_id: str = Field(serialization_alias="ruleId")
    message: str
    raw_severity: RawSeverity = Field(serialization_alias="rawSeverity")
    code_snippet: str = Field(serialization_alias="codeSnippet")
    context: str = ""


class ScanResult(BaseModel):
    """Outcome of a single Infilra scan pipeline run."""

    model_config = ConfigDict(populate_by_name=True)

    scan_id: str = Field(serialization_alias="scanId")
    status: ScanStatus
    failure_reason: Optional[str] = Field(default=None, serialization_alias="failureReason")
    findings_count: int = Field(default=0, serialization_alias="findingsCount")
    summary: Optional[str] = None
    findings_path: Optional[str] = Field(default=None, serialization_alias="findingsPath")
    findings: Optional[list[RawFinding]] = None
