"""
`fanctrl/sensors.py` — Rilevamento e raggruppamento dei sensori di temperatura.

Definisce il database delle etichette (TEMP_LABELS) e dei gruppi (TEMP_GROUPS)
per tutti i sensori noti del Mac Pro 5,1. Fornisce funzioni per:
  - Scansionare i sensori disponibili via sysfs (get_all_temps)
  - Raggruppare le temperature per componente (CPU, GPU, MCP, HDD, PWR)
  - Visualizzare i sensori a terminale (show_temps)
"""

import os

from fanctrl import SMC
from fanctrl.sysfs import read_sysfs, read_temp


TEMP_LABELS = {
    "TA0P": "Ambient",
    "TCAC": "CPU A Core",
    "TCAD": "CPU A Diode",
    "TCAG": "CPU A Heatsink",
    "TCAH": "CPU A HSD",
    "TCAS": "CPU A PECI",
    "TCBC": "CPU B Core",
    "TCBD": "CPU B Diode",
    "TCBG": "CPU B Heatsink",
    "TCBH": "CPU B HSD",
    "TCBS": "CPU B PECI",
    "TM0P": "Mem Riser A",
    "TM1P": "Mem DIMM A1",
    "TM2P": "Mem DIMM A2",
    "TM3P": "Mem DIMM B1",
    "TM4P": "Mem DIMM B2",
    "TM5P": "Mem DIMM C1",
    "TM6P": "Mem DIMM C2",
    "TM7P": "Mem DIMM D1",
    "TM8P": "Mem DIMM D2",
    "TMPS": "Mem Proximity",
    "TMPV": "Mem P5V",
    "TH1P": "HDD Bay 1",
    "TH2P": "HDD Bay 2",
    "TH3P": "HDD Bay 3",
    "TH4P": "HDD Bay 4",
    "THPS": "HDD Proximity",
    "THTG": "HDD Thermal G",
    "TN0D": "MCP Diode",
    "TN0H": "MCP Heatsink",
    "TNTG": "MCP Thermal G",
    "Tp0C": "PWR Supply 1",
    "Tp1C": "PWR Supply 2",
    "TpPS": "PWR Proximity",
    "TpTG": "PWR Thermal G",
    "TMA1": "PCIe Slot 1",
    "TMA2": "PCIe Slot 2",
    "TMA3": "PCIe Slot 3",
    "TMA4": "PCIe Slot 4",
    "TMB1": "PCIe Slot 5",
    "TMB2": "PCIe Slot 6",
    "TMB3": "PCIe Slot 7",
    "TMB4": "PCIe Slot 8",
    "TMTG": "PCIe Thermal G",
    "TMHS": "PCIe MCP HS",
    "TMLS": "PCIe P5V",
    "Te1P": "GPU 1 Proximity",
    "Te1F": "GPU 1 Flow",
    "Te1S": "GPU 1 Status",
    "Te2P": "GPU 2 Proximity",
    "Te2F": "GPU 2 Flow",
    "Te2S": "GPU 2 Status",
    "Te3P": "GPU 3 Proximity",
    "Te3F": "GPU 3 Flow",
    "Te3S": "GPU 3 Status",
    "Te4P": "GPU 4 Proximity",
    "Te4F": "GPU 4 Flow",
    "Te4S": "GPU 4 Status",
    "Te5P": "GPU 5 Proximity",
    "Te5F": "GPU 5 Flow",
    "Te5S": "GPU 5 Status",
    "TeGG": "GPU 1 Heatsink",
    "TeGP": "GPU Proximity Global",
    "TeRG": "GPU 2 Heatsink",
    "TeRP": "GPU Proximity Global 2",
    "TH1F": "HDD Bay 1 Flow",
    "TH2F": "HDD Bay 2 Flow",
    "TH3F": "HDD Bay 3 Flow",
    "TH4F": "HDD Bay 4 Flow",
}

TEMP_GROUPS = {
    "CPU": ["TCAC", "TCAD", "TCAG", "TCBC", "TCBD", "TCBG"],
    "GPU": ["TeGG", "TeRG", "TeGP", "TeRP", "Te1P", "Te1F", "Te1S", "Te2P", "Te2F", "Te2S", "Te3P", "Te3F", "Te3S", "Te4P", "Te4F", "Te4S", "Te5P", "Te5F", "Te5S"],
    "MCP": ["TN0D", "TN0H", "TNTG"],
    "HDD": ["TH1P", "TH2P", "TH3P", "TH4P", "TH1V", "TH2V", "TH3V", "TH4V"],
    "PWR": ["Tp0C", "Tp1C", "TpPS"],
    "MEM": ["TM0P", "TM1P", "TM2P", "TM3P", "TM4P", "TM5P", "TM6P", "TM7P", "TM8P", "TMPS", "TMPV"],
    "PCIe": ["TMA1", "TMA2", "TMA3", "TMA4", "TMB1", "TMB2", "TMB3", "TMB4", "TMTG", "TMHS", "TMLS"],
}

