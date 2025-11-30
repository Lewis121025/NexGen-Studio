import os
import sys
from pathlib import Path

import pytest

# Load .env file first before any other imports
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# Store original API keys before any modifications
_original_tavily = os.environ.get("TAVILY_API_KEY")
_original_firecrawl = os.environ.get("FIRECRAWL_API_KEY")
_original_e2b = os.environ.get("E2B_API_KEY")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(scope="session", autouse=True)
def configure_test_providers():
    """Force providers to run in mock mode during pytest."""
    from lewis_ai_system.config import settings
    from lewis_ai_system import providers
    from lewis_ai_system.agents import agent_pool

    original_mode = settings.llm_provider_mode
    original_key = settings.openrouter_api_key
    original_env = settings.environment
    original_e2b_key = settings.e2b_api_key
    original_tavily = settings.tavily_api_key
    original_firecrawl = settings.firecrawl_api_key
    
    settings.llm_provider_mode = "mock"
    settings.openrouter_api_key = None
    settings.environment = "development"  # Disable TrustedHostMiddleware
    settings.tavily_api_key = None  # Skip real network calls
    settings.firecrawl_api_key = None
    # Don't set E2B key - sandbox tests will be skipped by default
    
    providers.default_llm_provider = providers.EchoLLMProvider()
    agent_pool.planning.provider = providers.default_llm_provider
    agent_pool.formatter.provider = providers.default_llm_provider
    agent_pool.creative.provider = providers.default_llm_provider
    agent_pool.general.provider = providers.default_llm_provider
    yield
    settings.llm_provider_mode = original_mode
    settings.openrouter_api_key = original_key
    settings.environment = original_env
    settings.e2b_api_key = original_e2b_key
    settings.tavily_api_key = original_tavily
    settings.firecrawl_api_key = original_firecrawl


@pytest.fixture
def repository():
    """Shared in-memory creative repository for tests."""
    from lewis_ai_system.creative.repository import InMemoryCreativeProjectRepository

    return InMemoryCreativeProjectRepository()


@pytest.fixture
def orchestrator(repository):
    """Creative orchestrator wired to in-memory repository."""
    from lewis_ai_system.creative.workflow import CreativeOrchestrator

    return CreativeOrchestrator(repository=repository)


@pytest.fixture
def batch_service():
    """Batch processing service for creative consistency tests."""
    from lewis_ai_system.creative.batch_processing import BatchProcessingService

    return BatchProcessingService()
