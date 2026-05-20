from types import SimpleNamespace

import pytest

from backend.infrastructure.config.settings import Settings
from backend.infrastructure.services import llm_analysis_service as llm_module
from backend.infrastructure.services.llm_analysis_service import LLMAnalysisService


class _FakeCompletionClient:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content),
                )
            ]
        )


class _FakeGroqClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=_FakeCompletionClient(content))


@pytest.mark.asyncio
async def test_llm_analysis_service_parses_groq_json(monkeypatch, tmp_path):
    fake_content = (
        '{"summary":"Test summary","sentiment":"Neutral","entities":{"organizations":["UN"]},'
        '"themes":["Diplomacy"],"confidence":0.83}'
    )

    monkeypatch.setattr(llm_module, "AsyncGroq", lambda api_key: _FakeGroqClient(fake_content))

    settings = Settings(
        gcp_project_id="test-project",
        groq_api_key="test-groq-key",
        hot_tier_path=str(tmp_path / "hot"),
        cache_path=str(tmp_path / "cache"),
    )

    service = LLMAnalysisService(settings)
    analysis = await service.analyze_event("Article text")

    assert analysis.summary == "Test summary"
    assert analysis.sentiment == "Neutral"
    assert analysis.entities.organizations == ["UN"]
    assert analysis.themes == ["Diplomacy"]
    assert analysis.confidence == 0.83


@pytest.mark.asyncio
async def test_llm_analysis_service_sends_json_response_format(monkeypatch, tmp_path):
    fake_completion = _FakeCompletionClient(
        '{"summary":"Test summary","sentiment":"Positive","entities":{"countries":[],"organizations":[],"persons":[]},"themes":[],"confidence":0.5}'
    )
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completion))
    monkeypatch.setattr(llm_module, "AsyncGroq", lambda api_key: fake_client)

    settings = Settings(
        gcp_project_id="test-project",
        groq_api_key="test-groq-key",
        hot_tier_path=str(tmp_path / "hot"),
        cache_path=str(tmp_path / "cache"),
    )

    service = LLMAnalysisService(settings)
    await service.analyze_event("Article text")

    assert fake_completion.calls
    assert fake_completion.calls[0]["response_format"] == {"type": "json_object"}
