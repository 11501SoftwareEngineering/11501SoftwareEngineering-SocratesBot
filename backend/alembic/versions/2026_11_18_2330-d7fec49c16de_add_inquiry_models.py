"""add inquiry models

Revision ID: d7fec49c16de
Revises: 3991ec74f5a3
Create Date: 2026-11-18 23:30:37.793863+08:00

"""

from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d7fec49c16de"
down_revision: str | Sequence[str] | None = "3991ec74f5a3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _pro(base: str) -> str:
    return (
        f"{base} Pro is the same underlying model as {base}, served with "
        "reasoning.mode set to pro for higher-quality responses on complex tasks. "
        "Pro mode spends far more reasoning tokens per request, so a typical "
        f"request costs several times more than the same request on {base} and "
        "takes much longer to complete. It is intended for hard, high-stakes "
        "problems where the extra accuracy justifies the cost. For everyday "
        f"coding, agentic, and chat workloads, use {base} instead."
    )


_DESCRIPTIONS = {
    "GPT-6.2 Sol": (
        "GPT-6.2 Sol is an upgrade to GPT-6.1 Sol from OpenAI, positioned below "
        "the flagship GPT-6.2 Astra in the GPT-6.2 series. It is an efficient, "
        "versatile model for everyday work, suited for multistep agentic "
        "workflows and clear, natural writing across technical and non-technical "
        "tasks."
    ),
    "GPT-6.1 Sol": (
        "GPT-6.1 Sol is an upgrade to GPT-6 Sol from OpenAI, positioned below the "
        "flagship GPT-6 Astra in the GPT-6 series. It is suited for agentic "
        "coding, computer use, document-heavy professional work, and multi-step "
        "business workflow automation, and approaches Astra-level results on "
        "these tasks at a much lower cost. Compared with GPT-6 Sol, it makes "
        "fewer factual errors and is more reliable at respecting explicit "
        "restrictions and user intent during agentic tasks."
    ),
    "GPT-6.1 Terra": (
        "GPT-6.1 Terra is the mid-tier model in OpenAI's GPT-6.1 series, priced "
        "below GPT-6.1 Sol. It is suited for everyday agentic, coding, and "
        "writing work, is particularly strong at understanding screenshots and "
        "on-screen content, and is efficient enough for high-volume workloads."
    ),
    "GPT-6 Luna": (
        "GPT-6 Luna is the fast, cost-efficient model in OpenAI's GPT-6 series, "
        "positioned below GPT-6 Sol. It is suited for high-volume and "
        "latency-sensitive workloads such as chat, classification, and "
        "lightweight agentic tasks, and at higher reasoning effort it can take on "
        "complex software engineering and computer-use tasks that previously "
        "called for a Sol-tier model. It shares the GPT-6 family's gains in "
        "factual reliability and its clearer, more concise communication style."
    ),
}
_DESCRIPTIONS.update({f"{name} Pro": _pro(name) for name in list(_DESCRIPTIONS)})

# (model_id, name, input, output) in USD per million tokens, from
# GET https://openrouter.ai/api/v1/models on 2026-11-18.
_MODELS = [
    ("openai/gpt-6.2-sol", "GPT-6.2 Sol", "2", "10"),
    ("openai/gpt-6.1-sol", "GPT-6.1 Sol", "2", "10"),
    ("openai/gpt-6.1-terra", "GPT-6.1 Terra", "1", "5"),
    ("openai/gpt-6-luna", "GPT-6 Luna", "0.1", "0.5"),
    ("openai/gpt-6.2-sol-pro", "GPT-6.2 Sol Pro", "2", "10"),
    ("openai/gpt-6.1-sol-pro", "GPT-6.1 Sol Pro", "2", "10"),
    ("openai/gpt-6.1-terra-pro", "GPT-6.1 Terra Pro", "1", "5"),
    ("openai/gpt-6-luna-pro", "GPT-6 Luna Pro", "0.1", "0.5"),
]


def upgrade() -> None:
    """Create ``inquiry_models`` and seed the OpenAI models from OpenRouter."""
    table = op.create_table(
        "inquiry_models",
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("provider_id", sa.Text(), nullable=False),
        sa.Column("input_price_usd", sa.Numeric(), nullable=False),
        sa.Column("output_price_usd", sa.Numeric(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("model_id", name=op.f("pk_inquiry_models")),
        sa.UniqueConstraint("sort_order", name=op.f("uq_inquiry_models_sort_order")),
    )
    op.bulk_insert(
        table,
        [
            {
                "model_id": model_id,
                "name": name,
                "description": _DESCRIPTIONS[name],
                "provider_id": "openai",
                "input_price_usd": Decimal(input_price),
                "output_price_usd": Decimal(output_price),
                "sort_order": order,
            }
            for order, (model_id, name, input_price, output_price) in enumerate(
                _MODELS, start=1
            )
        ],
    )


def downgrade() -> None:
    """Drop ``inquiry_models``."""
    op.drop_table("inquiry_models")
