"""Tests for the transport-agnostic pipeline shared by ROS 2 and the web viewer.

These run with the Python standard library alone, so they execute in CI and in
the development container without a ROS 2 installation.
"""

import random
import unittest

from robo_rl_demo.detection import Detection
from robo_rl_demo.pipeline import (
    COMMAND_TOPIC,
    PICK_TOPIC,
    CameraSource,
    OperatorCommand,
    PickerLogic,
    format_publication,
    parse_command,
    simulate_grasp,
    validate_min_confidence,
    validate_rate_hz,
    validate_topic,
)


class RecordingTransport:
    """Minimal stand-in for the ROS publisher: records (topic, payload) pairs."""

    def __init__(self):
        self.published = []

    def __call__(self, topic, payload):
        self.published.append((topic, payload))


class ValidationTests(unittest.TestCase):
    def test_rate_must_be_positive_and_finite(self):
        self.assertEqual(validate_rate_hz(2.0), 2.0)
        for bad in (0.0, -1.0, float("nan"), float("inf"), True, "2"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_rate_hz(bad)

    def test_topic_must_be_non_empty(self):
        self.assertEqual(validate_topic("  detected_object "), "detected_object")
        for bad in ("", "   ", None, 7):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_topic(bad)

    def test_min_confidence_must_be_in_range(self):
        self.assertEqual(validate_min_confidence(0.65), 0.65)
        for bad in (-0.01, 1.01, float("nan"), None):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                validate_min_confidence(bad)


class CameraSourceTests(unittest.TestCase):
    def test_tick_publishes_valid_json_on_the_configured_topic(self):
        transport = RecordingTransport()
        source = CameraSource(transport, rate_hz=2.0, seed=7)

        detection = source.tick()

        self.assertEqual(len(transport.published), 1)
        topic, payload = transport.published[0]
        self.assertEqual(topic, PICK_TOPIC)
        self.assertEqual(Detection.from_json(payload), detection)

    def test_seeded_sources_are_reproducible_and_ids_increment(self):
        first = CameraSource(RecordingTransport(), seed=42)
        second = CameraSource(RecordingTransport(), seed=42)

        first_run = [first.tick() for _ in range(5)]
        second_run = [second.tick() for _ in range(5)]

        self.assertEqual(first_run, second_run)
        self.assertEqual([d.detection_id for d in first_run], [0, 1, 2, 3, 4])

    def test_publication_log_line_is_stable(self):
        detection = Detection(3, "item_c", 0.125, -0.2, 0.9)
        self.assertEqual(
            format_publication(detection),
            "Published #3: item_c at (0.125, -0.200) m, confidence=0.90",
        )


class PickerLogicTests(unittest.TestCase):
    def test_threshold_decisions_match_the_documented_wording(self):
        logic = PickerLogic(min_confidence=0.65)
        high = Detection(1, "item_a", 0.1, 0.2, 0.90)
        low = Detection(2, "item_b", 0.1, 0.2, 0.40)

        picked = logic.handle_payload(high.to_json())
        skipped = logic.handle_payload(low.to_json())

        self.assertTrue(picked.attempted)
        self.assertEqual(
            picked.message, "Would pick #1 (item_a) at (0.100, 0.200) m"
        )
        self.assertFalse(skipped.attempted)
        self.assertEqual(
            skipped.message,
            "Skipping #2 (item_b): confidence 0.40 is below 0.65",
        )
        self.assertEqual((logic.count_attempted, logic.count_skipped), (1, 1))

    def test_malformed_payload_never_raises_and_is_counted(self):
        logic = PickerLogic()

        for payload in ("not json", "[]", '{"id": 1}', "null"):
            with self.subTest(payload=payload):
                result = logic.handle_payload(payload)
                self.assertTrue(result.malformed)
                self.assertFalse(result.attempted)
                self.assertTrue(result.message.startswith("Ignoring malformed"))

        self.assertEqual(logic.count_malformed, 4)
        self.assertEqual((logic.count_attempted, logic.count_skipped), (0, 0))

    def test_threshold_can_be_changed_at_runtime(self):
        logic = PickerLogic(min_confidence=0.9)
        detection = Detection(1, "item_a", 0.0, 0.0, 0.7)
        self.assertFalse(logic.handle_payload(detection.to_json()).attempted)

        logic.set_min_confidence(0.5)
        self.assertTrue(logic.handle_payload(detection.to_json()).attempted)

        with self.assertRaises(ValueError):
            logic.set_min_confidence(1.5)

    def test_observer_sees_every_result_exactly_once(self):
        seen = []
        logic = PickerLogic(min_confidence=0.65, on_result=seen.append)

        logic.handle_payload(Detection(1, "item_a", 0.0, 0.0, 0.9).to_json())
        logic.handle_payload("garbage")

        self.assertEqual(len(seen), 2)
        self.assertIsInstance(seen[0], type(seen[0]))
        self.assertTrue(seen[0].attempted)
        self.assertTrue(seen[1].malformed)


class OperatorCommandTests(unittest.TestCase):
    def test_valid_commands_parse(self):
        self.assertEqual(parse_command('{"action": "start"}'), OperatorCommand("start"))
        self.assertEqual(parse_command('{"action": "stop"}'), OperatorCommand("stop"))
        self.assertEqual(
            parse_command('{"action": "call_support"}'),
            OperatorCommand("call_support"),
        )
        self.assertEqual(
            parse_command('{"action": "set_min_confidence", "value": 0.8}'),
            OperatorCommand("set_min_confidence", 0.8),
        )

    def test_invalid_commands_are_rejected(self):
        bad_payloads = (
            "not json",
            "[]",
            '{"action": "launch_missiles"}',
            '{"action": "set_min_confidence"}',
            '{"action": "set_min_confidence", "value": 2}',
        )
        for payload in bad_payloads:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_command(payload)

    def test_command_topic_default_is_documented(self):
        self.assertEqual(COMMAND_TOPIC, "arm_command")


class SimulateGraspTests(unittest.TestCase):
    def test_success_rate_increases_with_confidence(self):
        low = sum(simulate_grasp(0.2, random.Random(i)) for i in range(400))
        high = sum(simulate_grasp(0.95, random.Random(i)) for i in range(400))
        self.assertLess(low, high)

    def test_rejects_out_of_range_confidence(self):
        for bad in (-0.1, 1.1, float("nan")):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                simulate_grasp(bad, random.Random(0))


if __name__ == "__main__":
    unittest.main()
