import sys
import os
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fanctrl.pid import PIDController


class TestPIDController(unittest.TestCase):

    def test_initialization(self):
        pid = PIDController(kp=10, ki=0.5, kd=2.0, target_temp=50)
        self.assertEqual(pid.kp, 10)
        self.assertEqual(pid.ki, 0.5)
        self.assertEqual(pid.kd, 2.0)
        self.assertEqual(pid.target, 50)

    def test_output_clamped_to_min(self):
        pid = PIDController(kp=10, ki=0, kd=0, target_temp=50,
                            output_min=800, output_max=4500)
        rpm = pid.compute(current_temp=60, current_rpm=800)
        self.assertGreaterEqual(rpm, 800)

    def test_output_clamped_to_max(self):
        pid = PIDController(kp=1000, ki=0, kd=0, target_temp=50,
                            output_min=800, output_max=4500)
        rpm = pid.compute(current_temp=100, current_rpm=800)
        self.assertLessEqual(rpm, 4500)

    def test_proportional_response(self):
        pid = PIDController(kp=10, ki=0, kd=0, target_temp=50,
                            output_min=800, output_max=4500)
        rpm1 = pid.compute(current_temp=60, current_rpm=800)
        time.sleep(0.01)
        rpm2 = pid.compute(current_temp=70, current_rpm=rpm1)
        self.assertGreater(rpm2, rpm1)

    def test_cooler_temp_lower_fan(self):
        pid = PIDController(kp=10, ki=0, kd=0, target_temp=50,
                            output_min=800, output_max=4500)
        pid.reset()
        time.sleep(0.01)
        rpm_hot = pid.compute(current_temp=60, current_rpm=800)
        pid.reset()
        time.sleep(0.01)
        rpm_cool = pid.compute(current_temp=40, current_rpm=800)
        self.assertLess(rpm_cool, rpm_hot)

    def test_integral_accumulates(self):
        pid = PIDController(kp=0, ki=1, kd=0, target_temp=50,
                            output_min=800, output_max=4500)
        pid.reset()
        time.sleep(0.01)
        rpm1 = pid.compute(current_temp=60, current_rpm=800)
        time.sleep(0.01)
        rpm2 = pid.compute(current_temp=60, current_rpm=rpm1)
        self.assertGreater(rpm2, rpm1)

    def test_integral_anti_windup(self):
        pid = PIDController(kp=0, ki=100, kd=0, target_temp=50,
                            output_min=800, output_max=4500,
                            integral_limit=5000)
        pid.reset()
        for _ in range(100):
            time.sleep(0.001)
            pid.compute(current_temp=60, current_rpm=800)
        self.assertLessEqual(pid.integral, pid.integral_limit)

    def test_reset(self):
        pid = PIDController(kp=10, ki=1, kd=2, target_temp=50)
        pid.compute(current_temp=60, current_rpm=800)
        pid.reset()
        self.assertEqual(pid.integral, 0.0)
        self.assertEqual(pid.prev_error, 0.0)
        self.assertIsNone(pid.prev_time)

    def test_target_change(self):
        pid = PIDController(kp=10, ki=0, kd=0, target_temp=50,
                            output_min=800, output_max=4500)
        pid.reset()
        time.sleep(0.01)
        rpm_50 = pid.compute(current_temp=60, current_rpm=800)
        pid.set_target(70)
        pid.reset()
        time.sleep(0.01)
        rpm_70 = pid.compute(current_temp=60, current_rpm=800)
        self.assertLess(rpm_70, rpm_50)

    def test_tune(self):
        pid = PIDController(kp=10, ki=1, kd=2, target_temp=50)
        pid.tune(kp=20, ki=2, kd=4)
        self.assertEqual(pid.kp, 20)
        self.assertEqual(pid.ki, 2)
        self.assertEqual(pid.kd, 4)

    def test_zero_dt_handling(self):
        pid = PIDController(kp=10, ki=1, kd=2, target_temp=50)
        pid.prev_time = time.time()
        rpm = pid.compute(current_temp=60, current_rpm=800)
        self.assertIsInstance(rpm, int)


if __name__ == "__main__":
    unittest.main()
