"""Tests for daily note creation and idempotency."""

from __future__ import annotations

from datetime import date

import pytest

from openjarvis.knowledge_vault.service import KnowledgeVaultService


@pytest.fixture()
def vault():
    svc = KnowledgeVaultService(db_path=":memory:")
    yield svc
    svc.close()


def test_get_daily_note_today_creates_note(vault):
    note = vault.get_daily_note()
    assert note["note_type"] == "daily"
    assert note["date"] == date.today().isoformat()


def test_get_daily_note_is_idempotent(vault):
    """Calling get_daily_note multiple times for the same date returns the same note."""
    today = date.today().isoformat()
    n1 = vault.get_daily_note(today)
    n2 = vault.get_daily_note(today)
    assert n1["id"] == n2["id"]


def test_get_daily_note_creates_for_specific_date(vault):
    note = vault.get_daily_note("2025-03-14")
    assert note["date"] == "2025-03-14"
    assert note["note_type"] == "daily"


def test_get_daily_note_title_is_human_readable(vault):
    note = vault.get_daily_note("2025-01-06")
    # Should contain the day of week or month name
    assert any(
        word in note["title"]
        for word in ("Monday", "January", "2025", "6")
    )


def test_daily_note_content_has_heading(vault):
    note = vault.get_daily_note("2025-07-04")
    assert note["content"].startswith("#")


def test_list_daily_notes(vault):
    vault.get_daily_note("2025-01-01")
    vault.get_daily_note("2025-01-02")
    vault.get_daily_note("2025-01-03")
    daily = vault.list_daily_notes()
    assert len(daily) == 3
    # Should be ordered newest first
    dates = [n["date"] for n in daily]
    assert dates == sorted(dates, reverse=True)


def test_daily_note_distinct_from_regular_notes(vault):
    vault.create_note("Regular Note", note_type="note")
    vault.get_daily_note("2025-06-01")
    regulars = vault.list_notes(note_type="note")
    dailies = vault.list_notes(note_type="daily")
    assert len(regulars) == 1
    assert len(dailies) == 1


def test_daily_note_can_be_updated(vault):
    note = vault.get_daily_note("2025-08-15")
    updated = vault.update_note(
        note["id"], content="# Aug 15\n\nUpdated content #diary"
    )
    assert "Updated content" in updated["content"]
    assert "diary" in updated["tags"]


def test_daily_note_only_one_per_date(vault):
    vault.get_daily_note("2025-09-10")
    vault.get_daily_note("2025-09-10")  # idempotent call
    all_notes = vault.list_notes(note_type="daily")
    sep_10_notes = [n for n in all_notes if n["date"] == "2025-09-10"]
    assert len(sep_10_notes) == 1


def test_daily_note_shows_in_search(vault):
    note = vault.get_daily_note("2025-10-01")
    # Update with searchable content
    vault.update_note(
        note["id"],
        content="# Oct 1\n\nMeeting with Alice about the quarterly review.",
    )
    results = vault.search_notes("Alice quarterly")
    assert any(n["id"] == note["id"] for n in results)
