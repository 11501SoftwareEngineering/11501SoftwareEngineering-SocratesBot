"""Merge the versioned-prompts head with the PR 238 head (teacher AI settings)."""

from collections.abc import Sequence

revision: str = "b7d2e0f4a913"
down_revision: str | Sequence[str] | None = ("7ce5146e1d3a", "661d37e7b81e")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Merge revision: no schema change."""


def downgrade() -> None:
    """Merge revision: no schema change."""
