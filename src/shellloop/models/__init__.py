"""Model implementations."""

from shellloop.models.openai_compatible import OpenAICompatibleModel
from shellloop.models.scripted import ScriptedModel, demo_model

__all__ = ["OpenAICompatibleModel", "ScriptedModel", "demo_model"]
