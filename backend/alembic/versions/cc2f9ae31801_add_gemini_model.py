"""Offer one Gemini model without deleting historical activity references."""

from alembic import op

revision = "cc2f9ae31801"
down_revision = "b8e39a1547c2"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        INSERT INTO inquiry_models
        (model_id, name, description, provider_id, input_price_usd, output_price_usd, sort_order)
        SELECT 'gemini-3.1-flash-lite', 'Gemini 3.1 Flash-Lite',
        'Google Gemini API. Paid text rates shown; free-tier access depends on project quota.',
        'google', 0.25, 1.50, COALESCE(MAX(sort_order), 0)+1 FROM inquiry_models
        ON CONFLICT (model_id) DO NOTHING
    """)


def downgrade():
    op.execute("""
        DO $$ BEGIN
        IF EXISTS (SELECT 1 FROM teacher_ai_settings WHERE default_model_id='gemini-3.1-flash-lite')
        OR EXISTS (SELECT 1 FROM topics WHERE model_id='gemini-3.1-flash-lite') THEN
            RAISE EXCEPTION 'Remove Gemini model references before downgrade';
        END IF;
        END $$
    """)
    op.execute("DELETE FROM inquiry_models WHERE model_id='gemini-3.1-flash-lite'")
