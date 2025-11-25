import pytest

from nexgen_studio import providers
from nexgen_studio.config import settings


@pytest.fixture(autouse=True)
def _restore_settings():
    """Ensure provider-related settings are restored after each test."""
    snapshot = {
        "llm_provider_mode": settings.llm_provider_mode,
        "openrouter_api_key": settings.openrouter_api_key,
        "runware_api_key": settings.runware_api_key,
        "runway_api_key": settings.runway_api_key,
        "pika_api_key": settings.pika_api_key,
        "elevenlabs_api_key": settings.elevenlabs_api_key,
    }
    yield
    for key, value in snapshot.items():
        setattr(settings, key, value)


def test_llm_provider_uses_echo_by_default(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_mode", "mock")
    provider = providers._build_default_llm_provider()
    assert isinstance(provider, providers.EchoLLMProvider)


def test_llm_provider_switches_to_openrouter(monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_mode", "openrouter")
    monkeypatch.setattr(settings, "openrouter_api_key", "test-key")
    provider = providers._build_default_llm_provider()
    assert isinstance(provider, providers.OpenRouterLLMProvider)


def test_video_provider_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "runware_api_key", None)
    monkeypatch.setattr(settings, "runway_api_key", None)
    monkeypatch.setattr(settings, "pika_api_key", None)
    provider = providers.get_video_provider("runway")
    assert isinstance(provider, providers.MockVideoProvider)


def test_video_provider_prefers_runway_when_configured(monkeypatch):
    monkeypatch.setattr(settings, "runway_api_key", "runway-key")
    provider = providers.get_video_provider("runway")
    assert isinstance(provider, providers.RunwayVideoProvider)


def test_video_provider_supports_runware(monkeypatch):
    monkeypatch.setattr(settings, "runware_api_key", "runware-key")
    provider = providers.get_video_provider("runware")
    assert isinstance(provider, providers.RunwareVideoProvider)


def test_tts_provider_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "elevenlabs_api_key", None)
    provider = providers.get_tts_provider("elevenlabs")
    assert isinstance(provider, providers.MockTTSProvider)


def test_tts_provider_uses_elevenlabs_when_available(monkeypatch):
    monkeypatch.setattr(settings, "elevenlabs_api_key", "tts-key")
    provider = providers.get_tts_provider("elevenlabs")
    assert isinstance(provider, providers.ElevenLabsTTSProvider)


# ============================================================================
# External API Provider Tests (Tavily, E2B, Firecrawl)
# ============================================================================


def test_search_provider_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", None)
    provider = providers.get_search_provider()
    assert isinstance(provider, providers.MockSearchProvider)


def test_search_provider_uses_tavily_when_available(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "tavily-key")
    provider = providers.get_search_provider()
    assert isinstance(provider, providers.TavilySearchProvider)


def test_search_provider_override_mock_even_with_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", "tavily-key")
    provider = providers.get_search_provider("mock")
    assert isinstance(provider, providers.MockSearchProvider)


def test_search_provider_override_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "tavily_api_key", None)
    with pytest.raises(RuntimeError):
        providers.get_search_provider("tavily")


def test_sandbox_provider_falls_back_to_local(monkeypatch):
    monkeypatch.setattr(settings, "e2b_api_key", None)
    provider = providers.get_sandbox_provider()
    assert isinstance(provider, providers.LocalSandboxProvider)


def test_sandbox_provider_uses_e2b_when_available(monkeypatch):
    monkeypatch.setattr(settings, "e2b_api_key", "e2b-key")
    provider = providers.get_sandbox_provider()
    assert isinstance(provider, providers.E2BSandboxProvider)


def test_scrape_provider_falls_back_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "firecrawl_api_key", None)
    provider = providers.get_scrape_provider()
    assert isinstance(provider, providers.MockScrapeProvider)


def test_scrape_provider_uses_firecrawl_when_available(monkeypatch):
    monkeypatch.setattr(settings, "firecrawl_api_key", "firecrawl-key")
    provider = providers.get_scrape_provider()
    assert isinstance(provider, providers.FirecrawlScrapeProvider)


def test_scrape_provider_override_mock(monkeypatch):
    monkeypatch.setattr(settings, "firecrawl_api_key", "firecrawl-key")
    provider = providers.get_scrape_provider("mock")
    assert isinstance(provider, providers.MockScrapeProvider)


def test_scrape_provider_override_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "firecrawl_api_key", None)
    with pytest.raises(RuntimeError):
        providers.get_scrape_provider("firecrawl")
