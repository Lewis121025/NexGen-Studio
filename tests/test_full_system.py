import uuid

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from lewis_ai_system.creative.models import CreativeProject, CreativeProjectState
from lewis_ai_system.general.models import GeneralSession, GeneralSessionState
from lewis_ai_system.main import app
from lewis_ai_system.config import settings

client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)

@pytest.fixture
def mock_providers():
    """Patch routers with lightweight orchestrators + repositories."""

    class FakeCreativeOrchestrator:
        def __init__(self) -> None:
            self.projects: dict[str, CreativeProject] = {}

        async def create_project(self, payload):
            project = CreativeProject(
                id=str(uuid.uuid4()),
                tenant_id=payload.tenant_id,
                title=payload.title,
                brief=payload.brief,
            )
            project.mark_state(CreativeProjectState.SCRIPT_PENDING)
            self.projects[project.id] = project
            return project

        async def approve_script(self, project_id: str) -> CreativeProject:
            project = self.projects[project_id]
            project.mark_state(CreativeProjectState.SCRIPT_REVIEW)
            return project

        async def advance(self, project_id: str) -> CreativeProject:
            return self.projects[project_id]

    class FakeCreativeRepository:
        def __init__(self, store: dict[str, CreativeProject]) -> None:
            self._store = store

        async def get(self, project_id: str) -> CreativeProject:
            return self._store[project_id]

    class FakeGeneralOrchestrator:
        def __init__(self) -> None:
            self.sessions: dict[str, GeneralSession] = {}

        async def create_session(self, payload):
            session = GeneralSession(
                id=str(uuid.uuid4()),
                tenant_id=payload.tenant_id,
                goal=payload.goal,
                max_iterations=payload.max_iterations,
            )
            self.sessions[session.id] = session
            return session

        async def run_iteration(self, session_id: str, prompt_text: str | None = None) -> GeneralSession:
            session = self.sessions[session_id]
            session.summary = "Mock summary"
            session.messages.append("Final Answer: Mock summary")
            session.mark_state(GeneralSessionState.COMPLETED)
            return session

    class FakeGeneralRepository:
        def __init__(self, store: dict[str, GeneralSession]) -> None:
            self._store = store

        async def get(self, session_id: str) -> GeneralSession:
            return self._store[session_id]

    fake_creative = FakeCreativeOrchestrator()
    fake_general = FakeGeneralOrchestrator()

    with (
        patch("lewis_ai_system.routers.creative.creative_orchestrator", new=fake_creative),
        patch("lewis_ai_system.routers.creative.creative_repository", new=FakeCreativeRepository(fake_creative.projects)),
        patch("lewis_ai_system.routers.general.general_orchestrator", new=fake_general),
        patch("lewis_ai_system.routers.general.general_repository", new=FakeGeneralRepository(fake_general.sessions)),
    ):
        yield

def test_health_endpoints():
    response = client.get("/healthz")
    assert response.status_code == 200, f"Status: {response.status_code}, Body: {response.text}"
    assert response.json()["status"] == "ok"

    response = client.get("/readyz")
    assert response.status_code == 200, f"Status: {response.status_code}, Body: {response.text}"
    # Database might be not_initialized in test env without real DB
    assert "database" in response.json()

def test_creative_mode_lifecycle(mock_providers):
    # 1. Create Project
    response = client.post("/creative/projects", json={
        "title": "Test Project",
        "brief": "A test project brief."
    })
    assert response.status_code == 201, f"Status: {response.status_code}, Body: {response.text}"
    project = response.json()["project"]
    project_id = project["id"]
    
    # 2. Generate Script (Mocked)
    # Note: In a real scenario, we'd trigger the workflow. 
    # For now, we check if the endpoint exists and accepts the request.
    # Assuming there's an endpoint to trigger generation or it happens automatically.
    # If the current API is async/background, we might just check status.
    
    # Let's check project status
    response = client.get(f"/creative/projects/{project_id}")
    assert response.status_code == 200, f"Status: {response.status_code}, Body: {response.text}"
    assert response.json()["project"]["title"] == "Test Project"

def test_general_mode_lifecycle(mock_providers):
    # 1. Create Session
    response = client.post("/general/sessions", json={
        "goal": "Test Goal",
        "user_id": "test_user"
    })
    assert response.status_code == 201, f"Status: {response.status_code}, Body: {response.text}"
    session_id = response.json()["session"]["id"]
    
    # 2. Iterate (Mocked)
    response = client.post(f"/general/sessions/{session_id}/iterate", json={
        "input": "Start working"
    })
    assert response.status_code == 200, f"Status: {response.status_code}, Body: {response.text}"
    assert response.json()["session"]["state"] == GeneralSessionState.COMPLETED
    
    # 3. Check History
    response = client.get(f"/general/sessions/{session_id}")
    assert response.status_code == 200, f"Status: {response.status_code}, Body: {response.text}"
    assert response.json()["session"]["goal"] == "Test Goal"

def test_global_exception_handler():
    # Add a route that raises an exception
    @app.get("/force_error")
    async def force_error():
        raise ValueError("Test Error")
    
    response = client.get("/force_error")
    assert response.status_code == 500, f"Status: {response.status_code}, Body: {response.text}"
    assert response.json()["detail"] == "内部服务器错误"
    assert "Test Error" in response.json()["error"]
