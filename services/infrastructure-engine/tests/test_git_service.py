import pytest
from unittest.mock import patch, MagicMock
from app.services.git_service import temporary_workspace, format_clone_url, clone_repository, GitServiceError
import subprocess

def test_format_clone_url():
    url = "https://github.com/codelens/repo.git"
    with patch("app.services.git_service.settings") as mock_settings:
        mock_settings.github_token = "secret-token"
        secure_url = format_clone_url(url)
        assert "x-access-token:secret-token@" in secure_url
        
def test_format_clone_url_no_token():
    url = "https://github.com/codelens/repo.git"
    with patch("app.services.git_service.settings") as mock_settings:
        mock_settings.github_token = ""
        secure_url = format_clone_url(url)
        assert "x-access-token" not in secure_url

@pytest.mark.asyncio
async def test_temporary_workspace():
    async with temporary_workspace("test-run-id") as workspace:
        assert workspace.startswith("/tmp/codelens/workspace/run_test-run-id_")

@patch("app.services.git_service.subprocess.run")
def test_clone_repository_success(mock_run):
    clone_repository("https://github.com/test", "/tmp/ws")
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert "git" in args[0]
    assert "clone" in args[0]
    assert kwargs.get("shell") is False

@patch("app.services.git_service.subprocess.run")
def test_clone_repository_timeout(mock_run):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=60)
    with pytest.raises(GitServiceError) as exc_info:
        clone_repository("https://github.com/test", "/tmp/ws")
    assert "timed out" in str(exc_info.value)
