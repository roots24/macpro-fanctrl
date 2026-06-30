import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fanctrl.daemon import interpolate, safety_check, gpu_safety_check, get_sensor_fallback


class TestInterpolate(unittest.TestCase):

    def test_basic_interpolation(self):
        curve = [[0, 800], [50, 2000], [70, 4500]]
        self.assertEqual(interpolate(curve, 0), 800)
        self.assertEqual(interpolate(curve, 70), 4500)

    def test_mid_point(self):
        curve = [[0, 800], [50, 2000]]
        self.assertEqual(interpolate(curve, 25), 1400)

    def test_clamp_below_min(self):
        curve = [[30, 1000], [70, 3000]]
        self.assertEqual(interpolate(curve, 0), 1000)

    def test_clamp_above_max(self):
        curve = [[30, 1000], [70, 3000]]
        self.assertEqual(interpolate(curve, 100), 3000)

    def test_unsorted_curve(self):
        curve = [[70, 4500], [0, 800], [50, 2000]]
        self.assertEqual(interpolate(curve, 25), 1400)

    def test_empty_curve(self):
        self.assertEqual(interpolate([], 50), 800)

    def test_single_point_curve(self):
        self.assertEqual(interpolate([[30, 1000]], 50), 800)

    def test_exact_temp_match(self):
        curve = [[0, 800], [30, 1000], [60, 2000], [70, 4500]]
        self.assertEqual(interpolate(curve, 30), 1000)
        self.assertEqual(interpolate(curve, 60), 2000)

    def test_fractional_temperature(self):
        curve = [[0, 800], [10, 1800]]
        self.assertEqual(interpolate(curve, 5), 1300)

    def test_large_curve(self):
        curve = [[0, 800], [20, 800], [40, 1200], [60, 2500], [80, 4000], [100, 6000]]
        self.assertEqual(interpolate(curve, 10), 800)
        self.assertEqual(interpolate(curve, 30), 1000)
        self.assertEqual(interpolate(curve, 50), 1850)
        self.assertEqual(interpolate(curve, 90), 5000)


class TestSafetyCheck(unittest.TestCase):

    def test_below_threshold(self):
        self.assertFalse(safety_check({"TCAC": 50, "TeGG": 45}, max_safe=95))

    def test_at_threshold(self):
        self.assertFalse(safety_check({"TCAC": 95}, max_safe=95))

    def test_above_threshold(self):
        self.assertTrue(safety_check({"TCAC": 96}, max_safe=95))

    def test_empty_dict(self):
        self.assertFalse(safety_check({}, max_safe=95))

    def test_one_sensor_above(self):
        self.assertTrue(safety_check({"TCAC": 50, "TeGG": 96, "TA0P": 30}, max_safe=95))

    def test_custom_threshold(self):
        self.assertFalse(safety_check({"TCAC": 80}, max_safe=85))
        self.assertTrue(safety_check({"TCAC": 86}, max_safe=85))


class TestGpuSafetyCheck(unittest.TestCase):

    def test_below_threshold(self):
        keys = ["TeGG", "TeRG"]
        self.assertFalse(gpu_safety_check({"TeGG": 50, "TeRG": 45}, keys, max_gpu=90))

    def test_above_threshold(self):
        keys = ["TeGG", "TeRG"]
        self.assertTrue(gpu_safety_check({"TeGG": 95}, keys, max_gpu=90))

    def test_sensor_missing(self):
        keys = ["TeGG", "TeRG"]
        self.assertFalse(gpu_safety_check({"TCAC": 95}, keys, max_gpu=90))

    def test_custom_gpu_keys(self):
        keys = ["edge", "junction"]
        self.assertTrue(gpu_safety_check({"edge": 92}, keys, max_gpu=90))
        self.assertFalse(gpu_safety_check({"edge": 50, "junction": 55}, keys, max_gpu=90))


class TestGetSensorFallback(unittest.TestCase):

    def test_primary_sensors_available(self):
        all_temps = {"TCAC": 50, "TCAD": 52, "TeGG": 45}
        result = get_sensor_fallback(all_temps, ["TCAC", "TCAD"])
        self.assertEqual(result, [50, 52])

    def test_primary_missing_fallback_to_gpu(self):
        all_temps = {"TeGG": 45, "TeGP": 48, "TCAC": 50}
        result = get_sensor_fallback(all_temps, ["MISSING1", "MISSING2"])
        self.assertEqual(result, [45, 48])

    def test_all_missing(self):
        self.assertEqual(get_sensor_fallback({}, ["TCAC"]), [])

    def test_partial_primary(self):
        all_temps = {"TCAC": 50}
        result = get_sensor_fallback(all_temps, ["TCAC", "MISSING"])
        self.assertEqual(result, [50])

    def test_fallback_to_pci_when_gpu_missing(self):
        all_temps = {"TMA1": 35, "TMA2": 38}
        result = get_sensor_fallback(all_temps, ["MISSING"])
        self.assertIn(35, result)
        self.assertIn(38, result)


if __name__ == "__main__":
    unittest.main()
