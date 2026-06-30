import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fanctrl.sensors import group_temps, TEMP_GROUPS, TEMP_LABELS


class TestGroupTemps(unittest.TestCase):

    def test_basic_grouping(self):
        all_temps = {"TCAC": 50, "TCAD": 52, "TeGG": 45}
        result = group_temps(all_temps, include_unmapped=False)
        self.assertIn("CPU", result)
        self.assertEqual(result["CPU"], 52)
        self.assertIn("GPU", result)
        self.assertEqual(result["GPU"], 45)

    def test_ambient_included(self):
        result = group_temps({"TA0P": 28})
        self.assertIn("AMB", result)
        self.assertEqual(result["AMB"], 28)

    def test_group_with_missing_sensors(self):
        all_temps = {"TCAC": 50}
        result = group_temps(all_temps)
        self.assertEqual(result["CPU"], 50)
        self.assertNotIn("GPU", result)

    def test_empty_all_temps(self):
        result = group_temps({})
        self.assertEqual(result, {})

    def test_include_unmapped(self):
        all_temps = {"TCAC": 50, "UNKNOWN_SENSOR": 60, "TA0P": 28}
        result = group_temps(all_temps, include_unmapped=True)
        self.assertIn("UNMAPPED", result)
        self.assertEqual(result["UNMAPPED"], 60)

    def test_multiple_groups_with_overlap(self):
        all_temps = {}
        for group, keys in TEMP_GROUPS.items():
            for k in keys[:2]:
                all_temps[k] = 50 + hash(k) % 30
        result = group_temps(all_temps)
        for group in TEMP_GROUPS:
            self.assertIn(group, result, f"{group} missing from result")

    def test_group_max_correct(self):
        all_temps = {"TM0P": 30, "TM1P": 50, "TM2P": 45}
        result = group_temps(all_temps)
        self.assertEqual(result["MEM"], 50)


class TestTempLabels(unittest.TestCase):

    def test_known_sensors_have_labels(self):
        known = ["TCAC", "TeGG", "TA0P", "TMA1", "Tp0C", "TN0D"]
        for key in known:
            self.assertIn(key, TEMP_LABELS, f"{key} missing from TEMP_LABELS")

    def test_cpu_sensors_in_labels(self):
        for key in ["TCAC", "TCAD", "TCAG", "TCBC", "TCBD", "TCBG", "TCAH", "TCAS", "TCBH", "TCBS"]:
            self.assertIn(key, TEMP_LABELS, f"{key} missing from TEMP_LABELS")

    def test_gpu_sensors_in_labels(self):
        for key in ["TeGG", "TeGP", "TeRG", "TeRP"]:
            self.assertIn(key, TEMP_LABELS, f"{key} missing from TEMP_LABELS")


class TestTempGroups(unittest.TestCase):

    def test_all_groups_have_keys(self):
        for group, keys in TEMP_GROUPS.items():
            with self.subTest(group=group):
                self.assertTrue(len(keys) > 0, f"{group} has no keys")

    def test_no_duplicate_keys_across_groups(self):
        seen = {}
        for group, keys in TEMP_GROUPS.items():
            for k in keys:
                self.assertNotIn(k, seen, f"{k} appears in multiple TEMP_GROUPS")
                seen[k] = group

    def test_all_temp_group_keys_in_labels(self):
        missing = []
        for group, keys in TEMP_GROUPS.items():
            for k in keys:
                if k not in TEMP_LABELS:
                    missing.append(f"{k} in TEMP_GROUPS.{group}")
        if missing:
            self.fail(f"Sensors missing from TEMP_LABELS: {', '.join(missing)}")


if __name__ == "__main__":
    unittest.main()
