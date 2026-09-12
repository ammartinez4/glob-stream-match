# globstream

Glob pattern matching for paths, built around the case where the paths
don't fit in memory.

The standard library's `glob` module builds a full list of matches
before handing anything back, and `fnmatch` only compares one path at a
time - there's nothing in between for "I have a manifest of ten million
paths and I need the ones matching `**/*.log`, streamed". That's what
this is for: compile a pattern once, then match it against paths as
they arrive from a file, a subprocess, or a directory walk, without
ever holding the whole set in memory at once.

## Install

No PyPI release yet. Drop `src/globstream` on your path, or install
from a checkout:

```
pip install -e .
```

## Usage

Match a single path:

```python
from globstream import match

match("**/*.py", "src/globstream/core.py")   # True
match("*.py", "src/globstream/core.py")      # False, '*' doesn't cross '/'
```

Filter a huge line-delimited manifest without reading it all into a
list first - `filter_paths` and `read_paths` are both generators, so
only one line is ever in memory at a time:

```python
from globstream import filter_paths, read_paths

with open("manifest.txt") as f:
    for path in filter_paths(["**/*.py", "**/*.pyi"], read_paths(f)):
        print(path)
```

`filter_paths` works the same way against any iterable, including a
subprocess pipe:

```python
import subprocess
from globstream import filter_paths, read_paths

proc = subprocess.Popen(["find", ".", "-type", "f"], stdout=subprocess.PIPE, text=True)
for path in filter_paths("**/*.json", read_paths(proc.stdout)):
    print(path)
```

Walk a directory tree the same way. `walk` scans one directory at a
time with `os.scandir` and never accumulates a full tree listing, so
it's safe to point at a directory with millions of entries:

```python
from globstream import walk

for path in walk("/var/log", patterns="**/*.log"):
    print(path)
```

Compile once and reuse the pattern when matching many paths against it
directly:

```python
from globstream import compile_pattern

pattern = compile_pattern("src/**/*.py")
matches = [p for p in all_paths if pattern.match(p)]
```

## Pattern syntax

- `*` matches any run of characters within one path component (never
  crosses `/`)
- `?` matches a single character, not `/`
- `[seq]` / `[!seq]` character classes, same rules as `fnmatch`
- `**` as a whole path component matches zero or more components, so
  `a/**/b` matches `a/b`, `a/x/b`, and `a/x/y/b`

Patterns are matched against `/`-separated paths regardless of host
OS. `walk()` always yields forward-slash paths, since it joins path
components itself rather than going through `os.path.join`. Lines
from `read_paths()` are normalized the same way by default when
running on Windows (pass `normalize_sep=` to override); if you're
feeding paths in from somewhere else, normalize backslashes to `/`
yourself before matching.

`filter_paths` and `walk` both take a list of patterns instead of a
single one, and evaluate it gitignore-style: patterns are checked in
order, and whichever one last matches a given path decides whether
it's selected. Prefix a pattern with `!` to exclude paths that an
earlier pattern in the list selected:

```python
filter_paths(["**/*.py", "!**/test_*.py"], paths)  # all .py files except tests
```

A `!` on its own has nothing to negate, so `["!*.py"]` alone selects
nothing. Use `\!` to match a path that starts with a literal `!`.

## Status

Early. The matcher and streaming helpers work; see the roadmap for
what's missing.
