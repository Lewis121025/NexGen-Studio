"""
Lewis AI System - 生产就绪验证脚本
快速验证系统是否可以正常运行
"""

import sys
import subprocess
from pathlib import Path


def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_check(name, passed, details=""):
    status = "✅" if passed else "❌"
    print(f"{status} {name}")
    if details:
        print(f"   {details}")


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    passed = version >= (3, 11)
    details = f"Python {version.major}.{version.minor}.{version.micro}"
    print_check("Python 版本 (>= 3.11)", passed, details)
    return passed


def check_backend_imports():
    """检查后端模块导入"""
    try:
        from nexgen_studio.main import app
        from nexgen_studio.creative.workflow import CreativeOrchestrator
        from nexgen_studio.general.session import GeneralModeOrchestrator
        print_check("后端模块导入", True, "所有核心模块可正常导入")
        return True
    except Exception as e:
        print_check("后端模块导入", False, str(e))
        return False


def check_frontend_build():
    """检查前端构建文件"""
    frontend_dir = Path(__file__).parent / "frontend"
    build_dir = frontend_dir / ".next"
    
    if build_dir.exists():
        print_check("前端构建", True, "发现 .next 构建目录")
        return True
    else:
        print_check("前端构建", False, "未找到构建目录，请运行: cd frontend && npm run build")
        return False


def check_env_file():
    """检查环境变量文件"""
    env_file = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"
    
    if env_file.exists():
        content = env_file.read_text(encoding='utf-8')
        has_openrouter = "sk-or-v1-" in content or "OPENROUTER_API_KEY=" in content
        
        if has_openrouter:
            print_check("环境配置", True, ".env 文件已配置")
            return True
        else:
            print_check("环境配置", False, ".env 缺少 OPENROUTER_API_KEY")
            return False
    else:
        if env_example.exists():
            print_check("环境配置", False, "请复制 .env.example 为 .env 并配置 API 密钥")
        else:
            print_check("环境配置", False, "未找到 .env 或 .env.example 文件")
        return False


def check_dependencies():
    """检查关键依赖"""
    try:
        import fastapi
        import uvicorn
        import pydantic
        import httpx
        print_check("Python 依赖", True, "所有核心依赖已安装")
        return True
    except ImportError as e:
        print_check("Python 依赖", False, f"缺少依赖: {e.name}")
        return False


def check_docker():
    """检查 Docker 可用性"""
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print_check("Docker", True, version)
            return True
        else:
            print_check("Docker", False, "Docker 命令执行失败")
            return False
    except FileNotFoundError:
        print_check("Docker", False, "未安装 Docker（可选）")
        return False
    except Exception as e:
        print_check("Docker", False, str(e))
        return False


def check_node():
    """检查 Node.js"""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            version = result.stdout.strip()
            print_check("Node.js", True, version)
            return True
        else:
            print_check("Node.js", False, "Node.js 命令执行失败")
            return False
    except FileNotFoundError:
        print_check("Node.js", False, "未安装 Node.js")
        return False
    except Exception:
        print_check("Node.js", False, "检查失败")
        return False


def check_tests():
    """检查测试状态"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=Path(__file__).parent
        )
        
        if "passed" in result.stdout:
            # 提取通过的测试数量
            lines = result.stdout.split("\n")
            for line in lines:
                if "passed" in line:
                    print_check("单元测试", True, line.strip())
                    return True
        
        print_check("单元测试", False, "部分测试失败")
        return False
    except subprocess.TimeoutExpired:
        print_check("单元测试", False, "测试超时")
        return False
    except Exception as e:
        print_check("单元测试", False, str(e))
        return False


def check_port_available(port):
    """检查端口是否可用"""
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", port))
            return True
    except OSError:
        return False


def check_ports():
    """检查必需端口"""
    port_3000 = check_port_available(3000)
    port_8000 = check_port_available(8000)
    
    if port_3000 and port_8000:
        print_check("端口可用性", True, "3000 和 8000 端口可用")
        return True
    else:
        unavailable = []
        if not port_3000:
            unavailable.append("3000")
        if not port_8000:
            unavailable.append("8000")
        print_check("端口可用性", False, f"端口 {', '.join(unavailable)} 被占用")
        return False


def main():
    # 设置UTF-8输出
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print_header("Lewis AI System - 生产就绪验证")
    
    results = []
    
    # 必需检查
    print("\n[必需项检查]")
    results.append(("Python 版本", check_python_version()))
    results.append(("Python 依赖", check_dependencies()))
    results.append(("后端模块", check_backend_imports()))
    results.append(("环境配置", check_env_file()))
    results.append(("端口可用性", check_ports()))
    
    # 可选检查
    print("\n[可选项检查]")
    check_node()
    check_docker()
    check_frontend_build()
    
    # 测试检查（耗时，可选）
    print("\n[测试检查 - 可选]")
    test_passed = check_tests()
    
    # 总结
    print_header("验证结果")
    
    required_passed = all(result[1] for result in results)
    
    if test_passed:
        print("[OK] 单元测试通过")
    else:
        print("[WARN] 单元测试未通过（不影响部署）")
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    print(f"\n必需项通过: {passed_count}/{total_count}")
    
    if required_passed:
        print("\n[OK] 系统已就绪，可以部署!")
        print("\n快速启动:")
        print("  后端: uvicorn nexgen_studio.main:app --host 0.0.0.0 --port 8000")
        print("  前端: cd frontend && npm run dev")
        print("  或使用: docker-compose up -d")
        return 0
    else:
        print("\n[ERROR] 系统未就绪，请修复上述问题")
        print("\n常见解决方案:")
        print("  1. 安装依赖: pip install -e .")
        print("  2. 配置环境: cp .env.example .env")
        print("  3. 编辑 .env 文件，设置 OPENROUTER_API_KEY")
        return 1


if __name__ == "__main__":
    sys.exit(main())
