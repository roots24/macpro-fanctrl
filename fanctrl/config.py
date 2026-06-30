import json
import os
import shutil

from fanctrl import CONFIG_DIR, CONFIG_PATH

DEFAULT_SAFETY = {
    "system_max_temp": 95,
    "system_fallback_rpm": "max",
    "gpu_sensors": ["TeGG", "TeRG"],
    "gpu_max_temp": 90,
}

DEFAULT_HYSTERESIS = {
    "enabled": True,
    "deadband": 3,
}

DEFAULT_SLEW_RATE = {
    "max_rpm_change_per_cycle": 500,
}

DEFAULT_PID = {
    "target_temp": 50,
    "kp": 15,
    "ki": 0.5,
    "kd": 2.0,
    "output_min": 800,
    "output_max": 4500,
}


def validate_profile(profile):
    fans = profile.get("fans", {})
    if not fans:
        return False, "profilo senza ventole"
    for fan_label, fconf in fans.items():
        curve = fconf.get("curve", [])
        if len(curve) < 2:
            return False, f"{fan_label}: curva deve avere >=2 punti [temp, rpm]"
        prev_t = -1
        for pt in curve:
            if not isinstance(pt, (list, tuple)) or len(pt) != 2:
                return False, f"{fan_label}: punto curva invalido {pt}"
            t, r = pt[0], pt[1]
            if t < prev_t:
                return False, f"{fan_label}: punti curva non ordinati ({prev_t}C -> {t}C)"
            if r < 0:
                return False, f"{fan_label}: RPM negativo in punto {pt}"
            prev_t = t

    safety = profile.get("safety", {})
    if safety:
        if not isinstance(safety, dict):
            return False, "safety deve essere un dizionario"
        if "system_max_temp" in safety and not isinstance(safety["system_max_temp"], (int, float)):
            return False, "system_max_temp deve essere numerico"

    return True, "OK"


DEFAULT_PROFILES = {
    "silent": {
        "interval": 5,
        "control_mode": "curve",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": dict(DEFAULT_HYSTERESIS),
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD"],
                "curve": [[0, 800], [35, 1200], [45, 1600], [55, 2500], [65, 4500]]
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 800], [35, 1200], [50, 1800], [65, 3000], [75, 4500]]
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 800], [30, 1000], [40, 1400], [50, 2200], [60, 2800]]
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 800], [30, 1000], [40, 1400], [50, 2200], [60, 2800]]
            }
        }
    },
    "quiet_daily": {
        "interval": 5,
        "control_mode": "curve",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": dict(DEFAULT_HYSTERESIS),
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD"],
                "curve": [[0, 800], [35, 1200], [45, 2000], [55, 3000], [65, 4500]]
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 800], [35, 1200], [50, 2000], [65, 3500], [75, 4500]]
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 1000], [30, 1000], [40, 1500], [50, 2500], [60, 2800]]
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 1000], [30, 1000], [40, 1500], [50, 2500], [60, 2800]]
            }
        }
    },
    "heavy_work": {
        "interval": 3,
        "control_mode": "curve",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": dict(DEFAULT_HYSTERESIS),
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD"],
                "curve": [[0, 2000], [35, 2000], [45, 2800], [55, 3500], [65, 4500]]
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 1500], [35, 1500], [50, 2500], [65, 4000], [75, 4500]]
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 2000], [30, 2000], [40, 2500], [50, 3500], [60, 2800]]
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 2000], [30, 2000], [40, 2500], [50, 3500], [60, 2800]]
            }
        }
    },
    "quiet_daily_dual": {
        "interval": 5,
        "control_mode": "curve",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": dict(DEFAULT_HYSTERESIS),
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD", "TCBC", "TCBD"],
                "curve": [[0, 1200], [35, 1500], [45, 2500], [55, 3500], [65, 5200]]
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 1000], [35, 1400], [50, 2200], [65, 3500], [75, 4500]]
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 1200], [30, 1400], [40, 1800], [50, 2500], [60, 2800]]
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 1200], [30, 1400], [40, 1800], [50, 2500], [60, 2800]]
            }
        }
    },
    "heavy_work_dual": {
        "interval": 3,
        "control_mode": "curve",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": dict(DEFAULT_HYSTERESIS),
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD", "TCBC", "TCBD"],
                "curve": [[0, 2200], [35, 2500], [45, 3200], [55, 4000], [65, 5200]]
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 1800], [35, 2000], [50, 2800], [65, 4200], [75, 4500]]
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 2200], [30, 2400], [40, 2800], [50, 3500], [60, 4500]]
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 2200], [30, 2400], [40, 2800], [50, 3500], [60, 4500]]
            }
        }
    },
    "render_mode_dual": {
        "interval": 2,
        "control_mode": "curve",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": dict(DEFAULT_HYSTERESIS),
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD", "TCBC", "TCBD"],
                "curve": [[0, 3200], [35, 3500], [45, 4200], [55, 4800], [65, 5200]]
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 2800], [35, 3000], [50, 3800], [60, 4500], [75, 4500]]
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 3200], [30, 3400], [40, 4000], [50, 4500], [60, 4500]]
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 3200], [30, 3400], [40, 4000], [50, 4500], [60, 4500]]
            }
        }
    },
    "pid_quiet": {
        "interval": 3,
        "control_mode": "pid",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": {"enabled": False, "deadband": 0},
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD"],
                "curve": [[0, 800], [65, 4500]],
                "pid": {"target_temp": 55, "kp": 20, "ki": 0.8, "kd": 3.0, "output_min": 800, "output_max": 4500}
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 800], [75, 4500]],
                "pid": {"target_temp": 55, "kp": 18, "ki": 0.6, "kd": 2.5, "output_min": 800, "output_max": 4500}
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 800], [60, 2800]],
                "pid": {"target_temp": 50, "kp": 15, "ki": 0.5, "kd": 2.0, "output_min": 800, "output_max": 2800}
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 800], [60, 2800]],
                "pid": {"target_temp": 50, "kp": 15, "ki": 0.5, "kd": 2.0, "output_min": 800, "output_max": 2800}
            }
        }
    },
    "render_mode": {
        "interval": 2,
        "control_mode": "curve",
        "safety": dict(DEFAULT_SAFETY),
        "hysteresis": dict(DEFAULT_HYSTERESIS),
        "slew_rate": dict(DEFAULT_SLEW_RATE),
        "fans": {
            "BOOST": {
                "sensors": ["TCAC", "TCAD"],
                "curve": [[0, 3000], [35, 3000], [45, 3800], [55, 4200], [65, 4500]]
            },
            "PCI": {
                "sensors": ["TMA1", "TMA2", "TMTG", "edge", "junction", "mem"],
                "curve": [[0, 2500], [35, 2500], [50, 3500], [60, 4200], [75, 4500]]
            },
            "EXHAUST": {
                "sensors": ["Tp0C", "Tp1C", "TpPS"],
                "curve": [[0, 3000], [30, 3000], [40, 3800], [50, 4200], [60, 2800]]
            },
            "INTAKE": {
                "sensors": ["TCAG", "TCBG", "TN0D"],
                "curve": [[0, 3000], [30, 3000], [40, 3800], [50, 4200], [60, 2800]]
            }
        }
    }
}


