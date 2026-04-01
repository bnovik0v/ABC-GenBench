from __future__ import annotations

import unittest

from abcgenbench.canon import canonicalize_abc, normalized_levenshtein
from abcgenbench.parsers import DEFAULT_PARSERS, LightweightABCParser, split_musical_bars


class CanonicalizationTests(unittest.TestCase):
    def test_canonicalize_equivalent_abc(self) -> None:
        left = "T:Example\nX:1\nM:4/4\nL:1/4\nK:C\nCDEF|GABc|]"
        right = "X:1\nT:Example\nM:4/4\nL:1/4\nK:C\nCDEF | GABc |]"
        self.assertEqual(canonicalize_abc(left), canonicalize_abc(right))

    def test_normalized_levenshtein_identity(self) -> None:
        self.assertEqual(normalized_levenshtein("abc", "abc"), 0.0)


class ParserTests(unittest.TestCase):
    def test_default_parsers_include_music21_backend(self) -> None:
        self.assertGreaterEqual(len(DEFAULT_PARSERS), 2)

    def test_valid_fixture_tune_parses(self) -> None:
        abc = "X:1\nT:Valid Example\nM:4/4\nL:1/4\nR:reel\nK:D\nDEFG | ABcd | dcBA | GFED |]"
        result = LightweightABCParser().parse(abc)
        self.assertTrue(result.parse_success)
        self.assertTrue(result.bar_duration_consistent)
        self.assertEqual(result.bar_count, 4)

    def test_duration_modifiers_are_counted(self) -> None:
        abc = "X:1\nT:Duration Example\nM:4/4\nL:1/4\nK:G\nGABc | d2BG | dcBA |]"
        result = LightweightABCParser().parse(abc)
        self.assertTrue(result.parse_success)
        self.assertTrue(result.bar_duration_consistent)

    def test_repeat_markers_do_not_inflate_bar_count(self) -> None:
        body = "|:DGG BAG|Bcd edB|AGA Bcd|e2d B2:|"
        self.assertEqual(len(split_musical_bars(body)), 4)
        result = LightweightABCParser().parse(
            "X:1\nT:Repeat Example\nM:6/8\nL:1/8\nK:G\n|:DGG BAG|Bcd edB|AGA Bcd|e2d B2:|"
        )
        self.assertEqual(result.bar_count, 4)


if __name__ == "__main__":
    unittest.main()
