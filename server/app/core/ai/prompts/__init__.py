"""Prompt template management module.

This module provides centralized prompt template management with:
- Version control
- A/B testing support
- SQLite persistence
"""

from app.core.ai.prompts.registry import PromptTemplateRegistry, get_registry

__all__ = ["PromptTemplateRegistry", "get_registry"]
