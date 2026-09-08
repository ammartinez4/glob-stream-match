"""Glob pattern translation and matching over streamed paths."""

import os
import re
from typing import Iterable, Iterator, List, Optional, Pattern, Union

__all__ = [
    "translate",
    "compile_pattern",
    "match",
    "filter_paths",
    "read_paths",
    "walk",
]


def translate(pattern: str) -> str:
    """
    Turn a glob pattern into a regex string anchored to a full match.

    Supported syntax, all scoped to a single path component unless noted:
      *       any run of characters, not crossing a '/'
      ?       a single character, not '/'
      [seq]   a character class, same rules as fnmatch ([!seq] negates it)
      **      as a whole path component, matches zero or more components
              ("a/**/b" matches "a/b", "a/x/b", "a/x/y/b", ...)

    Patterns are matched against forward-slash-separated paths regardless
    of the host OS - callers on Windows should normalize backslashes
    before matching.
    """
    segments = pattern.split("/")

    # Consecutive '**' components behave the same as a single one, so
    # collapse them up front rather than special-casing runs below.
    collapsed: List[str] = []
    for seg in segments:
        if seg == "**" and collapsed and collapsed[-1] == "**":
            continue
        collapsed.append(seg)
    segments = collapsed

    n = len(segments)
    parts: List[str] = []
    for i, seg in enumerate(segments):
        if seg == "**":
            if n == 1:
                parts.append(".*")
            elif i == 0:
                parts.append("(?:.*/)?")
            elif i == n - 1:
                parts.append("(?:/.*)?")
            else:
                parts.append("/(?:.*/)?")
        else:
            frag = _translate_segment(seg)
            if i == 0 or segments[i - 1] == "**":
                # A preceding '**' already emitted its own separator (or
                # this is the first segment), so no extra '/' is needed.
                parts.append(frag)
            else:
                parts.append("/" + frag)

    return "^" + "".join(parts) + "$"


def _translate_segment(seg: str) -> str:
    """Translate a single path component (no '/') to a regex fragment."""
    if seg == "":
        return ""
    out: List[str] = []
    i = 0
    n = len(seg)
    while i < n:
        c = seg[i]
        if c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            j = i + 1
            if j < n and seg[j] == "!":
                j += 1
            if j < n and seg[j] == "]":
                j += 1
            while j < n and seg[j] != "]":
                j += 1
            if j >= n:
                # No closing bracket - treat '[' as a literal character.
                out.append(re.escape("["))
                i += 1
            else:
                inner = seg[i + 1 : j]
                if inner.startswith("!"):
                    inner = "^" + inner[1:]
                out.append("[" + inner + "]")
                i = j + 1
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


def compile_pattern(pattern: str) -> Pattern[str]:
    """Compile a glob pattern into a regex Pattern for repeated matching."""
    return re.compile(translate(pattern))


def match(pattern: str, path: str) -> bool:
    """Return whether `path` matches `pattern`. Compiles on every call -
    use compile_pattern() directly when matching many paths against the
    same pattern."""
    return compile_pattern(pattern).match(path) is not None


def filter_paths(
    patterns: Union[str, Iterable[str]], paths: Iterable[str]
) -> Iterator[str]:
    """
    Yield each path in `paths` that matches at least one of `patterns`.

    `paths` is consumed one item at a time and nothing from it is kept
    around after being checked, so it can be a generator reading lines
    from a multi-gigabyte manifest, a subprocess's stdout, or any other
    source too large to hold in a list.
    """
    if isinstance(patterns, str):
        patterns = [patterns]
    compiled = [compile_pattern(p) for p in patterns]
    for path in paths:
        if any(p.match(path) for p in compiled):
            yield path


def read_paths(
    lines: Iterable[str], *, normalize_sep: Optional[bool] = None
) -> Iterator[str]:
    """
    Lazily yield non-empty, newline-stripped paths from an iterable of
    lines (for example an open file object). Intended to sit in front of
    filter_paths() when reading a path-per-line manifest:

        with open("manifest.txt") as f:
            for p in filter_paths("**/*.py", read_paths(f)):
                ...

    Patterns are always matched against forward-slash paths, but a
    manifest written on Windows will typically use backslashes. By
    default, lines are normalized (backslashes turned into forward
    slashes) when running on Windows (os.sep != '/'), and left alone
    otherwise. Pass `normalize_sep` explicitly to override that - for
    example when matching a manifest that was produced on a different
    OS than the one running the match.
    """
    if normalize_sep is None:
        normalize_sep = os.sep != "/"
    for line in lines:
        line = line.rstrip("\r\n")
        if not line:
            continue
        if normalize_sep:
            line = line.replace("\\", "/")
        yield line


def walk(
    root: str,
    patterns: Optional[Union[str, Iterable[str]]] = None,
    *,
    files_only: bool = False,
) -> Iterator[str]:
    """
    Recursively walk `root`, yielding paths (relative to `root`, using
    '/' separators) one at a time.

    Each directory is scanned with its own os.scandir() iterator, which
    is consumed and closed before its subdirectories are entered. No
    directory's full listing is kept once traversal moves past it, and
    no list of the whole tree is ever assembled, so memory use is
    bounded by tree depth rather than tree size.

    If `patterns` is given, only paths matching at least one pattern are
    yielded (directories included, unless files_only is set).
    """
    compiled: Optional[List[Pattern[str]]] = None
    if patterns is not None:
        if isinstance(patterns, str):
            patterns = [patterns]
        compiled = [compile_pattern(p) for p in patterns]

    def matches(rel_path: str) -> bool:
        if compiled is None:
            return True
        return any(p.match(rel_path) for p in compiled)

    def walk_dir(dir_path: str, rel_prefix: str) -> Iterator[str]:
        with os.scandir(dir_path) as it:
            for entry in it:
                rel = rel_prefix + entry.name
                if entry.is_dir(follow_symlinks=False):
                    if not files_only and matches(rel):
                        yield rel
                    yield from walk_dir(entry.path, rel + "/")
                else:
                    if matches(rel):
                        yield rel

    yield from walk_dir(root, "")
