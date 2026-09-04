"""Unit tests for translate() and the matching behavior it produces."""

import unittest

from globstream import match, translate


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


if __name__ == "__main__":
    unittest.main()
