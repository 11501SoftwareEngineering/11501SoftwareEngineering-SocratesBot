"""Shared seed error type (avoids circular imports between runner and packs)."""


class SeedError(Exception):
    """Seed aborted due to environment, pack selection, or catalog conflict."""
