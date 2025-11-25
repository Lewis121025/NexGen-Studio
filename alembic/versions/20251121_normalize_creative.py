"""Normalize creative_projects, split config_json fields.

Revision ID: 20251121_normalize_creative
Revises: 
Create Date: 2025-11-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


# revision identifiers, used by Alembic.
revision = "20251121_normalize_creative"
down_revision = "normalize_creative_fields"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    cols = {c["name"] for c in insp.get_columns("creative_projects")}

    with op.batch_alter_table("creative_projects") as batch:
        if "summary" not in cols:
            batch.add_column(sa.Column("summary", sa.Text(), nullable=True))
        if "script_text" not in cols:
            batch.add_column(sa.Column("script_text", sa.Text(), nullable=True))
        if "storyboard_json" not in cols:
            batch.add_column(sa.Column("storyboard_json", sa.JSON(), nullable=True))
        if "shots_json" not in cols:
            batch.add_column(sa.Column("shots_json", sa.JSON(), nullable=True))
        if "render_manifest_json" not in cols:
            batch.add_column(sa.Column("render_manifest_json", sa.JSON(), nullable=True))
        if "preview_json" not in cols:
            batch.add_column(sa.Column("preview_json", sa.JSON(), nullable=True))
        if "validation_json" not in cols:
            batch.add_column(sa.Column("validation_json", sa.JSON(), nullable=True))
        if "distribution_json" not in cols:
            batch.add_column(sa.Column("distribution_json", sa.JSON(), nullable=True))
        if "error_message" not in cols:
            batch.add_column(sa.Column("error_message", sa.Text(), nullable=True))

    # 迁移已有的 config_json 数据
    if "config_json" in cols:
        rows = conn.execute(text("SELECT id, config_json FROM creative_projects")).fetchall()
        for row in rows:
            data = row.config_json or {}
            update_sql = text(
                """
                UPDATE creative_projects
                SET summary = COALESCE(:summary, summary),
                    script_text = COALESCE(:script_text, script_text),
                    storyboard_json = COALESCE(:storyboard_json, storyboard_json),
                    shots_json = COALESCE(:shots_json, shots_json),
                    render_manifest_json = COALESCE(:render_manifest_json, render_manifest_json),
                    preview_json = COALESCE(:preview_json, preview_json),
                    validation_json = COALESCE(:validation_json, validation_json),
                    distribution_json = COALESCE(:distribution_json, distribution_json),
                    error_message = COALESCE(:error_message, error_message)
                WHERE id = :row_id
                """
            )
            conn.execute(
                update_sql,
                {
                    "row_id": row.id,
                    "summary": data.get("summary"),
                    "script_text": data.get("script"),
                    "storyboard_json": data.get("storyboard"),
                    "shots_json": data.get("shots"),
                    "render_manifest_json": data.get("render_manifest"),
                    "preview_json": data.get("preview_record"),
                    "validation_json": data.get("validation_record"),
                    "distribution_json": data.get("distribution_log"),
                    "error_message": data.get("error_message"),
                },
            )

        with op.batch_alter_table("creative_projects") as batch:
            batch.drop_column("config_json")


def downgrade():
    with op.batch_alter_table("creative_projects") as batch:
        batch.add_column(sa.Column("config_json", sa.JSON(), nullable=True))
        batch.drop_column("distribution_json")
        batch.drop_column("validation_json")
        batch.drop_column("preview_json")
        batch.drop_column("render_manifest_json")
        batch.drop_column("shots_json")
        batch.drop_column("storyboard_json")
        batch.drop_column("script_text")
        batch.drop_column("summary")
        batch.drop_column("error_message")
