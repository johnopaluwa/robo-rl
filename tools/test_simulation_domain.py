"""Dependency-free regression tests for the simulation randomization ranges."""

import random
import unittest

from simulation.domain_randomization import sample_domain_parameters


class DomainRandomizationTests(unittest.TestCase):
    def test_same_seed_reproduces_the_same_scene_parameters(self):
        first = sample_domain_parameters(random.Random(2026))
        second = sample_domain_parameters(random.Random(2026))
        self.assertEqual(first, second)

    def test_randomized_parameters_vary_and_stay_in_documented_ranges(self):
        samples = [sample_domain_parameters(random.Random(seed)) for seed in range(12)]
        self.assertGreater(len({sample.source_x for sample in samples}), 1)
        self.assertGreater(len({sample.target_y for sample in samples}), 1)
        self.assertGreater(len({sample.tray_scale for sample in samples}), 1)
        self.assertGreater(len({sample.friction for sample in samples}), 1)
        self.assertGreater(len({sample.light_intensity for sample in samples}), 1)
        for sample in samples:
            self.assertGreaterEqual(sample.source_x, -0.36)
            self.assertLessEqual(sample.source_x, -0.22)
            self.assertGreaterEqual(sample.source_y, -0.18)
            self.assertLessEqual(sample.source_y, 0.18)
            self.assertGreaterEqual(sample.target_x, 0.22)
            self.assertLessEqual(sample.target_x, 0.36)
            self.assertGreaterEqual(sample.target_y, -0.18)
            self.assertLessEqual(sample.target_y, 0.18)
            self.assertGreaterEqual(sample.tray_scale, 0.85)
            self.assertLessEqual(sample.tray_scale, 1.15)
            self.assertGreaterEqual(sample.friction, 0.55)
            self.assertLessEqual(sample.friction, 1.35)
            self.assertGreaterEqual(sample.light_intensity, 0.65)
            self.assertLessEqual(sample.light_intensity, 1.0)

    def test_parameters_export_json_friendly_values(self):
        params = sample_domain_parameters(random.Random(1))
        self.assertEqual(
            set(params.to_dict()),
            {
                "source_x",
                "source_y",
                "target_x",
                "target_y",
                "tray_scale",
                "friction",
                "light_intensity",
            },
        )
        self.assertTrue(all(isinstance(value, float) for value in params.to_dict().values()))


if __name__ == "__main__":
    unittest.main()
