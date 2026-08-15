import os
import shutil
import subprocess
import tempfile
from contextlib import asynccontextmanager
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

class GitServiceError(Exception):
    pass

@asynccontextmanager
async def temporary_workspace(run_id: str):
    """
    Creates a temporary workspace securely inside the TEMP_WORKSPACE_ROOT.
    Ensures absolute cleanup upon exit, even if an exception occurs.
    """
    os.makedirs(settings.temp_workspace_root, exist_ok=True)
    workspace_path = tempfile.mkdtemp(prefix=f"run_{run_id}_", dir=settings.temp_workspace_root)
    
    try:
        logger.info("Created temporary workspace", extra={"runId": run_id, "workspace": workspace_path})
        yield workspace_path
    finally:
        shutil.rmtree(workspace_path, ignore_errors=True)
        logger.info("Cleaned up temporary workspace", extra={"runId": run_id, "workspace": workspace_path})

def format_clone_url(repo_url: str) -> str:
    """
    Injects the GitHub token into the HTTPS URL if available.
    """
    if not settings.github_token:
        return repo_url
        
    if repo_url.startswith("https://") and "@" not in repo_url:
        return repo_url.replace("https://", f"https://x-access-token:{settings.github_token}@")
    return repo_url

def clone_repository(repo_url: str, workspace_path: str, commit_sha: str = None, timeout: int = 60):
    """
    Clones the repository securely using subprocess without shell=True.
    """
    secure_url = format_clone_url(repo_url)
    
    try:
        # Clone repo
        # Note: We do not log the full command array because it contains the secure_url with the token.
        subprocess.run(
            ["git", "clone", "--quiet", secure_url, workspace_path],
            check=True,
            shell=False,
            timeout=timeout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Checkout specific SHA if provided
        if commit_sha:
            subprocess.run(
                ["git", "checkout", "--quiet", commit_sha],
                cwd=workspace_path,
                check=True,
                shell=False,
                timeout=timeout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
    except subprocess.TimeoutExpired:
        raise GitServiceError(f"Git operation timed out after {timeout} seconds.")
    except subprocess.CalledProcessError as e:
        # Avoid leaking token in stderr string if printed
        error_msg = e.stderr.decode('utf-8', errors='ignore') if e.stderr else "Unknown Git Error"
        if settings.github_token and settings.github_token in error_msg:
            error_msg = error_msg.replace(settings.github_token, "***MASKED_TOKEN***")
        raise GitServiceError(f"Git operation failed: {error_msg.strip()}")
