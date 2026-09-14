"""Unit tests for translate() and the matching behavior it produces."""

import unittest

from globstream import first_match, match, match_any, translate


class TranslateAnchoringTest(unittest.TestCase):
    def test_anchored_to_full_string(self):
        regex = translate("*.py")
        self.assertTrue(regex.startswith("^"))
        self.assertTrue(regex.endswith("$"))

    def test_empty_pattern_matches_only_empty_string(self):
        self.assertTrue(match("", ""))
        self.assertFalse(match("", "a"))


class TranslateLiteralTest(unittest.TestCase):
    def test_plain_literal(self):
        self.assertTrue(match("core.py", "core.py"))
        self.assertFalse(match("core.py", "core.pyc"))

    def test_regex_metacharacters_are_escaped(self):
        # '.' in a pattern should mean a literal dot, not "any character".
        self.assertTrue(match("a.b", "a.b"))
        self.assertFalse(match("a.b", "axb"))
        self.assertTrue(match("a+b", "a+b"))


class TranslateStarTest(unittest.TestCase):
    def test_star_matches_within_one_component(self):
        self.assertTrue(match("*.py", "core.py"))
        self.assertFalse(match("*.py", "src/core.py"))

    def test_star_matches_empty_run(self):
        self.assertTrue(match("a*b", "ab"))

    def test_star_does_not_cross_slash(self):
        self.assertFalse(match("a*b", "a/b"))


class TranslateQuestionTest(unittest.TestCase):
    def test_question_matches_single_char(self):
        self.assertTrue(match("a?c", "abc"))
        self.assertFalse(match("a?c", "ac"))
        self.assertFalse(match("a?c", "abbc"))

    def test_question_does_not_match_slash(self):
        self.assertFalse(match("a?c", "a/c"))


class TranslateCharClassTest(unittest.TestCase):
    def test_simple_class(self):
        self.assertTrue(match("[abc].py", "a.py"))
        self.assertFalse(match("[abc].py", "d.py"))

    def test_negated_class(self):
        self.assertTrue(match("[!abc].py", "d.py"))
        self.assertFalse(match("[!abc].py", "a.py"))

    def test_leading_bang_in_class_is_negation_not_literal(self):
        regex = translate("[!a]")
        self.assertEqual(regex, "^[^a]$")

    def test_unclosed_bracket_is_literal(self):
        # No closing ']' - '[' should be treated as a literal character.
        self.assertTrue(match("[abc", "[abc"))
        self.assertFalse(match("[abc", "abc"))

    def test_bracket_immediately_closed_treats_bracket_as_member(self):
        # fnmatch semantics: '[]]' matches the literal ']'.
        self.assertTrue(match("[]]", "]"))


class TranslateDoubleStarTest(unittest.TestCase):
    def test_bare_double_star_matches_anything_including_slashes(self):
        self.assertTrue(match("**", ""))
        self.assertTrue(match("**", "a"))
        self.assertTrue(match("**", "a/b/c"))

    def test_leading_double_star_matches_zero_or_more_components(self):
        self.assertTrue(match("**/*.py", "core.py"))
        self.assertTrue(match("**/*.py", "src/core.py"))
        self.assertTrue(match("**/*.py", "src/globstream/core.py"))

    def test_trailing_double_star_matches_zero_or_more_components(self):
        self.assertTrue(match("src/**", "src"))
        self.assertTrue(match("src/**", "src/core.py"))
        self.assertTrue(match("src/**", "src/globstream/core.py"))

    def test_middle_double_star_matches_zero_or_more_components(self):
        self.assertTrue(match("a/**/b", "a/b"))
        self.assertTrue(match("a/**/b", "a/x/b"))
        self.assertTrue(match("a/**/b", "a/x/y/b"))
        self.assertFalse(match("a/**/b", "a/b/c"))

    def test_consecutive_double_stars_collapse_to_one(self):
        self.assertEqual(translate("a/**/**/b"), translate("a/**/b"))

    def test_double_star_does_not_match_across_unrelated_prefix(self):
        self.assertFalse(match("a/**/b", "x/a/b"))

    def test_double_star_component_must_be_whole_component(self):
        # '**' only has special meaning as an entire path component - here
        # it's part of a larger component, so it's just two '*' runs and
        # still can't cross a '/'.
        self.assertTrue(match("a**b", "axyzb"))
        self.assertFalse(match("a**b", "a/b"))


class FirstMatchTest(unittest.TestCase):
    def test_returns_first_matching_pattern(self):
        patterns = ["*.tar.gz", "*.gz", "*"]
        self.assertEqual(first_match(patterns, "archive.tar.gz"), "*.tar.gz")
        self.assertEqual(first_match(patterns, "file.gz"), "*.gz")
        self.assertEqual(first_match(patterns, "readme.txt"), "*")

    def test_returns_none_when_nothing_matches(self):
        self.assertIsNone(first_match(["*.py"], "readme.txt"))

    def test_empty_patterns_returns_none(self):
        self.assertIsNone(first_match([], "anything"))

    def test_does_not_compile_patterns_after_a_match(self):
        # A pattern past the first match shouldn't even be looked at,
        # let alone compiled - so a bogus one there is never an error.
        seen = []

        def patterns():
            seen.append("*.py")
            yield "*.py"
            seen.append("[unclosed")
            yield "[unclosed"

        self.assertEqual(first_match(patterns(), "core.py"), "*.py")
        self.assertEqual(seen, ["*.py"])

    def test_precedence_differs_from_gitignore_ordering(self):
        # filter_paths()/walk() use last-match-wins; first_match() uses
        # first-match-wins, so the same list picks the opposite pattern.
        patterns = ["*", "*.py"]
        self.assertEqual(first_match(patterns, "core.py"), "*")


class MatchAnyTest(unittest.TestCase):
    def test_true_when_any_pattern_matches(self):
        self.assertTrue(match_any(["*.py", "*.md"], "readme.md"))

    def test_false_when_none_match(self):
        self.assertFalse(match_any(["*.py", "*.md"], "notes.txt"))

    def test_empty_patterns_is_false(self):
        self.assertFalse(match_any([], "anything"))


if __name__ == "__main__":
    unittest.main()
