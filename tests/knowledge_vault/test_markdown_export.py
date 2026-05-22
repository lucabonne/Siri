"""Tests for Knowledge Vault markdown export."""

from __future__ import annotations

import pytest

from openjarvis.knowledge_vault.markdown_export import (
    note_to_markdown,
    safe_filename,
)
from openjarvis.knowledge_vault.service import KnowledgeVaultService


@pytest.fixture()
def vault():
    svc = KnowledgeVaultService(db_path=":memory:")
    yield svc
    svc.close()


def test_note_to_markdown_frontmatter_present(vault):
    note = vault.create_note(
        "My Research Note",
        note_type="research",
        tags=["python", "testing"],
        content="This is the body.",
    )
    md = note_to_markdown(note)
    assert md.startswith("---\n")
    assert "title:" in md
    assert "tags:" in md
    assert "type: research" in md


def test_note_to_markdown_body_preserved(vault):
    body = "Hello world\n\nThis is [[wiki-linked]] text."
    note = vault.create_note("Body Test", content=body)
    md = note_to_markdown(note)
    assert "Hello world" in md
    assert "[[wiki-linked]]" in md


def test_note_to_markdown_tags_in_frontmatter(vault):
    note = vault.create_note("Tagged", tags=["alpha", "beta"])
    md = note_to_markdown(note)
    # Should produce tags: [alpha, beta]
    assert "tags: [alpha, beta]" in md


def test_note_to_markdown_pinned_flag(vault):
    note = vault.create_note("Pinnable")
    vault.pin_note(note["id"], True)
    note = vault.get_note(note["id"])
    md = note_to_markdown(note)
    assert "pinned: true" in md


def test_note_to_markdown_source_links(vault):
    note = vault.create_note(
        "Source Link Test",
        source_links=[{"title": "Example", "url": "https://example.com"}],
    )
    md = note_to_markdown(note)
    assert "sources:" in md
    assert "https://example.com" in md


def test_note_to_markdown_daily_note_has_date(vault):
    note = vault.get_daily_note("2025-06-15")
    md = note_to_markdown(note)
    assert "date: 2025-06-15" in md
    assert "type: daily" in md


def test_note_to_markdown_timestamps_present(vault):
    note = vault.create_note("Timestamped")
    md = note_to_markdown(note)
    assert "created:" in md
    assert "updated:" in md


def test_safe_filename_basic():
    assert safe_filename("My Note", "id-123") == "My Note.md"


def test_safe_filename_strips_illegal_chars():
    fname = safe_filename("Note: With / Slashes?", "x")
    assert "/" not in fname
    assert ":" not in fname
    assert "?" not in fname


def test_safe_filename_fallback_on_empty_title():
    fname = safe_filename("", "abc12345-xxxx")
    assert fname.endswith(".md")
    assert len(fname) > 3


def test_safe_filename_truncates_long_title():
    long_title = "A" * 200
    fname = safe_filename(long_title, "x")
    # base name without .md should be <=80
    assert len(fname.replace(".md", "")) <= 80


def test_export_vault_note_markdown_roundtrip(vault):
    """Service.export_note_markdown should return valid frontmatter."""
    note = vault.create_note("Round Trip", content="Hello [[World]].", tags=["test"])
    md = vault.export_note_markdown(note["id"])
    assert "title: 'Round Trip'" in md or "title: Round Trip" in md
    assert "Hello [[World]]." in md


def test_export_vault_writes_files(vault, tmp_path):
    vault.create_note("Export Note 1", content="Content 1")
    vault.create_note("Export Note 2", content="Content 2")
    result = vault.export_vault(output_dir=tmp_path)
    assert result["exported_count"] == 2
    assert len(result["files"]) == 2
    assert result["local_only"] is True
    for fpath in result["files"]:
        assert (
            "Content" in open(fpath, encoding="utf-8").read()
            or "title:" in open(fpath, encoding="utf-8").read()
        )


def test_export_vault_daily_note_named_by_date(vault, tmp_path):
    vault.get_daily_note("2025-01-20")
    result = vault.export_vault(output_dir=tmp_path)
    filenames = [p.split("/")[-1] for p in result["files"]]
    assert "2025-01-20.md" in filenames
