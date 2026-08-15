"""Tests for Groq AI suggestion generation."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from main import _parse_ai_json, generate_ai_suggestions, scan_documentation
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ai_json_valid():
    raw = '{"summary":"Good docs","suggestions":[{"area":"readme","priority":"high","suggestion":"Add usage."}]}'
    parsed = _parse_ai_json(raw)
    assert parsed is not None
    assert parsed["summary"] == "Good docs"
    assert len(parsed["suggestions"]) == 1


def test_parse_ai_json_invalid():
    assert _parse_ai_json("not json") is None
    assert _parse_ai_json('{"summary": 1, "suggestions": []}') is None


@pytest.mark.asyncio
async def test_ai_skipped_without_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")
    import main as m
    monkeypatch.setattr(m, "GROQ_API_KEY", "")
    monkeypatch.setattr(m, "ENABLE_AI_SUGGESTIONS", False)
    monkeypatch.setattr(m, "groq_client", None)
    scan = scan_documentation(FIXTURES / "empty_repo")
    result = await generate_ai_suggestions(scan)
    assert result["ai_status"] == "skipped"
    assert result["ai_summary"] is None


@pytest.mark.asyncio
async def test_ai_malformed_response(monkeypatch):
    import main as m
    monkeypatch.setattr(m, "groq_client", AsyncMock())
    m.groq_client.chat.completions.create = AsyncMock(
        return_value=type("R", (), {"choices": [type("C", (), {"message": type("M", (), {"content": "Sure! Here you go"})()})()]})()
    )
    scan = scan_documentation(FIXTURES / "empty_repo")
    result = await generate_ai_suggestions(scan)
    assert result["ai_status"] == "failed"


@pytest.mark.asyncio
async def test_ai_timeout(monkeypatch):
    import main as m

    async def slow(*_a, **_k):
        await asyncio.sleep(5)
        return type("R", (), {"choices": []})()

    mock_client = AsyncMock()
    mock_client.chat.completions.create = slow
    monkeypatch.setattr(m, "groq_client", mock_client)
    monkeypatch.setattr(m, "GROQ_TIMEOUT_SECONDS", 0.01)
    scan = scan_documentation(FIXTURES / "empty_repo")
    result = await generate_ai_suggestions(scan)
    assert result["ai_status"] == "failed"
