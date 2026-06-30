import time


class PIDController:
    def __init__(self, kp, ki, kd, target_temp,
                 output_min=800, output_max=4500,
                 integral_limit=None):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.target = target_temp
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit or (output_max - output_min)

        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = None

    def compute(self, current_temp, current_rpm=None):
        now = time.time()
        dt = (now - self.prev_time) if self.prev_time is not None else 0.1
        if dt <= 0:
            dt = 0.1

        error = current_temp - self.target

        self.integral += error * dt
        if self.integral > self.integral_limit:
            self.integral = self.integral_limit
        elif self.integral < -self.integral_limit:
            self.integral = -self.integral_limit

        derivative = (error - self.prev_error) / dt if dt > 0 else 0.0

        output = self.kp * error + self.ki * self.integral + self.kd * derivative

        if current_rpm is not None:
            rpm = int(current_rpm + output)
        else:
            rpm = int(self.output_min + output)

        rpm = max(self.output_min, min(self.output_max, rpm))

        self.prev_error = error
        self.prev_time = now

        return rpm

    def reset(self):
        self.integral = 0.0
        self.prev_error = 0.0
        self.prev_time = None

    def set_target(self, target_temp):
        self.target = target_temp

    def tune(self, kp=None, ki=None, kd=None):
        if kp is not None:
            self.kp = kp
        if ki is not None:
            self.ki = ki
        if kd is not None:
            self.kd = kd
