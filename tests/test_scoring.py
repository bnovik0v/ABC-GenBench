from __future__ import annotations

import unittest

from abcgenbench.scoring import score_control, soft_range_score


class ScoringTests(unittest.TestCase):
    def test_control_score_is_not_gated_by_parse_success(self) -> None:
        instance = {
            "constraints": {
                "meter": "6/8",
                "key": "G",
                "tune_type": "jig",
                "sections": 1,
                "bars": 4,
                "min_pitch": 67,
                "max_pitch": 88,
            }
        }
        output = "X:1\nT:Simple Jig\nM:6/8\nL:1/8\nK:G\n|:DGG BAG|Bcd edB|AGA Bcd|e2d B2:|"
        metrics = score_control(instance, output)
        self.assertEqual(metrics["metadata_accuracy"], 1.0)
        self.assertEqual(metrics["section_count_accuracy"], 1.0)
        self.assertEqual(metrics["bar_count_accuracy"], 1.0)
        self.assertGreater(metrics["control_code_similarity"], 0.6)

    def test_soft_range_score_degrades_gradually(self) -> None:
        self.assertEqual(soft_range_score(actual_min=67, actual_max=79, min_pitch=67, max_pitch=88), 1.0)
        self.assertGreater(soft_range_score(actual_min=62, actual_max=79, min_pitch=67, max_pitch=88), 0.5)


if __name__ == "__main__":
    unittest.main()
