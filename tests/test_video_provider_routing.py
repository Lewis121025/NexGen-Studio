"""测试视频提供商路由功能。"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from lewis_ai_system.main import app
from lewis_ai_system.creative.models import CreativeProjectCreateRequest
from lewis_ai_system.config import settings

client = TestClient(app, base_url="http://localhost", raise_server_exceptions=False)


class TestVideoProviderRouting:
    """测试视频提供商路由功能。"""

    def test_get_available_video_providers(self):
        """测试获取可用视频提供商列表。"""
        response = client.get("/v1/creative/video-providers")
        assert response.status_code == 200
        data = response.json()
        assert "providers" in data
        assert isinstance(data["providers"], list)
        assert len(data["providers"]) > 0
        # 确保默认提供商在列表中（系统已简化为只使用 doubao）
        assert "doubao" in data["providers"]

    @patch('lewis_ai_system.creative.workflow.CreativeOrchestrator.create_project')
    def test_create_project_with_video_provider(self, mock_create_project):
        """测试创建项目时指定视频提供商。"""
        # 模拟项目，使用真实的 CreativeProject 对象
        from lewis_ai_system.creative.models import CreativeProject, CreativeProjectState
        mock_project = CreativeProject(
            id="test-project-id",
            tenant_id="demo",
            title="测试项目",
            brief="这是一个测试项目",
            video_provider="pika",
            state=CreativeProjectState.BRIEF_PENDING
        )
        mock_create_project.return_value = mock_project
        
        # 创建项目请求，指定视频提供商
        payload = {
            "title": "测试项目",
            "brief": "这是一个测试项目",
            "duration_seconds": 30,
            "style": "cinematic",
            "video_provider": "pika",  # 指定非默认提供商
        }
        
        response = client.post("/v1/creative/projects", json=payload)
        assert response.status_code == 201
        
        # 验证 orchestrator 被调用时包含了视频提供商
        mock_create_project.assert_called_once()
        call_args = mock_create_project.call_args[0][0]
        assert isinstance(call_args, CreativeProjectCreateRequest)
        assert call_args.video_provider == "pika"

    @patch('lewis_ai_system.creative.workflow.CreativeOrchestrator.create_project')
    def test_create_project_with_default_video_provider(self, mock_create_project):
        """测试创建项目时使用默认视频提供商。"""
        # 模拟项目，使用真实的 CreativeProject 对象
        from lewis_ai_system.creative.models import CreativeProject, CreativeProjectState
        mock_project = CreativeProject(
            id="test-project-id",
            tenant_id="demo",
            title="测试项目",
            brief="这是一个测试项目",
            video_provider="runway",
            state=CreativeProjectState.BRIEF_PENDING
        )
        mock_create_project.return_value = mock_project
        
        # 创建项目请求，不指定视频提供商
        payload = {
            "title": "测试项目",
            "brief": "这是一个测试项目",
            "duration_seconds": 30,
            "style": "cinematic",
        }
        
        response = client.post("/v1/creative/projects", json=payload)
        assert response.status_code == 201
        
        # 验证 orchestrator 被调用时使用了默认提供商
        mock_create_project.assert_called_once()
        call_args = mock_create_project.call_args[0][0]
        assert isinstance(call_args, CreativeProjectCreateRequest)
        assert call_args.video_provider == "runway"  # 默认提供商

    def test_video_provider_config_validation(self):
        """测试视频提供商配置验证。"""
        # 验证配置中有可用的视频提供商列表
        assert hasattr(settings, 'available_video_providers')
        assert isinstance(settings.available_video_providers, list)
        assert len(settings.available_video_providers) > 0
        
        # 验证默认提供商在可用列表中
        assert settings.video_provider_default in settings.available_video_providers
        
        # 验证所有支持的提供商都在列表中
        supported_providers = ["runway", "pika", "runware", "doubao", "mock"]
        for provider in supported_providers:
            if provider in settings.available_video_providers:
                assert provider in settings.available_video_providers
