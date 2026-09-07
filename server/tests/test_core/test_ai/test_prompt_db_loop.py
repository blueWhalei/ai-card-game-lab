"""Prompt registry seeds DB defaults and serves them via get_template."""

from __future__ import annotations

import pytest

from app.core.ai.prompts.registry import PromptTemplateRegistry, _split_default_key


def test_split_default_key() -> None:
    assert _split_default_key("doudizhu_playing_v3") == ("doudizhu_playing", "v3")
    assert _split_default_key("doudizhu_bidding_v3_reasoning") == (
        "doudizhu_bidding",
        "v3_reasoning",
    )


def test_split_default_key_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unrecognized"):
        _split_default_key("doudizhu_playing_v1")


@pytest.mark.asyncio
async def test_seed_and_load_from_db(tmp_path) -> None:
    import aiosqlite

    from app.database import init_db

    db_path = str(tmp_path / "test.db")
    await init_db(db_path)
    registry = PromptTemplateRegistry()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        inserted = await registry.seed_defaults(db)
        assert inserted > 0

        # Second seed is idempotent
        assert await registry.seed_defaults(db) == 0

        registry.clear_cache()
        content = await registry.get_template(
            "doudizhu_playing",
            db=db,
            version="v3",
        )
        assert "斗地主" in content or "format_instructions" in content

        # Mutate DB and ensure cache invalidation surfaces new content
        await db.execute(
            "UPDATE prompt_templates SET content = ? WHERE template_key = ? AND version = ?",
            ("CUSTOM_PROMPT_MARKER {rules} {format_instructions}", "doudizhu_playing", "v3"),
        )
        await db.commit()
        registry.invalidate("doudizhu_playing", "v3")
        updated = await registry.get_template("doudizhu_playing", db=db, version="v3")
        assert updated.startswith("CUSTOM_PROMPT_MARKER")
