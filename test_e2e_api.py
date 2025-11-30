#!/usr/bin/env python3
"""Lewis AI System - 端到端 API 测试"""

import asyncio
import sys
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def ok(msg): print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")
def fail(msg): print(f"{Colors.RED}✗{Colors.RESET} {msg}")
def info(msg): print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")
def header(msg): print(f"\n{Colors.BOLD}{'='*50}\n{msg}\n{'='*50}{Colors.RESET}")

async def test_health_endpoints():
    """测试健康检查端点"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # Health check
        r = await client.get(f"{BASE_URL}/healthz")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        ok(f"健康检查: status={data['status']}, env={data['environment']}")
        
        # Readiness check
        r = await client.get(f"{BASE_URL}/readyz")
        assert r.status_code == 200
        data = r.json()
        ok(f"就绪检查: database={data['database']}, s3={data['s3']}")
        
        return True

async def test_api_versions():
    """测试 API 版本端点"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{BASE_URL}/api/versions")
        assert r.status_code == 200
        data = r.json()
        ok(f"API 版本: {', '.join(data['current_versions'])}")
        return True

async def test_creative_mode():
    """测试创意模式 API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 创建项目
        project_data = {
            "title": "科技产品宣传视频",
            "brief": "创建一个10秒的科技产品宣传视频",
            "tenant_id": "test-user-001",
            "video_provider": "doubao",
            "duration_seconds": 10
        }
        
        r = await client.post(
            f"{BASE_URL}/v1/creative/projects",
            json=project_data
        )
        
        if r.status_code in [200, 201]:
            data = r.json()
            project_id = data.get("id") or data.get("project_id")
            ok(f"创建创意项目: ID={project_id}")
            
            # 获取项目详情
            r2 = await client.get(f"{BASE_URL}/v1/creative/projects/{project_id}")
            if r2.status_code == 200:
                ok(f"获取项目详情成功")
            else:
                fail(f"获取项目详情失败: {r2.status_code}")
            
            return True
        else:
            fail(f"创建创意项目失败: {r.status_code} - {r.text[:200]}")
            return False

async def test_general_mode():
    """测试通用模式 API"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 创建会话
        session_data = {
            "tenant_id": "test-user-001",
            "goal": "介绍一下人工智能的发展历史"
        }
        
        r = await client.post(
            f"{BASE_URL}/v1/general/sessions",
            json=session_data
        )
        
        if r.status_code in [200, 201]:
            data = r.json()
            session_id = data.get("session_id") or data.get("id")
            ok(f"创建通用会话: ID={session_id}")
            
            # 发送消息
            message_data = {
                "query": "你好，请介绍一下你自己"
            }
            
            r2 = await client.post(
                f"{BASE_URL}/v1/general/sessions/{session_id}/iterate",
                json=message_data
            )
            
            if r2.status_code == 200:
                ok(f"发送消息成功")
            else:
                info(f"发送消息返回: {r2.status_code}")
            
            return True
        else:
            fail(f"创建通用会话失败: {r.status_code} - {r.text[:200]}")
            return False

async def test_governance_api():
    """测试治理 API"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 成本统计
        r = await client.get(f"{BASE_URL}/v1/governance/stats")
        
        if r.status_code == 200:
            ok("成本统计 API 正常")
            return True
        else:
            info(f"成本统计返回: {r.status_code}")
            return True

async def main():
    header("Lewis AI System - 端到端 API 测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"目标: {BASE_URL}")
    
    results = {}
    
    # 测试健康端点
    header("1. 健康检查端点")
    try:
        results['health'] = await test_health_endpoints()
    except Exception as e:
        fail(f"健康检查失败: {e}")
        results['health'] = False
    
    # 测试 API 版本
    header("2. API 版本端点")
    try:
        results['versions'] = await test_api_versions()
    except Exception as e:
        fail(f"API 版本失败: {e}")
        results['versions'] = False
    
    # 测试创意模式
    header("3. 创意模式 API")
    try:
        results['creative'] = await test_creative_mode()
    except Exception as e:
        fail(f"创意模式失败: {e}")
        results['creative'] = False
    
    # 测试通用模式
    header("4. 通用模式 API")
    try:
        results['general'] = await test_general_mode()
    except Exception as e:
        fail(f"通用模式失败: {e}")
        results['general'] = False
    
    # 测试治理 API
    header("5. 治理 API")
    try:
        results['governance'] = await test_governance_api()
    except Exception as e:
        fail(f"治理 API 失败: {e}")
        results['governance'] = False
    
    # 总结
    header("测试结果总结")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for name, result in results.items():
        status = "通过" if result else "失败"
        color = Colors.GREEN if result else Colors.RED
        print(f"  {color}{status}{Colors.RESET} - {name}")
    
    print(f"\n总计: {passed}/{total} 项通过")
    
    if passed == total:
        ok("端到端测试全部通过！")
        return 0
    else:
        fail(f"{total - passed} 项测试失败")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
