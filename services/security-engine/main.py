import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from models import AnalyzeJobRequest, ScanResult
from pipeline import process_scan

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="security-engine")


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "security-engine"}


@app.post("/analyze")
def analyze(request: AnalyzeJobRequest) -> JSONResponse:
    """
    Run the Infilra stage-1 pipeline for a job dispatched by the BullMQ worker.

    Accepts both Infilra-native fields (scanId, repoUrl) and platform fields
    (runId, cloneUrl) from the API gateway payload.
    """
    result = process_scan(
        scan_id=request.resolved_scan_id,
        repo_url=request.resolved_repo_url,
        github_token=request.github_token,
    )
    return JSONResponse(content=result.model_dump(by_alias=True, exclude_none=True))
