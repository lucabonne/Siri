"""Tests for Knowledge Vault tag extraction and management."""

from __future__ import annotations

import pytest

from openjarvis.knowledge_vault.service import KnowledgeVaultService
from openjarvis.knowledge_vault.tags import (
    extract_inline_tags,
    merge_tags,
)

# ---------------------------------------------------------------------------
# Unit tests for tag helper functions
# ---------------------------------------------------------------------------

def test_extract_inline_tags_basic():
    tags = extract_inline_tags("Hello #python and #async world")
    assert tags == ["python", "async"]


def test_extract_inline_tags_deduplicates():
    tags = extract_inline_tags("#foo and #foo again")
    assert tags.count("foo") == 1


def test_extract_inline_tags_lowercases():
    tags = extract_inline_tags("#Python #ASYNC")
    assert "python" in tags
    assert "async" in tags


def test_extract_inline_tags_ignores_mid_word():
    # #hashtag at start or after space only
    tags = extract_inline_tags("email@domain.com is not a #tag")
    assert "tag" in tags
    # email@ pattern doesn't produce a tag
    assert "domain.com" not in tags


def test_extract_inline_tags_empty():
    assert extract_inline_tags("No hash symbols here") == []


def test_extract_inline_tags_hyphenated():
    tags = extract_inline_tags("#my-tag and #another-one")
    assert "my-tag" in tags
    assert "another-one" in tags


def test_merge_tags_combines():
    result = merge_tags(["Explicit", "Tag"], ["inline", "tag"])
    assert "explicit" in result
    assert "tag" in result
    assert "inline" in result


def test_merge_tags_deduplicates():
    result = merge_tags(["python"], ["python"])
    assert result.count("python") == 1


def test_merge_tags_strips_hash():
    result = merge_tags(["#python"], [])
    assert "python" in result
    assert "#python" not in result


def test_merge_tags_empty_inputs():
    assert merge_tags([], []) == []


# ---------------------------------------------------------------------------
# Integration tests via service
# ---------------------------------------------------------------------------

@pytest.fixture()
def vault():
    svc = KnowledgeVaultService(db_path=":memory:")
    yield svc
    svc.close()


def test_tags_appear_in_all_tags(vault):
    vault.create_note("A", tags=["alpha", "beta"])
    vault.create_note("B", tags=["alpha", "gamma"])
    tags = vault.all_tags()
    tag_map = {t["name"]: t["count"] for t in tags}
    assert tag_map.get("alpha") == 2
    assert tag_map.get("beta") == 1
    assert tag_map.get("gamma") == 1


def test_all_tags_sorted_by_count(vault):
    vault.create_note("X", tags=["rare"])
    vault.create_note("Y", tags=["common"])
    vault.create_note("Z", tags=["common"])
    tags = vault.all_tags()
    assert tags[0]["name"] == "common"


def test_inline_tags_from_content_appear_in_all_tags(vault):
    vault.create_note("Inline", content="This has #inline tag content")
    tags = vault.all_tags()
    names = [t["name"] for t in tags]
    assert "inline" in names


def test_notes_by_tag(vault):
    vault.create_note("Note 1", tags=["mytag"])
    vault.create_note("Note 2", tags=["mytag"])
    vault.create_note("Note 3", tags=["other"])
    results = vault.notes_by_tag("mytag")
    assert len(results) == 2
    assert all("mytag" in n["tags"] for n in results)


def test_notes_by_tag_empty(vault):
    vault.create_note("Untagged note")
    assert vault.notes_by_tag("nonexistent") == []


def test_tag_filtering_in_list(vault):
    vault.create_note("Has tag", tags=["filter-me"])
    vault.create_note("No tag", tags=["other"])
    results = vault.list_notes(tags=["filter-me"])
    assert len(results) == 1
    assert "filter-me" in results[0]["tags"]
