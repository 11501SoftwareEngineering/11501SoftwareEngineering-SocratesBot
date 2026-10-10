import pytest

from scripts.check_migrations_align_with_main import (
    _validate_git_ref,
    _validate_versions_path,
    ancestors,
    build_graph,
    find_heads,
    parse_revision_meta,
)


def test_parse_revision_meta_linear() -> None:
    content = """
revision: str = "child"
down_revision: str | None = "parent"
"""
    rev, down = parse_revision_meta(content)
    assert rev == "child"
    assert down == "parent"


def test_find_heads_and_ancestors() -> None:
    files = [
        ("a.py", 'revision: str = "root"\ndown_revision = None\n'),
        ("b.py", 'revision: str = "child"\ndown_revision: str = "root"\n'),
    ]
    graph = build_graph(files)
    assert find_heads(graph) == {"child"}
    assert ancestors("child", graph) == {"child", "root"}


def test_branch_extends_main_head() -> None:
    main_files = [
        ("a.py", 'revision: str = "m1"\ndown_revision = None\n'),
    ]
    branch_files = [
        *main_files,
        ("b.py", 'revision: str = "m2"\ndown_revision: str = "m1"\n'),
    ]
    main_graph = build_graph(main_files)
    branch_graph = build_graph(branch_files)
    main_head = next(iter(find_heads(main_graph)))
    branch_head = next(iter(find_heads(branch_graph)))
    assert main_head == "m1"
    assert branch_head == "m2"
    assert main_head in ancestors(branch_head, branch_graph)


@pytest.mark.parametrize(
    "ref",
    [
        "--output=/tmp/x",
        "origin/main;rm -rf /",
        "HEAD~1$(whoami)",
        "../main",
        "-c",
    ],
)
def test_reject_unsafe_git_refs(ref: str) -> None:
    with pytest.raises(ValueError):
        _validate_git_ref(ref)


def test_accept_safe_git_refs() -> None:
    assert _validate_git_ref("origin/main") == "origin/main"
    assert _validate_git_ref("HEAD") == "HEAD"
    assert _validate_git_ref("refs/heads/main") == "refs/heads/main"


@pytest.mark.parametrize(
    "path",
    [
        "backend/alembic/versions/../config.py",
        "backend/secrets.py",
        "backend/alembic/versions/x.py:foo",
        "-evil.py",
    ],
)
def test_reject_unsafe_versions_paths(path: str) -> None:
    with pytest.raises(ValueError):
        _validate_versions_path(path)
