"""Model IDs offered in the inquiry model catalog.

Migration d7fec49c16de seeds the same IDs into ``inquiry_models``; a unit test
keeps the two lists equal.
"""

INQUIRY_CATALOG_MODELS: tuple[str, ...] = (
    "openai/gpt-6.2-sol",
    "openai/gpt-6.1-sol",
    "openai/gpt-6.1-terra",
    "openai/gpt-6-luna",
    "openai/gpt-6.2-sol-pro",
    "openai/gpt-6.1-sol-pro",
    "openai/gpt-6.1-terra-pro",
    "openai/gpt-6-luna-pro",
)
