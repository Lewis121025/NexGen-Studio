"""
数据初始化与种子数据脚本
用于创建初始用户、示例项目和测试数据
"""

import asyncio
import secrets
from datetime import datetime, timezone

from lewis_ai_system.database import (
    db_manager,
    User,
    CreativeProject,
    Conversation,
)
from lewis_ai_system.config import settings
from lewis_ai_system.instrumentation import get_logger

logger = get_logger()


async def create_seed_users():
    """创建种子用户"""
    async with db_manager.get_session() as db:
        from sqlalchemy import select
        
        # 管理员用户
        admin_external_id = "admin_beta_001"
        stmt = select(User).where(User.external_id == admin_external_id)
        result = await db.execute(stmt)
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = User(
                external_id=admin_external_id,
                user_id=admin_external_id,
                email="admin@lewis-ai-beta.com",
                is_active=True,
                is_admin=True,
                credits_usd=1000.0,  # 管理员赠送 $1000
                tier="enterprise",
            )
            db.add(admin)
            logger.info(f"✅ 创建管理员用户: {admin.email}")
        else:
            logger.info(f"⏭️  管理员用户已存在: {admin.email}")
        
        # 示例内测用户
        demo_users = [
            {
                "external_id": "beta_user_001",
                "email": "demo1@lewis-ai-beta.com",
                "credits": 100.0,
                "tier": "beta",
            },
            {
                "external_id": "beta_user_002",
                "email": "demo2@lewis-ai-beta.com",
                "credits": 100.0,
                "tier": "beta",
            },
        ]
        
        for user_data in demo_users:
            stmt = select(User).where(User.external_id == user_data["external_id"])
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            
            if not existing:
                user = User(
                    external_id=user_data["external_id"],
                    user_id=user_data["external_id"],
                    email=user_data["email"],
                    is_active=True,
                    is_admin=False,
                    credits_usd=user_data["credits"],
                    tier=user_data["tier"],
                )
                db.add(user)
                logger.info(f"✅ 创建内测用户: {user.email}")
            else:
                logger.info(f"⏭️  内测用户已存在: {existing.email}")
        
        await db.commit()


async def create_seed_projects():
    """创建示例创意项目"""
    async with db_manager.get_session() as db:
        from sqlalchemy import select
        
        # 检查是否已有项目
        stmt = select(CreativeProject).limit(1)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info("⏭️  已有创意项目，跳过种子数据创建")
            return
        
        # 创建示例项目
        demo_projects = [
            {
                "external_id": f"demo_project_{secrets.token_hex(8)}",
                "user_id": "beta_user_001",
                "title": "科技产品宣传片",
                "brief": "为一款AI助手产品制作30秒的宣传视频，风格现代科技感，突出智能交互功能。",
                "duration_seconds": 30,
                "style": "cinematic",
                "status": "initiated",
                "budget_usd": 50.0,
            },
            {
                "external_id": f"demo_project_{secrets.token_hex(8)}",
                "user_id": "beta_user_002",
                "title": "品牌故事短片",
                "brief": "讲述一个创业团队的故事，温馨感人，展示团队协作精神。",
                "duration_seconds": 45,
                "style": "documentary",
                "status": "initiated",
                "budget_usd": 80.0,
            },
        ]
        
        for project_data in demo_projects:
            project = CreativeProject(**project_data)
            db.add(project)
            logger.info(f"✅ 创建示例项目: {project.title}")
        
        await db.commit()


async def create_seed_conversations():
    """创建示例对话会话"""
    async with db_manager.get_session() as db:
        from sqlalchemy import select
        
        # 检查是否已有会话
        stmt = select(Conversation).limit(1)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            logger.info("⏭️  已有对话会话，跳过种子数据创建")
            return
        
        # 创建示例会话
        demo_conversations = [
            {
                "external_id": f"conv_{secrets.token_hex(8)}",
                "user_id": "beta_user_001",
                "mode": "general",
                "status": "idle",
                "max_iterations": 10,
                "budget_limit_usd": 5.0,
            },
        ]
        
        for conv_data in demo_conversations:
            conversation = Conversation(**conv_data)
            db.add(conversation)
            logger.info(f"✅ 创建示例会话: {conversation.external_id}")
        
        await db.commit()


async def main():
    """主入口"""
    logger.info("=" * 60)
    logger.info("开始执行数据初始化与种子数据创建")
    logger.info("=" * 60)
    
    # 初始化数据库
    if not settings.database_url:
        logger.error("❌ DATABASE_URL 未配置!")
        return
    
    db_manager.initialize(settings.database_url)
    
    try:
        # 确保表已创建
        await db_manager.create_tables()
        logger.info("✅ 数据库表已就绪")
        
        # 创建种子数据
        await create_seed_users()
        await create_seed_projects()
        await create_seed_conversations()
        
        logger.info("=" * 60)
        logger.info("✅ 数据初始化完成!")
        logger.info("=" * 60)
        logger.info("\n可用的测试账户:")
        logger.info("  管理员: admin@lewis-ai-beta.com")
        logger.info("  用户1:  demo1@lewis-ai-beta.com")
        logger.info("  用户2:  demo2@lewis-ai-beta.com")
        logger.info("\n所有账户均无需密码，直接使用邮箱登录即可\n")
        
    except Exception as e:
        logger.error(f"❌ 数据初始化失败: {e}", exc_info=True)
    finally:
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())
