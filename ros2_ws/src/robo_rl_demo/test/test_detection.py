"""Unit tests for the ROS-independent parts of the ROS 2 demo."""

import json
import random
import unittest

from robo_rl_demo.detection import (
    DEMO_LABELS,
    Detection,
    make_demo_detection,
    should_attempt_pick,
)


class DetectionTests(unittest.TestCase):
    def test_json_round_trip(self):
        original = Detection(7, "item_b", 0.125, -0.2, 0.91)
        self.assertEqual(Detection.from_json(original.to_json()), original)

    def test_rejects_invalid_json_and_non_object_payloads(self):
        for payload in ("not json", "[]", "null", "\"text\""):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                Detection.from_json(payload)

    def test_rejects_missing_and_invalid_fields(self):
        with self.assertRaisesRegex(ValueError, "missing required"):
            Detection.from_json('{"id": 1}')

        invalid_payloads = (
            {"id": True, "label": "item_a", "x": 0, "y": 0, "confidence": 0.5},
            {"id": -1, "label": "item_a", "x": 0, "y": 0, "confidence": 0.5},
            {"id": 1, "label": " ", "x": 0, "y": 0, "confidence": 0.5},
            {"id": 1, "label": "item_a", "x": float("nan"), "y": 0, "confidence": 0.5},
            {"id": 1, "label": "item_a", "x": 0, "y": 0, "confidence": 1.1},
        )
        for record in invalid_payloads:
            with self.subTest(record=record), self.assertRaises(ValueError):
                Detection.from_json(json.dumps(record))

    def test_confidence_threshold_is_inclusive(self):
        detection = Detection(1, "item_a", 0, 0, 0.65)
        self.assertTrue(should_attempt_pick(detection, 0.65))
        self.assertFalse(should_attempt_pick(detection, 0.66))

    def test_confidence_threshold_must_be_in_range(self):
        detection = Detection(1, "item_a", 0, 0, 0.5)
        for threshold in (-0.1, 1.1, float("nan")):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                should_attempt_pick(detection, threshold)

    def test_demo_data_is_repeatable_with_a_seed_and_bounded(self):
        first = make_demo_detection(random.Random(42), 0)
        second = make_demo_detection(random.Random(42), 0)
        self.assertEqual(first, second)
        self.assertIn(first.label, DEMO_LABELS)
        self.assertGreaterEqual(first.x, -0.25)
        self.assertLessEqual(first.x, 0.25)
        self.assertGreaterEqual(first.y, -0.25)
        self.assertLessEqual(first.y, 0.25)
        self.assertGreaterEqual(first.confidence, 0.35)
        self.assertLessEqual(first.confidence, 1.0)


if __name__ == "__main__":
    unittest.main()
