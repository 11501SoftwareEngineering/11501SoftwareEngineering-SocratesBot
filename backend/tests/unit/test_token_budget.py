import importlib.util
from pathlib import Path

from app.core.model_catalog import INQUIRY_CATALOG_MODELS
from app.services.token_budget import estimate_request_tokens

_SEED = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/2026_11_18_2330-d7fec49c16de_add_inquiry_models.py"
)


def test_every_catalog_model_has_a_tokenizer() -> None:
    spec = importlib.util.spec_from_file_location("inquiry_models_seed", _SEED)
    assert spec is not None and spec.loader is not None
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)

    assert [row[0] for row in seed._MODELS] == list(INQUIRY_CATALOG_MODELS)
    for model_id in INQUIRY_CATALOG_MODELS:
        tokens = estimate_request_tokens(
            model_id=model_id, instructions="i", material="m", schema={}
        )
        assert tokens > 0


def test_product_defaults_target_sol_with_reviewed_encoding():
    from app.core.config import Settings
    from app.core.model_catalog import INQUIRY_CATALOG_MODELS
    from app.services.token_budget import MODEL_ENCODINGS

    for name in ("OPENAI_MODEL", "OPENAI_VALIDITY_MODEL"):
        model = Settings.model_fields[name].default
        assert model == "openai/gpt-6.1-sol"
        assert model in INQUIRY_CATALOG_MODELS
        assert MODEL_ENCODINGS[model] == "o200k_base"
