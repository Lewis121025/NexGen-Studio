import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from nexgen_studio import auth
from nexgen_studio.config import settings


@pytest.mark.asyncio
async def test_configured_api_key_is_accepted(monkeypatch):
    api_key = "lewis_test_key"
    monkeypatch.setattr(settings, "service_api_keys", [api_key])
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=api_key)

    user = await auth.get_current_user(credentials)

    assert user["auth_type"] == "api_key"
    assert user["user_id"].startswith("user_")


@pytest.mark.asyncio
async def test_unknown_api_key_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "service_api_keys", ["lewis_valid"])
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="lewis_invalid")

    with pytest.raises(HTTPException) as exc:
        await auth.get_current_user(credentials)

    assert exc.value.status_code == 401
    assert "Invalid" in exc.value.detail
