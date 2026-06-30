import os
import re

HWMON_PATH = "/sys/class/hwmon"


def _read_sysfs(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def _list_hwmon_devices():
    if not os.path.isdir(HWMON_PATH):
        return []
    try:
        return sorted(os.listdir(HWMON_PATH))
    except OSError:
        return []


def _get_driver_name(hwmon):
    name = _read_sysfs(f"{HWMON_PATH}/{hwmon}/name")
    return name if name else ""


def _read_temp_input(path):
    raw = _read_sysfs(path)
    if raw is None:
        return None
    try:
        millic = int(raw)
    except (ValueError, TypeError):
        return None
    if abs(millic) > 90000:
        return None
    return round(millic / 1000, 1)


def _read_int(path):
    raw = _read_sysfs(path)
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def _read_float(path, divisor=1):
    raw = _read_sysfs(path)
    if raw is None:
        return None
    try:
        return int(raw) / divisor
    except (ValueError, TypeError):
        return None


def _scan_coretemp(hwmon):
    base = f"{HWMON_PATH}/{hwmon}"
    cores = {}
    temp_inputs = {}
    temp_labels = {}

    for f in os.listdir(base):
        m = re.match(r"temp(\d+)_input$", f)
        if m:
            idx = m.group(1)
            t = _read_temp_input(f"{base}/{f}")
            if t is not None:
                temp_inputs[idx] = t

        m = re.match(r"temp(\d+)_label$", f)
        if m:
            idx = m.group(1)
            label = _read_sysfs(f"{base}/{f}")
            if label:
                temp_labels[idx] = label

    for idx in temp_inputs:
        label = temp_labels.get(idx, f"Core {idx}")
        cores[label] = temp_inputs[idx]

    return cores


def _scan_amdgpu(hwmon):
    base = f"{HWMON_PATH}/{hwmon}"
    result = {
        "fan_rpm": _read_int(f"{base}/fan1_input"),
        "pwm": _read_int(f"{base}/pwm1"),
        "pwm_enable": _read_int(f"{base}/pwm1_enable"),
        "fan_max": _read_int(f"{base}/fan1_max"),
        "fan_min": _read_int(f"{base}/fan1_min"),
        "temps": {},
        "power_w": _read_float(f"{base}/power1_input", 1_000_000),
        "voltage_mv": _read_float(f"{base}/in0_input", 1),
        "sclk_mhz": _read_float(f"{base}/freq1_input", 1_000_000),
        "mclk_mhz": _read_float(f"{base}/freq2_input", 1_000_000),
    }

    temp_labels = {}
    for f in os.listdir(base):
        m = re.match(r"temp(\d+)_label$", f)
        if m:
            idx = m.group(1)
            label = _read_sysfs(f"{base}/{f}")
            if label:
                temp_labels[idx] = label

    for f in os.listdir(base):
        m = re.match(r"temp(\d+)_input$", f)
        if m:
            idx = m.group(1)
            t = _read_temp_input(f"{base}/{f}")
            if t is not None:
                label = temp_labels.get(idx, f"sensor{idx}")
                result["temps"][label] = t

    return result


def _scan_nvme(hwmon):
    base = f"{HWMON_PATH}/{hwmon}"
    result = {"device": None, "temps": {}}

    for f in os.listdir(base):
        m = re.match(r"temp(\d+)_input$", f)
        if m:
            idx = m.group(1)
            t = _read_temp_input(f"{base}/{f}")
            if t is not None:
                label_path = f"{base}/temp{idx}_label"
                label = _read_sysfs(label_path) or f"Sensor {idx}"
                result["temps"][label] = t

    device_path = f"{base}/device/device"
    if os.path.exists(device_path):
        result["device"] = _read_sysfs(device_path)

    return result


def get_non_smc_temps():
    devices = {}
    for hwmon in _list_hwmon_devices():
        driver = _get_driver_name(hwmon)
        if driver == "coretemp":
            devices["cpu_core"] = _scan_coretemp(hwmon)
        elif driver == "amdgpu":
            devices["gpu"] = _scan_amdgpu(hwmon)
        elif driver == "nvme":
            devices.setdefault("nvme", []).append(_scan_nvme(hwmon))

    return devices


def get_gpu_temps():
    devices = get_non_smc_temps()
    gpu = devices.get("gpu", {})
    return gpu.get("temps", {})


def get_gpu_info():
    devices = get_non_smc_temps()
    gpu = devices.get("gpu", {})
    if not gpu:
        return None
    return {
        "fan_rpm": gpu.get("fan_rpm"),
        "pwm": gpu.get("pwm"),
        "pwm_enable": gpu.get("pwm_enable"),
        "fan_max": gpu.get("fan_max"),
        "fan_min": gpu.get("fan_min"),
        "temps": gpu.get("temps", {}),
        "power_w": gpu.get("power_w"),
        "voltage_mv": gpu.get("voltage_mv"),
        "sclk_mhz": gpu.get("sclk_mhz"),
        "mclk_mhz": gpu.get("mclk_mhz"),
    }


def get_cpu_core_temps():
    devices = get_non_smc_temps()
    cpu = devices.get("cpu_core", {})
    if not cpu:
        return {}
    return dict(cpu)


def get_nvme_temps():
    devices = get_non_smc_temps()
    nvme_list = devices.get("nvme", [])
    result = {}
    for i, nvme in enumerate(nvme_list):
        label = nvme.get("device") or f"NVMe #{i+1}"
        result[label] = nvme.get("temps", {})
    return result
