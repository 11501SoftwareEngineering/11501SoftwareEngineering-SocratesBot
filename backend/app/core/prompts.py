"""Versioned system prompts for the backend's AI workflows.

Prompt instructions live in ``backend/app/core/prompts/<stage>.toml`` so
experimenters can edit wording without touching Python code. Each file declares
``version``, ``max_output_tokens`` and a multiline ``instructions`` string.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tomllib import load
from types import MappingProxyType


class PromptStage(StrEnum):
    INQUIRY_DESIGN = "inquiry_design"
    OPENING = "opening"
    DIALOGUE = "dialogue"
    VALIDITY = "validity"
    STATUS = "status"
    PERSONAL_REPORT = "personal_report"
    CLASS_SUMMARY = "class_summary"
    DIALOGUE_CONTEXT_SUMMARY = "dialogue_context_summary"


@dataclass(frozen=True)
class PromptDefinition:
    stage: PromptStage
    version: str
    instructions: str
    max_output_tokens: int


_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def _load(stage: PromptStage) -> PromptDefinition:
    path = _PROMPTS_DIR / f"{stage.value}.toml"
    with path.open("rb") as fh:
        data = load(fh)
    return PromptDefinition(
        stage=stage,
        version=data["version"],
        instructions=data["instructions"],
        max_output_tokens=data["max_output_tokens"],
    )


PROMPTS: Mapping[PromptStage, PromptDefinition] = MappingProxyType(
    {stage: _load(stage) for stage in PromptStage}
)


def prompt_for(stage: PromptStage) -> PromptDefinition:
    """Return the registered prompt used for one model task."""
    return PROMPTS[stage]
