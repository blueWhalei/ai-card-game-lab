"""Unit tests for PromptTemplateRegistry."""

from __future__ import annotations

import pytest

from app.core.ai.prompts.registry import PromptTemplate, PromptTemplateRegistry


class TestPromptTemplate:
    """Test cases for PromptTemplate dataclass."""

    def test_create_template(self) -> None:
        """Should create template with auto-generated fields."""
        template = PromptTemplate.create(
            template_key="doudizhu_playing",
            version="v1",
            content="Test content",
        )

        assert template.id  # Should have UUID
        assert template.template_key == "doudizhu_playing"
        assert template.version == "v1"
        assert template.content == "Test content"
        assert template.is_active is True
        assert template.created_at  # Should have timestamp
        assert template.updated_at

    def test_to_dict(self) -> None:
        """Should convert template to dictionary."""
        template = PromptTemplate(
            id="test-id",
            template_key="test_key",
            version="v1",
            content="Test content",
            is_active=True,
            created_at="2024-01-01T00:00:00Z",
            updated_at="2024-01-01T00:00:00Z",
        )

        result = template.to_dict()

        assert result["id"] == "test-id"
        assert result["template_key"] == "test_key"
        assert result["version"] == "v1"
        assert result["content"] == "Test content"
        assert result["is_active"] is True


class TestPromptTemplateRegistry:
    """Test cases for PromptTemplateRegistry."""

    @pytest.fixture
    def registry(self) -> PromptTemplateRegistry:
        return PromptTemplateRegistry()

    @pytest.fixture
    def ab_registry(self) -> PromptTemplateRegistry:
        return PromptTemplateRegistry(
            default_version="v1",
            ab_test_enabled=True,
            ab_test_ratio=0.5,
        )

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
        content_v1 = await registry.get_template("doudizhu_playing", version="v1")
        content_v2 = await registry.get_template("doudizhu_playing", version="v2")

        assert content_v1 != content_v2
        assert "一次性出完" in content_v2  # v2 has extra strategy

    @pytest.mark.asyncio
    async def test_missing_template_raises(self, registry: PromptTemplateRegistry) -> None:
        """Should raise ValueError for missing template."""
        with pytest.raises(ValueError, match="No template found"):
            await registry.get_template("nonexistent_template")

    def test_select_version_explicit(self, registry: PromptTemplateRegistry) -> None:
        """Should use explicitly requested version."""
        version = registry._select_version(
            template_key="doudizhu_playing",
            requested_version="v2",
            session_id=None,
        )
        assert version == "v2"

    def test_select_version_default(self, registry: PromptTemplateRegistry) -> None:
        """Should use default version when nothing specified."""
        version = registry._select_version(
            template_key="doudizhu_playing",
            requested_version=None,
            session_id=None,
        )
        assert version == "v1"

    def test_select_version_ab_test_consistent(self, ab_registry: PromptTemplateRegistry) -> None:
        """Should consistently assign same version for same session."""
        # Same session should get same version
        v1 = ab_registry._select_version(
            template_key="doudizhu_playing",
            requested_version=None,
            session_id="session-123",
        )
        v2 = ab_registry._select_version(
            template_key="doudizhu_playing",
            requested_version=None,
            session_id="session-123",
        )

        assert v1 == v2

    def test_select_version_ab_test_different_sessions(self, ab_registry: PromptTemplateRegistry) -> None:
        """Should potentially assign different versions for different sessions."""
        versions = set()
        for i in range(100):
            version = ab_registry._select_version(
                template_key="doudizhu_playing",
                requested_version=None,
                session_id=f"session-{i}",
            )
            versions.add(version)

        # With 100 sessions and 50% ratio, we should see both versions
        assert len(versions) == 2

    def test_ab_test_disabled(self, registry: PromptTemplateRegistry) -> None:
        """Should always return default when A/B testing disabled."""
        for i in range(10):
            version = registry._select_version(
                template_key="doudizhu_playing",
                requested_version=None,
                session_id=f"session-{i}",
            )
            assert version == "v1"

    def test_clear_cache(self, registry: PromptTemplateRegistry) -> None:
        """Should clear cache and A/B assignments."""
        registry._cache["test"] = PromptTemplate(
            id="", template_key="test", version="v1", content="test"
        )
        registry._ab_assignments["session-1"] = "v1"

        registry.clear_cache()

        assert not registry._cache
        assert not registry._ab_assignments

    def test_get_ab_stats(self, ab_registry: PromptTemplateRegistry) -> None:
        """Should return A/B test statistics."""
        # Assign some sessions
        for i in range(10):
            ab_registry._select_version(
                template_key="doudizhu_playing",
                requested_version=None,
                session_id=f"session-{i}",
            )

        stats = ab_registry.get_ab_stats()

        assert stats["enabled"] is True
        assert stats["ratio"] == 0.5
        assert stats["total_assignments"] == 10
        assert stats["v1_count"] + stats["v2_count"] == 10


class TestPromptTemplateRegistryDefaults:
    """Test default template content."""

    @pytest.fixture
    def registry(self) -> PromptTemplateRegistry:
        return PromptTemplateRegistry()

    @pytest.mark.asyncio
    async def test_playing_v1_has_required_sections(self, registry: PromptTemplateRegistry) -> None:
        """v1 playing template should have required sections."""
        content = await registry.get_template("doudizhu_playing", version="v1")

        assert "游戏规则" in content
        assert "出牌策略" in content
        assert "format_instructions" in content

    @pytest.mark.asyncio
    async def test_playing_v2_has_extra_strategy(self, registry: PromptTemplateRegistry) -> None:
        """v2 playing template should have extra strategy hints."""
        content = await registry.get_template("doudizhu_playing", version="v2")

        assert "一次性出完" in content or "压制对手" in content

    @pytest.mark.asyncio
    async def test_bidding_template_has_evaluation(self, registry: PromptTemplateRegistry) -> None:
        """Bidding template should have hand evaluation guidance."""
        content = await registry.get_template("doudizhu_bidding")

        assert "炸弹" in content
        assert "王炸" in content
        assert "叫分建议" in content