def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def load_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        config = {
            "active_profile": "quiet_daily",
            "profiles": DEFAULT_PROFILES
        }
        save_config(config)
        print(f"Config creata: {CONFIG_PATH}")
        return config

    shutil.copy2(CONFIG_PATH, CONFIG_PATH + ".bak")

    with open(CONFIG_PATH) as f:
        config = json.load(f)

    if "profiles" not in config:
        print("Migrazione al formato profili in corso...")
        old_fans = config.get("fans", {})
        old_interval = config.get("interval", 5)
        profiles = {}
        for name in ["quiet_daily", "heavy_work", "render_mode", "silent"]:
            base = dict(DEFAULT_PROFILES[name])
            if name == "quiet_daily":
                base["interval"] = old_interval
                base["fans"] = old_fans if old_fans else base["fans"]
            profiles[name] = base
        config = {
            "active_profile": "quiet_daily",
            "profiles": profiles,
        }
        save_config(config)
        print("Migrazione completata.")

    for name, profile in config.get("profiles", {}).items():
        profile.setdefault("safety", dict(DEFAULT_SAFETY))
        profile.setdefault("hysteresis", dict(DEFAULT_HYSTERESIS))
        profile.setdefault("slew_rate", dict(DEFAULT_SLEW_RATE))
        profile.setdefault("control_mode", "curve")
        for fconf in profile.get("fans", {}).values():
            fconf.setdefault("pid", dict(DEFAULT_PID))

        valid, msg = validate_profile(profile)
        if not valid:
            print(f"AVVISO: profilo '{name}' invalido ({msg}) — uso default")
            config["profiles"][name] = dict(DEFAULT_PROFILES.get(name, DEFAULT_PROFILES["quiet_daily"]))

    return config


def list_profiles():
    config = load_config()
    return list(config.get("profiles", {}).keys())


def get_active_profile():
    config = load_config()
    return config.get("active_profile", "quiet_daily")


def get_active_profile_config():
    config = load_config()
    name = config.get("active_profile", "quiet_daily")
    profile = config["profiles"].get(name)
    if profile is None:
        name = "quiet_daily"
        profile = config["profiles"].get(name, DEFAULT_PROFILES["quiet_daily"])
    return name, profile


def switch_profile(name):
    if not name:
        print("ERRORE: Nome profilo vuoto")
        return False
    config = load_config()
    profiles = config.get("profiles", {})
    if name not in profiles:
        print(f"ERRORE: Profilo '{name}' non trovato. Disponibili: {', '.join(profiles.keys())}")
        return False
    valid, msg = validate_profile(profiles[name])
    if not valid:
        print(f"AVVISO: profilo '{name}' invalido ({msg})")
    config["active_profile"] = name
    save_config(config)
    print(f"Profilo attivo: {name}")
    return True


def export_profile(name, output_path):
    config = load_config()
    profiles = config.get("profiles", {})
    if name not in profiles:
        print(f"ERRORE: Profilo '{name}' non trovato.")
        return False
    profile_data = {"profile": name, "data": profiles[name]}
    with open(output_path, "w") as f:
        json.dump(profile_data, f, indent=2)
    print(f"Profilo '{name}' esportato in {output_path}")
    return True


def import_profile(input_path):
    if not os.path.exists(input_path):
        print(f"ERRORE: File '{input_path}' non trovato.")
        return False
    with open(input_path) as f:
        data = json.load(f)
    profile_name = data.get("profile", "custom")
    profile_data = data.get("data", {})
    if not profile_name or not profile_data:
        print("ERRORE: file JSON formato invalido (serve 'profile' + 'data')")
        return False
    valid, msg = validate_profile(profile_data)
    if not valid:
        print(f"ERRORE: profilo invalido ({msg})")
        return False
    config = load_config()
    config["profiles"][profile_name] = profile_data
    save_config(config)
    print(f"Profilo '{profile_name}' importato e aggiunto alla config.")
    return True
