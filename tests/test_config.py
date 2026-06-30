import sys
import os
import tempfile
import json
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fanctrl.config import validate_profile, DEFAULT_PROFILES, DEFAULT_SAFETY


class TestValidateProfile(unittest.TestCase):

    def test_valid_profile(self):
        profile = {
            "fans": {
                "BOOST": {
                    "sensors": ["TCAC"],
                    "curve": [[0, 800], [50, 2000], [70, 4500]]
                }
            }
        }
        valid, msg = validate_profile(profile)
        self.assertTrue(valid, msg)

    def test_no_fans(self):
        valid, msg = validate_profile({"fans": {}})
        self.assertFalse(valid)

    def test_curve_less_than_2_points(self):
        profile = {
            "fans": {
                "BOOST": {
                    "sensors": ["TCAC"],
                    "curve": [[0, 800]]
                }
            }
        }
        valid, msg = validate_profile(profile)
        self.assertFalse(valid)

    def test_curve_not_sorted(self):
        profile = {
            "fans": {
                "BOOST": {
                    "sensors": ["TCAC"],
                    "curve": [[0, 800], [70, 4500], [50, 2000]]
                }
            }
        }
        valid, msg = validate_profile(profile)
        self.assertFalse(valid)

    def test_negative_rpm(self):
        profile = {
            "fans": {
                "BOOST": {
                    "sensors": ["TCAC"],
                    "curve": [[0, -100], [50, 2000]]
                }
            }
        }
        valid, msg = validate_profile(profile)
        self.assertFalse(valid)

    def test_invalid_point_format(self):
        profile = {
            "fans": {
                "BOOST": {
                    "sensors": ["TCAC"],
                    "curve": [0, 800]
                }
            }
        }
        valid, msg = validate_profile(profile)
        self.assertFalse(valid)

    def test_safety_valid_dict(self):
        profile = {
            "fans": {
                "BOOST": {
                    "sensors": ["TCAC"],
                    "curve": [[0, 800], [70, 4500]]
                }
            },
            "safety": {"system_max_temp": 90, "gpu_max_temp": 85}
        }
        valid, msg = validate_profile(profile)
        self.assertTrue(valid, msg)

    def test_safety_invalid_type(self):
        profile = {
            "fans": {
                "BOOST": {
                    "sensors": ["TCAC"],
                    "curve": [[0, 800], [70, 4500]]
                }
            },
            "safety": "not_a_dict"
        }
        valid, msg = validate_profile(profile)
        self.assertFalse(valid)


class TestDefaultProfiles(unittest.TestCase):

    def test_all_default_profiles_valid(self):
        for name, profile in DEFAULT_PROFILES.items():
            with self.subTest(profile=name):
                valid, msg = validate_profile(profile)
                self.assertTrue(valid, f"{name}: {msg}")

    def test_all_defaults_have_safety(self):
        for name, profile in DEFAULT_PROFILES.items():
            with self.subTest(profile=name):
                self.assertIn("safety", profile)
                self.assertIn("system_max_temp", profile["safety"])

    def test_all_defaults_have_hysteresis(self):
        for name, profile in DEFAULT_PROFILES.items():
            with self.subTest(profile=name):
                self.assertIn("hysteresis", profile)
                self.assertIn("deadband", profile["hysteresis"])

    def test_all_defaults_have_slew_rate(self):
        for name, profile in DEFAULT_PROFILES.items():
            with self.subTest(profile=name):
                self.assertIn("slew_rate", profile)
                self.assertIn("max_rpm_change_per_cycle", profile["slew_rate"])

    def test_exhaust_rpm_capped_single_cpu(self):
        single_cpu = ["silent", "quiet_daily", "heavy_work", "render_mode"]
        for name in single_cpu:
            with self.subTest(profile=name):
                exhaust = DEFAULT_PROFILES[name]["fans"]["EXHAUST"]
                max_rpm = exhaust["curve"][-1][1]
                self.assertLessEqual(max_rpm, 2800, f"{name}: EXHAUST max={max_rpm}")

    def test_intake_rpm_capped_single_cpu(self):
        single_cpu = ["silent", "quiet_daily", "heavy_work", "render_mode"]
        for name in single_cpu:
            with self.subTest(profile=name):
                intake = DEFAULT_PROFILES[name]["fans"]["INTAKE"]
                max_rpm = intake["curve"][-1][1]
                self.assertLessEqual(max_rpm, 2800, f"{name}: INTAKE max={max_rpm}")

    def test_pci_includes_non_smc_sensors(self):
        for name, profile in DEFAULT_PROFILES.items():
            with self.subTest(profile=name):
                pci_sensors = profile["fans"]["PCI"]["sensors"]
                self.assertIn("edge", pci_sensors)
                self.assertIn("junction", pci_sensors)
                self.assertIn("mem", pci_sensors)


if __name__ == "__main__":
    unittest.main()
