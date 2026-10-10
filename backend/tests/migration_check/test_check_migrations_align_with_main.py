from scripts.check_migrations_align_with_main import (
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
