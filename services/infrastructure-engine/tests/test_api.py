import pytest
from fastapi.testclient import TestClient
from app.main import app
import json

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "infrastructure-engine"}

def test_analyze_endpoint():
    payload = {
        "runId": "test-uuid",
        "repositoryId": "test-repo",
        "repoUrl": "https://github.com/codelens/test",
        "commitSha": "abcdef",
        "branch": "main"
    }
    
    # We mock the git service so it doesn't actually clone during the test
    with pytest.MonkeyPatch.context() as m:
        m.setattr("app.api.routes.clone_repository", lambda **kwargs: None)
        
        response = client.post("/internal/analyze", json=payload)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/x-ndjson"
        
        lines = [line for line in response.text.split("\n") if line.strip()]
        assert len(lines) >= 3
        
        # Check first event
        started_event = json.loads(lines[0])
        assert started_event["stage"] == "analysis"
        assert started_event["status"] == "started"
        
        # Check last event
        final_event = json.loads(lines[-1])
        assert final_event.get("final_result", {}).get("status") == "success"
