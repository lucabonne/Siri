"""Tests for Knowledge Vault note lifecycle (create, read, update, delete, pin)."""

from __future__ import annotations

import pytest

from openjarvis.knowledge_vault.service import KnowledgeVaultService


@pytest.fixture()
def vault():
    """In-memory vault for testing — no disk I/O."""
    svc = KnowledgeVaultService(db_path=":memory:")
    yield svc
    svc.close()


def test_create_note_basic(vault):
    note = vault.create_note("My First Note", content="Hello world")
    assert note["id"]
    assert note["title"] == "My First Note"
    assert note["content"] == "Hello world"
    assert note["note_type"] == "note"
    assert note["pinned"] is False


def test_create_note_validates_empty_title(vault):
    with pytest.raises(ValueError, match="title cannot be empty"):
        vault.create_note("   ")


def test_create_note_with_tags(vault):
    note = vault.create_note("Tagged Note", tags=["python", "research"])
    assert "python" in note["tags"]
    assert "research" in note["tags"]


def test_create_note_inline_tags_extracted(vault):
    """Inline #hashtags in content should be merged into the tags array."""
    note = vault.create_note("Inline Tags", content="Check this #python #async thing")
    assert "python" in note["tags"]
    assert "async" in note["tags"]


def test_create_note_types(vault):
    for note_type in ("note", "daily", "project", "research"):
        note = vault.create_note(f"{note_type} note", note_type=note_type)
        assert note["note_type"] == note_type


def test_get_note_returns_with_backlinks(vault):
    note = vault.create_note("Note A")
    fetched = vault.get_note(note["id"])
    assert fetched["id"] == note["id"]
    assert "backlinks" in fetched


def test_get_note_not_found_raises(vault):
    with pytest.raises(KeyError):
        vault.get_note("nonexistent-id")


def test_update_note_title(vault):
    note = vault.create_note("Original Title")
    updated = vault.update_note(note["id"], title="New Title")
    assert updated["title"] == "New Title"
    # Content unchanged
    assert updated["content"] == note["content"]


def test_update_note_content_tags(vault):
    note = vault.create_note("My Note")
    updated = vault.update_note(note["id"], content="Updated #newtag content")
    assert "newtag" in updated["tags"]
    assert "Updated" in updated["content"]


def test_delete_note(vault):
    note = vault.create_note("To Delete")
    deleted = vault.delete_note(note["id"])
    assert deleted is True
    with pytest.raises(KeyError):
        vault.get_note(note["id"])


def test_delete_nonexistent_returns_false(vault):
    assert vault.delete_note("no-such-id") is False


def test_pin_note(vault):
    note = vault.create_note("Pinnable Note")
    assert note["pinned"] is False
    pinned = vault.pin_note(note["id"], True)
    assert pinned["pinned"] is True
    unpinned = vault.pin_note(note["id"], False)
    assert unpinned["pinned"] is False


def test_pin_note_not_found(vault):
    with pytest.raises(KeyError):
        vault.pin_note("ghost-id", True)


def test_list_notes_empty(vault):
    assert vault.list_notes() == []


def test_list_notes_returns_all(vault):
    vault.create_note("A")
    vault.create_note("B")
    vault.create_note("C")
    notes = vault.list_notes()
    assert len(notes) == 3


def test_list_notes_filter_by_type(vault):
    vault.create_note("n1", note_type="note")
    vault.create_note("p1", note_type="project")
    vault.create_note("p2", note_type="project")
    projects = vault.list_notes(note_type="project")
    assert len(projects) == 2
    assert all(n["note_type"] == "project" for n in projects)


def test_list_notes_filter_pinned(vault):
    n1 = vault.create_note("Pinned")
    vault.pin_note(n1["id"], True)
    vault.create_note("Not pinned")
    pinned = vault.list_notes(pinned=True)
    assert len(pinned) == 1
    assert pinned[0]["pinned"] is True


def test_count(vault):
    assert vault.count() == 0
    vault.create_note("X")
    vault.create_note("Y")
    assert vault.count() == 2


def test_source_links_stored(vault):
    note = vault.create_note(
        "With Source",
        source_links=[{"title": "Docs", "url": "https://example.com"}],
    )
    fetched = vault.get_note(note["id"])
    assert len(fetched["source_links"]) == 1
    assert fetched["source_links"][0]["url"] == "https://example.com"


def test_project_id_stored(vault):
    note = vault.create_note("Proj Note", project_id="my-project")
    assert note["project_id"] == "my-project"
    results = vault.list_notes(project_id="my-project")
    assert len(results) == 1
