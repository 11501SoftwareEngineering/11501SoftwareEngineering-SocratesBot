"""store each class summary version

Revision ID: 3991ec74f5a3
Revises: c0f35e45489f
Create Date: 2026-11-15 19:56:21.265125+08:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3991ec74f5a3"
down_revision: str | Sequence[str] | None = "c0f35e45489f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Keep every class-summary version as its own row."""
    op.rename_table("class_summaries", "class_summary_versions")
    op.execute(
        "ALTER TABLE class_summary_versions "
        "RENAME CONSTRAINT pk_class_summaries TO pk_class_summary_versions"
    )
    op.execute(
        "ALTER TABLE class_summary_versions "
        "RENAME CONSTRAINT fk_class_summaries_topic_id_topics "
        "TO fk_class_summary_versions_topic_id_topics"
    )
    op.drop_constraint(
        "uq_class_summaries_topic_id", "class_summary_versions", type_="unique"
    )
    op.create_unique_constraint(
        "uq_class_summary_versions_topic_id_version",
        "class_summary_versions",
        ["topic_id", "version"],
    )


def downgrade() -> None:
    """Restore one current summary row per topic."""
    op.execute(
        """
        DELETE FROM class_summary_versions AS old
        WHERE EXISTS (
            SELECT 1
            FROM class_summary_versions AS newer
            WHERE newer.topic_id = old.topic_id
              AND newer.version > old.version
        )
        """
    )
    op.drop_constraint(
        "uq_class_summary_versions_topic_id_version",
        "class_summary_versions",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_class_summaries_topic_id", "class_summary_versions", ["topic_id"]
    )
    op.execute(
        "ALTER TABLE class_summary_versions "
        "RENAME CONSTRAINT pk_class_summary_versions TO pk_class_summaries"
    )
    op.execute(
        "ALTER TABLE class_summary_versions "
        "RENAME CONSTRAINT fk_class_summary_versions_topic_id_topics "
        "TO fk_class_summaries_topic_id_topics"
    )
    op.rename_table("class_summary_versions", "class_summaries")
