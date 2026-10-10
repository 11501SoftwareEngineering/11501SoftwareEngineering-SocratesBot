#!/usr/bin/env python3
"""Ensure Alembic revisions on this branch extend the default branch without drift."""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from collections.abc import Iterable

VERSIONS_PREFIX = "backend/alembic/versions/"


def _run_git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def list_version_paths(ref: str) -> list[str]:
    out = _run_git("ls-tree", "-r", "--name-only", ref, "--", VERSIONS_PREFIX)
    if not out:
        return []
    return sorted(
        line
        for line in out.splitlines()
        if line.endswith(".py") and "__pycache__" not in line
    )


def file_at_ref(ref: str, path: str) -> str:
    return _run_git("show", f"{ref}:{path}")


def parse_revision_meta(content: str) -> tuple[str, str | tuple[str, ...] | None]:
    tree = ast.parse(content)
    revision: str | None = None
    down: str | tuple[str, ...] | None = None
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
            if (
                name == "revision"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                revision = node.value.value
            if name == "down_revision" and node.value is not None:
                down = _parse_down_revision(node.value)
            continue
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if (
                target.id == "revision"
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                revision = node.value.value
            if target.id == "down_revision":
                down = _parse_down_revision(node.value)
    if revision is None:
        msg = "could not parse revision id from migration file"
        raise ValueError(msg)
    return revision, down


def _parse_down_revision(node: ast.expr) -> str | tuple[str, ...] | None:
    if isinstance(node, ast.Constant):
        if node.value is None:
            return None
        if isinstance(node.value, str):
            return node.value
    if isinstance(node, ast.Tuple):
        parts: list[str] = []
        for elt in node.elts:
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                parts.append(elt.value)
            else:
                msg = "unsupported down_revision tuple element"
                raise ValueError(msg)
        return tuple(parts)
    msg = "unsupported down_revision expression"
    raise ValueError(msg)


def build_graph(
    files: Iterable[tuple[str, str]],
) -> dict[str, str | tuple[str, ...] | None]:
    graph: dict[str, str | tuple[str, ...] | None] = {}
    for _path, content in files:
        rev, down = parse_revision_meta(content)
        graph[rev] = down
    return graph


def find_heads(graph: dict[str, str | tuple[str, ...] | None]) -> set[str]:
    referenced: set[str] = set()
    for down in graph.values():
        if down is None:
            continue
        if isinstance(down, str):
            referenced.add(down)
        else:
            referenced.update(down)
    return set(graph.keys()) - referenced


def ancestors(rev: str, graph: dict[str, str | tuple[str, ...] | None]) -> set[str]:
    seen: set[str] = set()
    stack = [rev]
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        down = graph.get(current)
        if down is None:
            continue
        if isinstance(down, str):
            stack.append(down)
        else:
            stack.extend(down)
    return seen


def check(base_ref: str, head_ref: str = "HEAD") -> int:
    main_paths = list_version_paths(base_ref)
    head_paths = list_version_paths(head_ref)

    main_set = set(main_paths)
    head_set = set(head_paths)

    for path in sorted(main_set):
        if path not in head_set:
            print(f"::error::Missing migration file from {base_ref}: {path}")
            return 1
        main_body = file_at_ref(base_ref, path)
        head_body = file_at_ref(head_ref, path)
        if main_body != head_body:
            print(
                f"::error::Migration file changed relative to {base_ref}: {path} "
                "(rewrite history on default branch is not allowed)"
            )
            return 1

    main_files = [(p, file_at_ref(base_ref, p)) for p in main_paths]
    head_files = [(p, file_at_ref(head_ref, p)) for p in head_paths]

    main_graph = build_graph(main_files)
    head_graph = build_graph(head_files)

    main_heads = find_heads(main_graph)
    head_heads = find_heads(head_graph)

    if len(head_heads) != 1:
        print(
            f"::error::Expected exactly one Alembic head on this branch, "
            f"found {sorted(head_heads)}"
        )
        return 1

    if len(main_heads) != 1:
        print(
            f"::error::Expected exactly one Alembic head on {base_ref}, "
            f"found {sorted(main_heads)}"
        )
        return 1

    main_head = next(iter(main_heads))
    branch_head = next(iter(head_heads))

    if branch_head == main_head:
        print(f"Alembic head matches {base_ref} ({main_head}); no new revisions.")
        return 0

    branch_anc = ancestors(branch_head, head_graph)
    if main_head not in branch_anc:
        print(
            f"::error::Branch head {branch_head} does not extend {base_ref} "
            f"head {main_head}. Rebase and set down_revision to the current main head."
        )
        return 1

    added = sorted(head_set - main_set)
    print(
        f"Alembic aligned with {base_ref}: extends {main_head} -> {branch_head} "
        f"({len(added)} new revision file(s))."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Git ref for the default branch migration baseline (default: origin/main)",
    )
    args = parser.parse_args()
    try:
        _run_git("rev-parse", "--verify", args.base)
    except subprocess.CalledProcessError:
        print(f"::error::Base ref not found: {args.base}", file=sys.stderr)
        return 1
    return check(args.base)


if __name__ == "__main__":
    raise SystemExit(main())
