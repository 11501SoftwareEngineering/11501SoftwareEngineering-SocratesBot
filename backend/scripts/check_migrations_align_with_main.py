#!/usr/bin/env python3
"""Ensure Alembic revisions on this branch extend the default branch without drift."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
from collections.abc import Iterable

VERSIONS_PREFIX = "backend/alembic/versions/"
# Safe git ref for --base / HEAD: no leading dash, no shell metacharacters.
_GIT_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/\-]*$")
_VERSIONS_PATH_RE = re.compile(rf"^{re.escape(VERSIONS_PREFIX)}[A-Za-z0-9._/\-]+\.py$")


def _validate_git_ref(ref: str) -> str:
    """Reject git refs that could inject argv or path traversal."""
    if not _GIT_REF_RE.fullmatch(ref) or ".." in ref:
        msg = f"unsafe or invalid git ref: {ref!r}"
        raise ValueError(msg)
    return ref


def _validate_versions_path(path: str) -> str:
    """Reject migration paths outside versions/ or with unsafe characters."""
    if not _VERSIONS_PATH_RE.fullmatch(path) or ".." in path:
        msg = f"unsafe or invalid migration path: {path!r}"
        raise ValueError(msg)
    return path


def _repo_root() -> str:
    """Return the git repository root (works from backend/ or repo root)."""
    # Resolve once without -C so the script works from backend/ or repo root.
    root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
    ).strip()
    if not root or "\x00" in root:
        raise ValueError("could not resolve git repository root")
    return root


def _run_git(*args: str) -> str:
    """Run git with a fixed argv list from the repository root; return stdout."""
    if not args:
        raise ValueError("git argv must not be empty")
    for arg in args:
        if "\x00" in arg:
            raise ValueError("git argv must not contain NUL")
    # argv list form (no shell); -C keeps pathspecs repo-root-relative.
    return subprocess.check_output(
        ["git", "-C", _repo_root(), *args],
        text=True,
    ).strip()


def list_version_paths(ref: str) -> list[str]:
    """List validated Alembic version .py paths present at the given git ref."""
    ref = _validate_git_ref(ref)
    out = _run_git("ls-tree", "-r", "--name-only", ref, "--", VERSIONS_PREFIX)
    if not out:
        return []
    return sorted(
        _validate_versions_path(line)
        for line in out.splitlines()
        if line.endswith(".py") and "__pycache__" not in line
    )


def file_at_ref(ref: str, path: str) -> str:
    """Return the contents of a migration file at ref:path via cat-file."""
    ref = _validate_git_ref(ref)
    path = _validate_versions_path(path)
    # Resolve blob via rev-parse then cat-file so path cannot inject show options.
    blob = _run_git("rev-parse", "--verify", "--quiet", f"{ref}:{path}")
    return _run_git("cat-file", "-p", blob)


def parse_revision_meta(content: str) -> tuple[str, str | tuple[str, ...] | None]:
    """Parse revision and down_revision from a migration module source."""
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
    """Parse a down_revision AST expression into str, tuple, or None."""
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
    """Build revision -> down_revision from (path, content) migration pairs."""
    graph: dict[str, str | tuple[str, ...] | None] = {}
    for _path, content in files:
        rev, down = parse_revision_meta(content)
        graph[rev] = down
    return graph


def find_heads(graph: dict[str, str | tuple[str, ...] | None]) -> set[str]:
    """Return revision ids that are not referenced as any down_revision."""
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
    """Return rev and all reachable down_revision ancestors in the graph."""
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
    """Verify head_ref migrations align with base_ref; return process exit code."""
    main_paths = list_version_paths(base_ref)
    head_paths = list_version_paths(head_ref)

    main_set = set(main_paths)
    head_set = set(head_paths)

    # 1) Baseline files on base_ref must still exist on the branch, byte-identical
    #    (no rewriting history of migrations already on main).
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

    # 2) Build revision graphs and require exactly one Alembic head on each side.
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

    # 3) Same head as base → nothing new; otherwise branch head must descend
    #    from base head (linear extension, no silent fork).
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
    """CLI entry: validate --base and run the alignment check."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Git ref for the default branch migration baseline (default: origin/main)",
    )
    args = parser.parse_args()
    try:
        base = _validate_git_ref(args.base)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    try:
        _run_git("rev-parse", "--verify", base)
    except subprocess.CalledProcessError:
        print(f"::error::Base ref not found: {base}", file=sys.stderr)
        return 1
    try:
        return check(base)
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
