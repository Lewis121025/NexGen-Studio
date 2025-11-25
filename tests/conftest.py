import sys
from pathlib import Path

import pytest

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
    from lewis_ai_system.creative import workflow as creative_workflow
    from lewis_ai_system.general import session as general_session

    original_mode = settings.llm_provider_mode
    original_key = settings.openrouter_api_key
    original_env = settings.environment
    
    settings.llm_provider_mode = "mock"
    settings.openrouter_api_key = None
    settings.environment = "development"  # Disable TrustedHostMiddleware
    
    providers.default_llm_provider = providers.EchoLLMProvider()
    creative_workflow.default_llm_provider = providers.default_llm_provider
    general_session.default_llm_provider = providers.default_llm_provider
    agent_pool.planning.provider = providers.default_llm_provider
    agent_pool.formatter.provider = providers.default_llm_provider
    yield
    settings.llm_provider_mode = original_mode
    settings.openrouter_api_key = original_key
    settings.environment = original_env
