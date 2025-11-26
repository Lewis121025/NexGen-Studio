"""
数据库字段规范化迁移脚本
将 config_json 中的核心字段提升为一级列
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'normalize_creative_fields'
down_revision = 'init_schema'  # Depends on initial schema
branch_labels = None
depends_on = None


def upgrade():
    """
    这个迁移已被合并到 init_schema 中。
    由于 init_schema 已经创建了这些列，这里无需执行任何操作。
    保留此文件以维护迁移链完整性。
    """
    # All columns (title, brief, duration_seconds, etc.) are already created in init_schema.
    # This migration is kept for compatibility with existing migration chain.
    pass


def downgrade():
    """
    No-op downgrade since this migration is now a placeholder.
    """
    pass
