"""Tests for Knowledge Vault backlink extraction and storage."""

from __future__ import annotations

import pytest

from openjarvis.knowledge_vault.backlinks import (
    extract_wiki_links,
    resolve_links,
)
from openjarvis.knowledge_vault.service import KnowledgeVaultService

# ---------------------------------------------------------------------------
# Unit tests for pure functions
# ---------------------------------------------------------------------------

def test_extract_wiki_links_basic():
    content = "See [[Alpha]] and [[Beta]] for details."
    links = extract_wiki_links(content)
    assert links == ["Alpha", "Beta"]


def test_extract_wiki_links_alias():
    content = "Click [[Target Note|alias text]] here."
    links = extract_wiki_links(content)
    assert links == ["Target Note"]


def test_extract_wiki_links_empty():
    assert extract_wiki_links("No links here.") == []


def test_extract_wiki_links_nested_brackets():
    content = "Only [[valid]] and not [[bad|extra|pipe]]."
    links = extract_wiki_links(content)
    # bad|extra|pipe - only first segment returned
    assert "valid" in links


def test_resolve_links_basic():
    index = {"alpha": "id-1", "beta": "id-2"}
    resolved = resolve_links(["Alpha", "Beta", "Gamma"], index)
    assert resolved == [("Alpha", "id-1"), ("Beta", "id-2")]


def test_resolve_links_case_insensitive():
    index = {"my note": "id-x"}
    resolved = resolve_links(["My Note", "MY NOTE"], index)
    assert len(resolved) == 2
    assert all(r[1] == "id-x" for r in resolved)


def test_resolve_links_missing_note():
    index = {"exists": "id-1"}
    resolved = resolve_links(["Missing"], index)
    assert resolved == []


# ---------------------------------------------------------------------------
# Integration tests via KnowledgeVaultService
# ---------------------------------------------------------------------------

@pytest.fixture()
def vault():
    svc = KnowledgeVaultService(db_path=":memory:")
    yield svc
    svc.close()


def test_backlinks_created_on_create_note(vault):
    target = vault.create_note("Target Note")
    _source = vault.create_note(
        "Source Note",
        content="This references [[Target Note]] in the text.",
    )
    backlinks = vault.get_backlinks(target["id"])
    assert len(backlinks) == 1
    assert backlinks[0]["source_note_title"] == "Source Note"
    assert "Target Note" in backlinks[0]["context_snippet"]


def test_backlinks_updated_on_note_update(vault):
    target = vault.create_note("The Target")
    source = vault.create_note("Source", content="No link yet")
    # Initially no backlinks
    assert vault.get_backlinks(target["id"]) == []
    # Add a link
    vault.update_note(source["id"], content="Now links to [[The Target]].")
    backlinks = vault.get_backlinks(target["id"])
    assert len(backlinks) == 1


def test_backlinks_removed_when_link_deleted(vault):
    target = vault.create_note("Linked Target")
    source = vault.create_note("Linker", content="Points to [[Linked Target]].")
    assert len(vault.get_backlinks(target["id"])) == 1
    # Remove the link from content
    vault.update_note(source["id"], content="No more links.")
    assert vault.get_backlinks(target["id"]) == []


def test_self_links_ignored(vault):
    """A note should not create a backlink to itself."""
    note = vault.create_note("Self Reference", content="I link to [[Self Reference]].")
    backlinks = vault.get_backlinks(note["id"])
    assert backlinks == []


def test_multiple_sources_linking_to_same_target(vault):
    target = vault.create_note("Popular Target")
    vault.create_note("Ref A", content="See [[Popular Target]] for more.")
    vault.create_note("Ref B", content="Also [[Popular Target]] is great.")
    backlinks = vault.get_backlinks(target["id"])
    assert len(backlinks) == 2
    source_titles = {bl["source_note_title"] for bl in backlinks}
    assert "Ref A" in source_titles
    assert "Ref B" in source_titles


def test_backlinks_deleted_when_source_note_deleted(vault):
    target = vault.create_note("Keep Target")
    source = vault.create_note("Delete Me", content="Link to [[Keep Target]].")
    assert len(vault.get_backlinks(target["id"])) == 1
    vault.delete_note(source["id"])
    # Backlinks should be cascaded away
    assert vault.get_backlinks(target["id"]) == []


def test_note_with_backlinks_in_get_note(vault):
    target = vault.create_note("Ref Target")
    vault.create_note("Linker", content="[[Ref Target]] is here.")
    full = vault.get_note(target["id"])
    assert len(full["backlinks"]) == 1
    assert full["backlinks"][0]["source_note_title"] == "Linker"
