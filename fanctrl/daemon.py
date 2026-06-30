import atexit
import os
import signal
import sys
import time

from fanctrl import SMC, CONFIG_PATH, PIDFILE_PATH
from fanctrl.sysfs import read_sysfs, write_sysfs
from fanctrl.sensors import get_all_temps
from fanctrl.fan import get_fan_info, auto as set_auto
from fanctrl.config import load_config, get_active_profile_config
from fanctrl.utils import require_root, write_pidfile, remove_pidfile, setup_logging
from fanctrl.non_smc import get_gpu_temps as get_non_smc_gpu_temps
from fanctrl.pid import PIDController


def interpolate(curve, temp):
    if not curve or len(curve) < 2:
        return 800
    curve = sorted(curve, key=lambda p: p[0])
    if temp <= curve[0][0]:
        return curve[0][1]
    if temp >= curve[-1][0]:
        return curve[-1][1]
    for i in range(len(curve) - 1):
        t1, r1 = curve[i]
        t2, r2 = curve[i + 1]
        if t1 <= temp <= t2:
            return int(r1 + (r2 - r1) * (temp - t1) / (t2 - t1))
    return curve[-1][1]


def safety_check(all_temps, max_safe=95):
    for temp in all_temps.values():
        if temp > max_safe:
            return True
    return False


def gpu_safety_check(all_temps, gpu_keys, max_gpu=90):
    for key in gpu_keys:
        temp = all_temps.get(key)
        if temp is not None and temp > max_gpu:
            return True
    return False


def get_sensor_fallback(all_temps, sensor_list):
    primary = [all_temps.get(s) for s in sensor_list if all_temps.get(s) is not None]
    if primary:
        return primary

    gpu_fallback = ["TeGG", "TeGP", "TeRG", "TeRP"]
    alt = [all_temps.get(k) for k in gpu_fallback if all_temps.get(k) is not None]
    if alt:
        return alt

    pci_fallback = ["TMA1", "TMA2", "TMTG"]
    alt2 = [all_temps.get(k) for k in pci_fallback if all_temps.get(k) is not None]
    if alt2:
        return alt2

    return []


def _cleanup_daemon():
    set_auto()
    remove_pidfile()


def _signal_handler(signum, frame):
    raise KeyboardInterrupt


def _apply_slew_rate(last_rpm, target, max_change):
    if max_change <= 0:
        return target
    if last_rpm is None:
        return target
    diff = target - last_rpm
    if abs(diff) > max_change:
        return last_rpm + (max_change if diff > 0 else -max_change)
    return target


def _build_pid_controllers(profile):
    controllers = {}
    for label, fconf in profile["fans"].items():
        pid_cfg = fconf.get("pid", {})
        curve = fconf.get("curve", [[0, 800], [70, 4500]])
        output_min = pid_cfg.get("output_min", curve[0][1] if curve else 800)
        output_max = pid_cfg.get("output_max", curve[-1][1] if curve else 4500)
        controllers[label] = PIDController(
            kp=pid_cfg.get("kp", 15),
            ki=pid_cfg.get("ki", 0.5),
            kd=pid_cfg.get("kd", 2.0),
            target_temp=pid_cfg.get("target_temp", 50),
            output_min=output_min,
            output_max=output_max,
        )
    return controllers


