"""检查系统是否已配置为执行真实任务。"""

import os
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nexgen_studio.config import settings


def check_provider_config() -> dict[str, bool]:
    """检查Provider配置状态。"""
    results = {}
    
    # LLM Provider
    if settings.llm_provider_mode == "openrouter":
        results["LLM Provider (OpenRouter)"] = bool(settings.openrouter_api_key)
    else:
        results["LLM Provider"] = False
        print("  [!] LLM_PROVIDER_MODE 设置为 'mock'，需要设置为 'openrouter' 才能使用真实LLM")
    
    # Video Providers
    results["Runway Video"] = bool(settings.runway_api_key)
    results["Pika Video"] = bool(settings.pika_api_key)
    results["Runware Video"] = bool(settings.runware_api_key)
    results["Doubao Video"] = bool(settings.doubao_api_key)
    
    # TTS Provider
    results["ElevenLabs TTS"] = bool(settings.elevenlabs_api_key)
    
    # Search Provider
    results["Tavily Search"] = bool(settings.tavily_api_key)
    
    # Scrape Provider
    results["Firecrawl Scrape"] = bool(settings.firecrawl_api_key)
    
    return results


def check_infrastructure_config() -> dict[str, bool]:
    """检查基础设施配置状态。"""
    results = {}
    
    # Database
    results["PostgreSQL Database"] = bool(settings.database_url)
    
    # Redis
    results["Redis Cache"] = bool(settings.redis_url) and settings.redis_enabled
    
    # Vector DB
    if settings.vector_db_type != "none":
        results["Vector Database"] = bool(settings.vector_db_url)
    else:
        results["Vector Database"] = False
    
    # S3 Storage
    results["S3 Storage"] = bool(
        settings.s3_access_key and 
        settings.s3_secret_key and 
        settings.s3_bucket_name
    )
    
    return results


def main():
    """主检查函数。"""
    print("=" * 60)
    print("Lewis AI System - 生产环境就绪检查")
    print("=" * 60)
    print()
    
    # 检查Provider配置
    print("Provider 配置检查:")
    print("-" * 60)
    provider_results = check_provider_config()
    for provider, configured in provider_results.items():
        status = "[OK] 已配置" if configured else "[X] 未配置"
        print(f"  {status} - {provider}")
    print()
    
    # 检查基础设施
    print("基础设施配置检查:")
    print("-" * 60)
    infra_results = check_infrastructure_config()
    for infra, configured in infra_results.items():
        status = "[OK] 已配置" if configured else "[!] 未配置（可选）"
        print(f"  {status} - {infra}")
    print()
    
    # 总结
    print("=" * 60)
    print("配置总结:")
    print("-" * 60)
    
    required_providers = ["LLM Provider (OpenRouter)"]
    optional_providers = [k for k in provider_results.keys() if k not in required_providers]
    
    required_configured = all(provider_results.get(p, False) for p in required_providers)
    optional_configured = sum(provider_results.get(p, False) for p in optional_providers)
    
    if required_configured:
        print("[OK] 核心Provider已配置，可以执行真实任务！")
        print()
        print(f"可选Provider配置: {optional_configured}/{len(optional_providers)}")
        if optional_configured < len(optional_providers):
            print("   提示: 配置更多Provider可以获得更好的功能支持")
    else:
        print("[X] 核心Provider未配置，系统将使用Mock模式")
        print()
        print("需要配置:")
        print("   1. 设置 LLM_PROVIDER_MODE=openrouter")
        print("   2. 配置 OPENROUTER_API_KEY")
        print()
        print("   可选配置:")
        print("   - RUNWAY_API_KEY / PIKA_API_KEY / RUNWARE_API_KEY (视频生成)")
        print("   - ELEVENLABS_API_KEY (语音合成)")
        print("   - TAVILY_API_KEY (网络搜索)")
        print("   - FIRECRAWL_API_KEY (网页抓取)")
    
    print()
    print("=" * 60)
    
    # 返回状态码
    return 0 if required_configured else 1


if __name__ == "__main__":
    sys.exit(main())

