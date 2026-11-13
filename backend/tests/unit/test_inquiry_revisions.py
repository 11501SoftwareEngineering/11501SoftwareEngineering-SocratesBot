"""Inquiry revisions are stored only when the eight fields change."""

from app.crud.topic import next_revision_version

SAME = {"topic": "Cities", "core_question": "Why?"}
OTHER = {"topic": "Rivers", "core_question": "Why?"}


def test_first_change_is_version_one() -> None:
    assert next_revision_version(None, None, SAME) == 1


def test_unchanged_fields_do_not_allocate_a_version() -> None:
    assert next_revision_version(SAME, 1, dict(SAME)) is None


def test_changed_fields_allocate_the_next_version() -> None:
    assert next_revision_version(SAME, 1, OTHER) == 2
