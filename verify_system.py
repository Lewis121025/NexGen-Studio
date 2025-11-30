#!/usr/bin/env python3
"""Lewis AI System - 完整系统验证脚本"""

import asyncio
import sys
import os
import time
import subprocess
import signal
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def print_ok(msg):
    print(f"{Colors.GREEN}✓{Colors.RESET} {msg}")

def print_fail(msg):
    print(f"{Colors.RED}✗{Colors.RESET} {msg}")

def print_warn(msg):
    print(f"{Colors.YELLOW}⚠{Colors.RESET} {msg}")

def print_info(msg):
    print(f"{Colors.BLUE}ℹ{Colors.RESET} {msg}")

def print_header(msg):
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{msg}{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")

async def test_database_connection():
    """测试数据库连接"""
    try:
        import asyncpg
        conn = await asyncpg.connect(
            'postgresql://lewis:lewis_pass@localhost:5432/lewis_db',
            timeout=5
        )
        result = await conn.fetchval('SELECT 1')
        await conn.close()
        print_ok(f"PostgreSQL 连接成功")
        return True
    except Exception as e:
        print_fail(f"PostgreSQL 连接失败: {e}")
        return False

def test_config_loading():
    """测试配置加载"""
    try:
        from lewis_ai_system.config import settings
        print_ok(f"配置加载成功")
        print_info(f"  环境: {settings.environment}")
        print_info(f"  数据库: {settings.database_url[:50]}...")
        print_info(f"  Redis: {'启用' if settings.redis_enabled else '禁用'}")
        print_info(f"  LLM 模式: {settings.llm_provider_mode}")
        print_info(f"  视频提供商: {settings.video_provider_default}")
        return True
    except Exception as e:
        print_fail(f"配置加载失败: {e}")
        return False

def test_module_imports():
    """测试核心模块导入"""
    modules = [
        ('lewis_ai_system.main', 'FastAPI 应用'),
        ('lewis_ai_system.database', '数据库模块'),
        ('lewis_ai_system.providers', '提供商模块'),
        ('lewis_ai_system.tooling', '工具模块'),
        ('lewis_ai_system.creative.workflow', '创意工作流'),
        ('lewis_ai_system.general.session', '通用会话'),
        ('lewis_ai_system.agents.planning', '规划代理'),
        ('lewis_ai_system.agents.creative', '创意代理'),
        ('lewis_ai_system.agents.general', '通用代理'),
    ]
    
    success = True
    for module_name, description in modules:
        try:
            __import__(module_name)
            print_ok(f"{description} ({module_name})")
        except Exception as e:
            print_fail(f"{description} 导入失败: {e}")
            success = False
    
    return success

async def test_fastapi_app():
    """测试 FastAPI 应用"""
    try:
        from lewis_ai_system.main import app
        print_ok("FastAPI 应用实例化成功")
        
        # 检查路由
        routes = [route.path for route in app.routes]
        print_info(f"  已注册 {len(routes)} 个路由")
        
        # 检查关键端点
        key_endpoints = ['/', '/healthz', '/readyz', '/docs', '/api/versions']
        for endpoint in key_endpoints:
            if endpoint in routes or any(endpoint in r for r in routes):
                print_ok(f"  端点 {endpoint} 已注册")
            else:
                print_warn(f"  端点 {endpoint} 未找到")
        
        return True
    except Exception as e:
        print_fail(f"FastAPI 应用测试失败: {e}")
        return False

async def test_api_endpoints():
    """测试 API 端点"""
    import httpx
    
    base_url = "http://localhost:8000"
    
    endpoints = [
        ('/', 'GET', 200, '根端点'),
        ('/healthz', 'GET', 200, '健康检查'),
        ('/readyz', 'GET', 200, '就绪检查'),
        ('/api/versions', 'GET', 200, 'API 版本'),
        ('/docs', 'GET', 200, 'API 文档'),
    ]
    
    success = True
    async with httpx.AsyncClient(timeout=10.0) as client:
        for path, method, expected_status, description in endpoints:
            try:
                if method == 'GET':
                    response = await client.get(f"{base_url}{path}")
                
                if response.status_code == expected_status:
                    print_ok(f"{description} ({path}) - 状态码 {response.status_code}")
                else:
                    print_fail(f"{description} ({path}) - 期望 {expected_status}, 得到 {response.status_code}")
                    success = False
            except httpx.ConnectError:
                print_fail(f"{description} ({path}) - 无法连接到服务器")
                success = False
            except Exception as e:
                print_fail(f"{description} ({path}) - 错误: {e}")
                success = False
    
    return success

def run_tests():
    """运行测试套件"""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pytest', 'tests/', '-v', '--tb=short', '-q'],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            print_ok("所有测试通过")
            # 解析测试结果
            for line in result.stdout.split('\n'):
                if 'passed' in line or 'failed' in line:
                    print_info(f"  {line.strip()}")
            return True
        else:
            print_fail("部分测试失败")
            print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
            return False
    except subprocess.TimeoutExpired:
        print_fail("测试超时")
        return False
    except Exception as e:
        print_fail(f"测试运行错误: {e}")
        return False

async def main():
    """主函数"""
    print_header("Lewis AI System - 系统验证")
    
    results = {}
    
    # 1. 配置测试
    print_header("1. 配置验证")
    results['config'] = test_config_loading()
    
    # 2. 模块导入测试
    print_header("2. 模块导入验证")
    results['modules'] = test_module_imports()
    
    # 3. 数据库连接测试
    print_header("3. 数据库连接验证")
    results['database'] = await test_database_connection()
    
    # 4. FastAPI 应用测试
    print_header("4. FastAPI 应用验证")
    results['fastapi'] = await test_fastapi_app()
    
    # 5. 测试套件
    print_header("5. 测试套件验证")
    results['tests'] = run_tests()
    
    # 总结
    print_header("验证结果总结")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for name, result in results.items():
        status = "通过" if result else "失败"
        color = Colors.GREEN if result else Colors.RED
        print(f"  {color}{status}{Colors.RESET} - {name}")
    
    print(f"\n总计: {passed}/{total} 项通过")
    
    if passed == total:
        print_ok("系统验证全部通过！")
        return 0
    else:
        print_fail(f"系统验证存在 {total - passed} 项失败")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