def cmd_daemon(debug=False):
    require_root()
    logger = setup_logging(background=False, debug=debug)
    full_config = load_config()
    config_mtime = os.path.getmtime(CONFIG_PATH)
    profile_name, profile = get_active_profile_config()
    interval = profile.get("interval", 5)

    atexit.register(_cleanup_daemon)
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    fan_map = {}
    for fi in get_fan_info():
        for label in profile["fans"]:
            if fi["label"] == label:
                fan_map[label] = fi["num"]
                break
    for label in profile["fans"]:
        fan_num = fan_map.get(label)
        if fan_num is not None:
            try:
                write_sysfs(f"{SMC}/fan{fan_num}_manual", "1")
            except OSError:
                pass

    logger.info(f"MacPro Fan Daemon avviato (profilo={profile_name}, interval={interval}s)")
    logger.info(f"Config: {CONFIG_PATH}")
    logger.info("Premi Ctrl+C per fermare.\n")

    safety_cfg = profile.get("safety", {})
    system_max_safe = safety_cfg.get("system_max_temp", 95)
    gpu_max_safe = safety_cfg.get("gpu_max_temp", 90)
    gpu_sensor_keys = safety_cfg.get("gpu_sensors", ["TeGG", "TeRG"])
    system_fallback = safety_cfg.get("system_fallback_rpm", "max")

    hysteresis_cfg = profile.get("hysteresis", {})
    hysteresis_enabled = hysteresis_cfg.get("enabled", True)
    hysteresis_deadband = hysteresis_cfg.get("deadband", 3)

    slew_cfg = profile.get("slew_rate", {})
    max_rpm_change = slew_cfg.get("max_rpm_change_per_cycle", 500)

    control_mode = profile.get("control_mode", "curve")
    pid_controllers = _build_pid_controllers(profile) if control_mode == "pid" else {}

    last_rpm = {}
    last_hysteresis_temp = {}

    try:
        while True:
            try:
                mtime = os.path.getmtime(CONFIG_PATH)
                if mtime != config_mtime:
                    full_config = load_config()
                    config_mtime = mtime
                    profile_name, profile = get_active_profile_config()
                    interval = profile.get("interval", 5)
                    safety_cfg = profile.get("safety", {})
                    system_max_safe = safety_cfg.get("system_max_temp", 95)
                    gpu_max_safe = safety_cfg.get("gpu_max_temp", 90)
                    gpu_sensor_keys = safety_cfg.get("gpu_sensors", ["TeGG", "TeRG"])
                    system_fallback = safety_cfg.get("system_fallback_rpm", "max")
                    hysteresis_cfg = profile.get("hysteresis", {})
                    hysteresis_enabled = hysteresis_cfg.get("enabled", True)
                    hysteresis_deadband = hysteresis_cfg.get("deadband", 3)
                    slew_cfg = profile.get("slew_rate", {})
                    max_rpm_change = slew_cfg.get("max_rpm_change_per_cycle", 500)
                    control_mode = profile.get("control_mode", "curve")
                    pid_controllers = _build_pid_controllers(profile) if control_mode == "pid" else {}
                    fan_map.clear()
                    for fi in get_fan_info():
                        for label in profile["fans"]:
                            if fi["label"] == label:
                                fan_map[label] = fi["num"]
                                break
                    logger.info(f"Config ricaricata (profilo={profile_name})")
            except OSError:
                pass

            all_temps = get_all_temps()

            non_smc_gpu = get_non_smc_gpu_temps()
            for label, temp in non_smc_gpu.items():
                all_temps[label] = temp

            safety_active = safety_check(all_temps, max_safe=system_max_safe)
            if safety_active:
                top = sorted(all_temps.items(), key=lambda x: x[1], reverse=True)[:5]
                logger.warning(f"SAFETY: temperature critiche! {', '.join(f'{k}={v}C' for k,v in top)}")

            gpu_safety_active = gpu_safety_check(all_temps, gpu_sensor_keys, max_gpu=gpu_max_safe)
            if gpu_safety_active:
                top = sorted(all_temps.items(), key=lambda x: x[1], reverse=True)[:5]
                logger.warning(f"SAFETY GPU: temperatura giunzione critica! {', '.join(f'{k}={v}C' for k,v in top)}")

            gpu_active = False
            gpu_temps = [all_temps.get(k) for k in gpu_sensor_keys if all_temps.get(k) is not None]
            if not gpu_temps:
                gpu_temps = [all_temps.get(k) for k in ["TeGG", "TeGP", "TeRG", "TeRP"] if all_temps.get(k) is not None]
            if gpu_temps and max(gpu_temps) > 45:
                gpu_active = True

            for label, fconf in profile["fans"].items():
                fan_num = fan_map.get(label)
                if fan_num is None:
                    continue

                sensor_temps = get_sensor_fallback(all_temps, fconf["sensors"])
                key = f"fan{fan_num}"

                if safety_active:
                    if system_fallback == "max":
                        target = interpolate(fconf["curve"], 9999)
                    else:
                        try:
                            target = int(system_fallback)
                        except (ValueError, TypeError):
                            target = interpolate(fconf["curve"], 9999)
                    target = _apply_slew_rate(last_rpm.get(key), target, max_rpm_change)
                    if last_rpm.get(key) != target:
                        try:
                            write_sysfs(f"{SMC}/fan{fan_num}_manual", "1")
                            write_sysfs(f"{SMC}/fan{fan_num}_output", str(target))
                            actual = read_sysfs(f"{SMC}/fan{fan_num}_input")
                            logger.info(f"{label} [SAFETY] -> {target} RPM [{actual}]")
                            last_rpm[key] = target
                        except OSError as e:
                            logger.error(f"Errore scrittura {label}: {e}")
                    continue

                if not sensor_temps:
                    target = interpolate(fconf["curve"], 0)
                    target = _apply_slew_rate(last_rpm.get(key), target, max_rpm_change)
                    if last_rpm.get(key) != target:
                        try:
                            write_sysfs(f"{SMC}/fan{fan_num}_manual", "1")
                            write_sysfs(f"{SMC}/fan{fan_num}_output", str(target))
                            actual = read_sysfs(f"{SMC}/fan{fan_num}_input")
                            logger.info(f"{label} [fallback] -> {target} RPM [{actual}] (no sensors)")
                            last_rpm[key] = target
                        except OSError as e:
                            logger.error(f"Errore scrittura {label}: {e}")
                    continue

                max_temp = max(sensor_temps)

                if control_mode == "pid":
                    controller = pid_controllers.get(label)
                    if controller:
                        raw_target = controller.compute(max_temp, current_rpm=last_rpm.get(key))
                        curve = fconf.get("curve", [[0, 800], [70, 4500]])
                        pid_cfg = fconf.get("pid", {})
                        out_min = pid_cfg.get("output_min", curve[0][1])
                        out_max = pid_cfg.get("output_max", curve[-1][1])
                        target = max(out_min, min(out_max, raw_target))
                    else:
                        target = interpolate(fconf["curve"], max_temp)
                else:
                    if hysteresis_enabled:
                        prev_temp = last_hysteresis_temp.get(key)
                        if prev_temp is not None and abs(max_temp - prev_temp) < hysteresis_deadband:
                            pass
                        else:
                            last_hysteresis_temp[key] = max_temp
                            target = interpolate(fconf["curve"], max_temp)
                    else:
                        target = interpolate(fconf["curve"], max_temp)

                if gpu_active and label == "PCI":
                    min_rpm = fconf["curve"][0][1]
                    adjusted_min = int(min_rpm * 1.15)
                    current_target = interpolate(fconf["curve"], max_temp)
                    target = max(target, adjusted_min)

                target = _apply_slew_rate(last_rpm.get(key), target, max_rpm_change)

                if last_rpm.get(key) != target:
                    try:
                        write_sysfs(f"{SMC}/fan{fan_num}_manual", "1")
                        write_sysfs(f"{SMC}/fan{fan_num}_output", str(target))
                        actual = read_sysfs(f"{SMC}/fan{fan_num}_input")
                        logger.info(f"{label} ({max_temp}C) -> {target} RPM [{actual}]")
                        last_rpm[key] = target
                    except OSError as e:
                        logger.error(f"Errore scrittura {label}: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Daemon fermato.")
        _cleanup_daemon()


def cmd_daemon_bg():
    pid = os.fork()
    if pid > 0:
        print(f"Daemon avviato in background (PID {pid})")
        sys.exit(0)
    os.setsid()
    pid = os.fork()
    if pid > 0:
        sys.exit(0)
    setup_logging(background=True)
    write_pidfile()
    cmd_daemon()
