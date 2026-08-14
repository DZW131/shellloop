"""Model implementations."""

from shellloop.models.ollama_cloud import OllamaCloudModel
from shellloop.models.openai_compatible import OpenAICompatibleModel
from shellloop.models.scripted import ScriptedModel, demo_model

__all__ = ["OllamaCloudModel", "OpenAICompatibleModel", "ScriptedModel", "demo_model"]
