"""Unit tests for PromptTemplateRegistry."""

from __future__ import annotations

import pytest

from app.core.ai.prompts.registry import (
    DEFAULT_TEMPLATE_VERSION,
    REASONING_TEMPLATE_VERSION,
    PromptTemplate,
    PromptTemplateRegistry,
)


class TestPromptTemplate:
    """Test cases for PromptTemplate dataclass."""

    def test_create_template(self) -> None:
        """Should create template with auto-generated fields."""
        template = PromptTemplate.create(
            template_key="doudizhu_playing",
            version="v3",
            content="Test content",
        )

        assert template.id  # Should have UUID
        assert template.template_key == "doudizhu_playing"
        assert template.version == "v3"
        assert template.content == "Test content"
        assert template.is_active is True
        assert template.created_at  # Should have timestamp
        assert template.updated_at

    def test_to_dict(self) -> None:
        """Should convert template to dictionary."""
        template = PromptTemplate(
            id="test-id",
            template_key="test_key",
            version="v3",
            content="Test content",
            is_active=True,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        result = template.to_dict()

        assert result["id"] == "test-id"
        assert result["template_key"] == "test_key"
        assert result["version"] == "v3"
        assert result["content"] == "Test content"
        assert result["is_active"] is True


class TestPromptTemplateRegistry:
    """Test cases for PromptTemplateRegistry."""

    @pytest.fixture
    def registry(self) -> PromptTemplateRegistry:
        return PromptTemplateRegistry()

    @pytest.mark.asyncio
    async def test_get_default_template(self, registry: PromptTemplateRegistry) -> None:
        """Should get default template when no DB provided."""
        content = await registry.get_template("doudizhu_playing")

        assert content
        assert "{rules}" in content
        assert "{format_instructions}" in content

    @pytest.mark.asyncio
    async def test_get_bidding_template(self, registry: PromptTemplateRegistry) -> None:
        """Should get bidding template."""
        content = await registry.get_template("doudizhu_bidding")

        assert content
        assert "叫地主" in content

    @pytest.mark.asyncio
    async def test_get_specific_version(self, registry: PromptTemplateRegistry) -> None:
        """Should get specific version when requested."""
        content_v3 = await registry.get_template("doudizhu_playing", version="v3")
        content_reasoning = await registry.get_template("doudizhu_playing", version="v3_reasoning")

        assert content_v3 != content_reasoning
        assert "思考请控制" in content_reasoning

    @pytest.mark.asyncio
    async def test_missing_template_raises(self, registry: PromptTemplateRegistry) -> None:
        """Should raise ValueError for missing template."""
        with pytest.raises(ValueError, match="No template"):
            await registry.get_template("nonexistent_template")

    @pytest.mark.asyncio
    async def test_missing_old_version_raises(self, registry: PromptTemplateRegistry) -> None:
        """v1/v2 are not built-in defaults under the action-id protocol."""
        with pytest.raises(ValueError, match="No template"):
            await registry.get_template("doudizhu_playing", version="v1")

    def test_default_version_is_v3(self, registry: PromptTemplateRegistry) -> None:
        assert registry._default_version == DEFAULT_TEMPLATE_VERSION
        assert DEFAULT_TEMPLATE_VERSION == "v3"
        assert REASONING_TEMPLATE_VERSION == "v3_reasoning"

    def test_clear_cache(self, registry: PromptTemplateRegistry) -> None:
        """Should clear cache."""
        registry._cache["test"] = PromptTemplate(
            id="", template_key="test", version="v3", content="test"
        )

        registry.clear_cache()

        assert not registry._cache


class TestPromptTemplateRegistryDefaults:
    """Test default template content."""

    @pytest.fixture
    def registry(self) -> PromptTemplateRegistry:
        return PromptTemplateRegistry()

    @pytest.mark.asyncio
    async def test_playing_v3_has_required_sections(self, registry: PromptTemplateRegistry) -> None:
        """v3 playing template should have required sections."""
        content = await registry.get_template("doudizhu_playing", version="v3")

        assert "核心规则" in content
        assert "决策要点" in content
        assert "format_instructions" in content

    @pytest.mark.asyncio
    async def test_playing_v3_reasoning_has_budget(self, registry: PromptTemplateRegistry) -> None:
        """v3_reasoning playing template should spell out the thinking budget."""
        content = await registry.get_template("doudizhu_playing", version="v3_reasoning")

        assert "思考请控制" in content
        assert "format_instructions" in content

    @pytest.mark.asyncio
    async def test_bidding_template_has_evaluation(self, registry: PromptTemplateRegistry) -> None:
        """Bidding template should have hand evaluation guidance."""
        content = await registry.get_template("doudizhu_bidding")

        assert "炸弹" in content
        assert "王炸" in content
        assert "叫分" in content
