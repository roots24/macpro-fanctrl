"""
`fanctrl/display.py` — Output formattato per terminale.

Fornisce funzioni per la visualizzazione a terminale delle informazioni
sulle ventole (show_fans) e sui sensori di temperatura (show_temps).
"""

import os
import subprocess
import time

from fanctrl import SMC
from fanctrl.sysfs import read_sysfs, read_temp
from fanctrl.sensors import TEMP_LABELS
from fanctrl.fan import get_fan_info
from fanctrl.config import get_active_profile


def show_fans():
    """
    Stampa a terminale una tabella riassuntiva di tutte le ventole.

    Colonne: VENTOLA (label), RPM (corrente), MIN, MAX, MANUALE (1/0).
    """
    profile = get_active_profile()
    print(f"Profilo attivo: {profile}")
    print(f"{'VENTOLA':<10} {'RPM':>7} {'MIN':>7} {'MAX':>7} {'MANUALE':>7}")
    print("-" * 42)
    for f in get_fan_info():
        print(
            f"{f['label']:<10} {f['rpm']:>7} {f['min']:>7} "
            f"{f['max']:>7} {f['manual']:>7}"
        )


def show_temps():
    """
    Stampa a terminale tutti i sensori di temperatura raggruppati
    per componente (CPU, Memoria, HDD, PCIe/GPU, Northbridge, Altro).

    Ogni sensore viene visualizzato con barra ASCII proporzionale
    alla temperatura (ogni 5°C un blocco '█', max 20 blocchi).
    """
    sensors = []
    for f in sorted(os.listdir(SMC)):
        if not f.endswith("_label") or not f.startswith("temp"):
            continue
        label = read_sysfs(f"{SMC}/{f}")
        if not label:
            continue
        base = f.replace("_label", "")
        t = read_temp(base)
        desc = TEMP_LABELS.get(label, label)
        if t is not None:
            sensors.append((desc, label, t))

    if not sensors:
        return

    cpu_sensors = [s for s in sensors if s[0].startswith("CPU")]
    gpu_sensors = [s for s in sensors if s[0].startswith(("GPU", "Te"))]
    mem_sensors = [s for s in sensors if s[0].startswith("Mem")]
    pcie_sensors = [s for s in sensors if s[0].startswith("PCIe")]
    hdd_sensors = [s for s in sensors if s[0].startswith("HDD")]
    nb_sensors = [s for s in sensors if s[0].startswith("MCP")]
    pwr_sensors = [s for s in sensors if s[0].startswith("PWR")]
    other_sensors = [
        s for s in sensors
        if s not in cpu_sensors + gpu_sensors + mem_sensors + pcie_sensors + hdd_sensors + nb_sensors + pwr_sensors
    ]

    def print_group(title, items):
        if not items:
            return
        print(f"\n  {title}:")
        for desc, key, t in items:
            bar = "█" * min(t // 5, 20)
            print(f"    {key:<6} {t:>3}°C  {bar}  {desc}")

    print(f"\n{'═' * 42}")
    print("  SENSORI TEMPERATURA")
    print(f"{'═' * 42}")
    print_group("CPU", cpu_sensors)
    print_group("GPU (Radeon VII)", gpu_sensors)
    print_group("Memoria", mem_sensors)
    print_group("PCIe", pcie_sensors)
    print_group("HDD", hdd_sensors)
    print_group("Northbridge", nb_sensors)
    print_group("Alimentazione", pwr_sensors)
    print_group("Altro", other_sensors)
    print()


def cmd_monitor():
    """
    Monitoraggio continuo: mostra ventole e temperature ogni 5 secondi.
    Termina con Ctrl+C.
    """
    try:
        while True:
            if os.name == "posix":
                subprocess.run(["clear"], check=False)
            else:
                subprocess.run(["cls"], check=False)
            show_fans()
            show_temps()
            time.sleep(5)
    except KeyboardInterrupt:
        print("\nMonitoraggio terminato.")
