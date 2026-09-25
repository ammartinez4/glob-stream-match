"""Unit tests for filter_paths() and walk()."""

import os
import tempfile
import unittest

from globstream import filter_paths, read_paths, walk


class ReadPathsTest(unittest.TestCase):
    def test_strips_newlines_and_skips_blank_lines(self):
        lines = ["a.py\n", "\n", "b.py\r\n", "c.py"]
        self.assertEqual(list(read_paths(lines)), ["a.py", "b.py", "c.py"])

    def test_normalizes_backslashes_when_requested(self):
        lines = ["src\\pkg\\mod.py"]
        result = list(read_paths(lines, normalize_sep=True))
        self.assertEqual(result, ["src/pkg/mod.py"])

    def test_leaves_backslashes_alone_when_disabled(self):
        lines = ["src\\pkg\\mod.py"]
        result = list(read_paths(lines, normalize_sep=False))
        self.assertEqual(result, ["src\\pkg\\mod.py"])

    def test_default_follows_host_separator(self):
        lines = ["src\\pkg\\mod.py"]
        result = list(read_paths(lines))
        if os.sep == "/":
            self.assertEqual(result, ["src\\pkg\\mod.py"])
        else:
            self.assertEqual(result, ["src/pkg/mod.py"])


class FilterPathsTest(unittest.TestCase):
    def test_yields_only_matching_paths(self):
        paths = ["a.py", "a.txt", "b.py", "b.txt"]
        result = list(filter_paths("*.py", paths))
        self.assertEqual(result, ["a.py", "b.py"])

    def test_single_pattern_string_is_wrapped(self):
        # A bare string pattern should behave like a one-element list,
        # not get iterated character by character.
        result = list(filter_paths("*.py", ["a.py"]))
        self.assertEqual(result, ["a.py"])

    def test_multiple_patterns_are_ored(self):
        paths = ["a.py", "a.txt", "a.md"]
        result = list(filter_paths(["*.py", "*.md"], paths))
        self.assertEqual(result, ["a.py", "a.md"])

    def test_empty_patterns_matches_nothing(self):
        result = list(filter_paths([], ["a.py", "b.py"]))
        self.assertEqual(result, [])

    def test_empty_input_yields_nothing(self):
        result = list(filter_paths("*.py", []))
        self.assertEqual(result, [])

    def test_negated_pattern_excludes_from_earlier_match(self):
        paths = ["a.py", "test_a.py", "b.py"]
        result = list(filter_paths(["*.py", "!test_*.py"], paths))
        self.assertEqual(result, ["a.py", "b.py"])

    def test_case_sensitive_by_default(self):
        result = list(filter_paths("*.PY", ["a.py", "b.PY"]))
        self.assertEqual(result, ["b.PY"])

    def test_case_insensitive_when_requested(self):
        result = list(
            filter_paths("*.PY", ["a.py", "b.PY"], case_sensitive=False)
        )
        self.assertEqual(result, ["a.py", "b.PY"])

    def test_negated_pattern_alone_matches_nothing(self):
        # There's nothing earlier for it to carve an exception out of.
        result = list(filter_paths("!*.py", ["a.py"]))
        self.assertEqual(result, [])

    def test_later_positive_pattern_overrides_earlier_negation(self):
        paths = ["keep.py"]
        result = list(filter_paths(["!*.py", "keep.py"], paths))
        self.assertEqual(result, ["keep.py"])

    def test_escaped_bang_is_a_literal_pattern_character(self):
        result = list(filter_paths("\\!important", ["!important", "important"]))
        self.assertEqual(result, ["!important"])

    def test_consumes_input_lazily(self):
        # Only the items actually needed to produce one match should ever
        # be pulled from the source iterable.
        consumed = []

        def source():
            for i in range(10**9):
                consumed.append(i)
                yield "match.py" if i == 0 else f"file{i}.txt"

        it = filter_paths("*.py", source())
        self.assertEqual(next(it), "match.py")
        self.assertEqual(consumed, [0])


class WalkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self._touch("a.py")
        self._touch("b.txt")
        self._touch("src/core.py")
        self._touch("src/pkg/__init__.py")
        self._touch("src/pkg/mod.py")
        os.makedirs(os.path.join(self.root, "empty_dir"))

    def tearDown(self):
        self.tmp.cleanup()

    def _touch(self, rel_path):
        full = os.path.join(self.root, *rel_path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w"):
            pass

    def test_yields_files_and_dirs_relative_to_root(self):
        result = set(walk(self.root))
        self.assertEqual(
            result,
            {
                "a.py",
                "b.txt",
                "src",
                "src/core.py",
                "src/pkg",
                "src/pkg/__init__.py",
                "src/pkg/mod.py",
                "empty_dir",
            },
        )

    def test_files_only_excludes_directories(self):
        result = set(walk(self.root, files_only=True))
        self.assertEqual(
            result,
            {
                "a.py",
                "b.txt",
                "src/core.py",
                "src/pkg/__init__.py",
                "src/pkg/mod.py",
            },
        )

    def test_filters_by_pattern_across_depths(self):
        result = set(walk(self.root, patterns="**/*.py"))
        self.assertEqual(
            result,
            {"a.py", "src/core.py", "src/pkg/__init__.py", "src/pkg/mod.py"},
        )

    def test_pattern_can_select_a_directory_and_its_contents(self):
        result = set(walk(self.root, patterns="src/**"))
        self.assertEqual(
            result,
            {
                "src",
                "src/core.py",
                "src/pkg",
                "src/pkg/__init__.py",
                "src/pkg/mod.py",
            },
        )

    def test_multiple_patterns_are_ored(self):
        result = set(walk(self.root, patterns=["*.txt", "empty_dir"]))
        self.assertEqual(result, {"b.txt", "empty_dir"})

    def test_no_matches_yields_nothing(self):
        result = list(walk(self.root, patterns="*.nonexistent"))
        self.assertEqual(result, [])

    def test_negated_pattern_excludes_from_earlier_match(self):
        result = set(walk(self.root, patterns=["**/*.py", "!src/pkg/*.py"]))
        self.assertEqual(result, {"a.py", "src/core.py"})

    def test_empty_directory_yields_nothing(self):
        empty_root = os.path.join(self.root, "empty_dir")
        self.assertEqual(list(walk(empty_root)), [])

    def test_missing_root_raises(self):
        missing = os.path.join(self.root, "does-not-exist")
        with self.assertRaises(FileNotFoundError):
            list(walk(missing))

    def test_case_insensitive_pattern(self):
        result = set(walk(self.root, patterns="*.PY", case_sensitive=False))
        self.assertEqual(result, {"a.py"})


if __name__ == "__main__":
    unittest.main()