GPU_SENSOR_KEYS = {
    "TeGG": "GPU Heatsink 1",
    "TeGP": "GPU Proximity Global",
    "TeRG": "GPU Heatsink 2",
    "TeRP": "GPU Proximity Global 2",
    "Te1P": "GPU 1 Proximity",
    "Te1F": "GPU 1 Flow",
    "Te1S": "GPU 1 Status",
    "Te2P": "GPU 2 Proximity",
    "Te2F": "GPU 2 Flow",
    "Te2S": "GPU 2 Status",
    "Te3P": "GPU 3 Proximity",
    "Te3F": "GPU 3 Flow",
    "Te3S": "GPU 3 Status",
    "Te4P": "GPU 4 Proximity",
    "Te4F": "GPU 4 Flow",
    "Te4S": "GPU 4 Status",
    "Te5P": "GPU 5 Proximity",
    "Te5F": "GPU 5 Flow",
    "Te5S": "GPU 5 Status",
}

# Cache sensori disponibili (popolata al primo accesso)
_available_sensor_keys = None


def _scan_available_sensors():
    """
    Scansiona sysfs per identificare i sensori di temperatura disponibili.
    Risultato cached per evitare scansione ripetuta.

    Returns:
        set[str]: Set delle chiave sensore (es. "TCAC", "TA0P") disponibili.
    """
    global _available_sensor_keys
    if _available_sensor_keys is not None:
        return _available_sensor_keys
    _available_sensor_keys = set()
    try:
        for f in sorted(os.listdir(SMC)):
            if not f.endswith("_label") or not f.startswith("temp"):
                continue
            label = read_sysfs(f"{SMC}/{f}")
            if label:
                _available_sensor_keys.add(label)
    except OSError:
        pass
    return _available_sensor_keys


def get_all_temps():
    """
    Scansiona tutti i sensori di temperatura disponibili in sysfs.

    Usa la cache _scan_available_sensors() per identificare rapidamente
    i sensori presenti, poi legge le temperature corrispondenti.

    Returns:
        dict: Mappa {chiave_sensore: temperatura_C} per tutti i sensori
              attualmente leggibili. I sensori non presenti o illeggibili
              vengono omessi.
    """
    sensors = {}
    available = _scan_available_sensors()
    for f in sorted(os.listdir(SMC)):
        if not f.endswith("_label") or not f.startswith("temp"):
            continue
        label = read_sysfs(f"{SMC}/{f}")
        if not label:
            continue
        base = f.replace("_label", "")
        t = read_temp(base)
        if t is not None:
            sensors[label] = t
    return sensors


def get_available_sensor_keys():
    """
    Restituisce il set delle chiave sensore disponibili (cached).

    Utile per verificare quali sensori sono leggibili senza leggere
    le temperature.

    Returns:
        set[str]: Set delle chiave sensore disponibili.
    """
    return _scan_available_sensors()


def get_sensor_debug_info():
    """
    Restituisce informazioni debug sui sensori: disponibili vs mappati.

    Utile per troubleshooting quando alcuni sensori non appaiono.

    Returns:
        dict: {
            "available": set delle chiave sensore trovate in sysfs,
            "mapped": TEMP_LABELS keys,
            "missing_from_labels": sensors found but not in TEMP_LABELS,
            "unmapped_in_sysfs": labels read that aren't in TEMP_GROUPS
        }
    """
    available = _scan_available_sensors()
    missing_from_labels = available - set(TEMP_LABELS.keys())
    return {
        "available_count": len(available),
        "mapped_count": len(set(TEMP_LABELS.keys())),
        "missing_from_labels": sorted(missing_from_labels),
    }


def group_temps(all_temps, include_unmapped=False):
    """
    Raggruppa le temperature per componente hardware.

    Per ogni gruppo definito in TEMP_GROUPS calcola la temperatura
    massima tra i suoi sensori. Aggiunge anche la temperatura ambiente (TA0P).
    Utile per sintetizzare lo stato termico del sistema in poche cifre.

    Args:
        all_temps (dict): Mappa {chiave: temperatura_C} da get_all_temps().

    Returns:
        dict: Mappa {nome_gruppo: temperatura_massima_C} con chiavi
              "CPU", "GPU", "MCP", "HDD", "PWR", "AMB" (se disponibile).
    """
    result = {}
    for group, keys in TEMP_GROUPS.items():
        vals = [all_temps.get(k) for k in keys if all_temps.get(k) is not None]
        if vals:
            result[group] = max(vals)
    ambient = all_temps.get("TA0P")
    if ambient is not None:
        result["AMB"] = ambient

    # Opzionale: gruppi per sensori non mappati in TEMP_GROUPS
    if include_unmapped:
        mapped_keys = set()
        for keys in TEMP_GROUPS.values():
            mapped_keys.update(keys)
        unmapped_temps = {k: v for k, v in all_temps.items() if k not in mapped_keys and k != "TA0P"}
        if unmapped_temps:
            result["UNMAPPED"] = max(unmapped_temps.values())
            result["UNMAPPED_detail"] = unmapped_temps

    return result
