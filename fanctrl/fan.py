"""
`fanctrl/fan.py` — Operazioni di lettura e controllo delle ventole.

Fornisce funzioni per:
  - Rilevare dinamicamente il numero di ventole presenti (get_fan_count)
  - Leggere lo stato di tutte le ventole (get_fan_info)
  - Impostare una ventola singola o tutte le ventole a un dato RPM
  - Ripristinare il controllo automatico hardware (auto)

Il numero di ventole non è hardcodato ma rilevato dinamicamente
scansionando i file sysfs, supportando così configurazioni con
numero variabile di ventole (4, 5, 6 a seconda del modello).
"""

import os
import time

from fanctrl import SMC
from fanctrl.sysfs import read_sysfs, write_sysfs

class FanError(ValueError):
    pass

# Debounce: intervallo minimo tra writes consecutive sulla stessa ventola (secondi)
_FAN_DEBOUNCE_INTERVAL = 0.15
# Cache ultimi write times per ventola
_fan_last_write = {}


def get_fan_count():
    """
    Conta le ventole presenti nel sistema.

    Scansiona /sys/devices/platform/applesmc.768/ alla ricerca di
    file con pattern fan{1..N}_label.

    Returns:
        int: Numero di ventole rilevate (0 se nessuna).
    """
    count = 0
    for f in os.listdir(SMC):
        if f.startswith("fan") and f.endswith("_label"):
            count += 1
    return count


def get_fan_info():
    """
    Recupera le informazioni di tutte le ventole presenti.

    Returns:
        list[dict]: Lista ordinata di dizionari, uno per ventola:
            - num (int): Numero progressivo (1..N)
            - label (str): Etichetta hardware (es. "PCI", "EXHAUST")
            - rpm (int): RPM misurati correnti
            - min (int): RPM minimo ammesso dall'hardware
            - max (int): RPM massimo ammesso dall'hardware
            - manual (int): 1 se in override manuale, 0 se automatico

        Le ventole che generano errori di lettura vengono escluse.
    """
    fans = []
    for i in range(1, get_fan_count() + 1):
        try:
            fans.append({
                "num": i,
                "label": read_sysfs(f"{SMC}/fan{i}_label"),
                "rpm": int(read_sysfs(f"{SMC}/fan{i}_input")),
                "min": int(read_sysfs(f"{SMC}/fan{i}_min")),
                "max": int(read_sysfs(f"{SMC}/fan{i}_max")),
                "manual": int(read_sysfs(f"{SMC}/fan{i}_manual")),
            })
        except (FileNotFoundError, ValueError, OSError):
            continue
    return fans


def set_fan(fan, rpm):
    """
    Imposta manualmente la velocità di una ventola.

    Attiva la modalità manuale (fan_manual=1) e scrive l'RPM richiesto.
    Prima verifica che l'RPM sia nel range [min, max] della ventola.
    Applica debounce per evitare writes consecutive ridondanti sulla stessa ventola.

    Args:
        fan (int): Numero progressivo della ventola (1..N).
        rpm (int): RPM desiderato.

    Raises:
        FanError: Se ventola non trovata o RPM fuori range.

    Stampa:
        Messaggio di conferma con RPM misurati.
    """
    try:
        label = read_sysfs(f"{SMC}/fan{fan}_label")
        min_rpm = int(read_sysfs(f"{SMC}/fan{fan}_min"))
        max_rpm = int(read_sysfs(f"{SMC}/fan{fan}_max"))
    except (FileNotFoundError, ValueError, OSError):
        raise FanError(f"Ventola {fan} non trovata")
    if min_rpm > max_rpm:
        raise FanError(f"{label} ({fan}): min ({min_rpm}) > max ({max_rpm}) — sensore anomalo")
    if rpm < min_rpm or rpm > max_rpm:
        raise FanError(f"{label} ({fan}): {rpm} RPM fuori range [{min_rpm}, {max_rpm}]")

    # Debounce: skip se write troppo recente sulla stessa ventola
    key = f"fan{fan}"
    now = time.time()
    last = _fan_last_write.get(key, 0)
    if now - last < _FAN_DEBOUNCE_INTERVAL:
        return  # skip write ridondante

    write_sysfs(f"{SMC}/fan{fan}_manual", "1")
    write_sysfs(f"{SMC}/fan{fan}_output", str(rpm))
    _fan_last_write[key] = time.time()
    actual = read_sysfs(f"{SMC}/fan{fan}_input")
    print(f"{label} ({fan}) → {rpm} RPM ({actual} misurati)")


def set_all_fans(rpm):
    """
    Imposta tutte le ventole allo stesso RPM.

    Args:
        rpm (int): RPM da applicare a ogni ventola.
    """
    for i in range(1, get_fan_count() + 1):
        set_fan(i, rpm)


def auto():
    """
    Ripristina il controllo automatico hardware per tutte le ventole.

    Scrive 0 in ogni file fan{1..N}_manual, restituendo il controllo
    al firmware dell'hardware (driver applesmc).
    Resetta la cache debounce.
    """
    _fan_last_write.clear()
    for i in range(1, get_fan_count() + 1):
        write_sysfs(f"{SMC}/fan{i}_manual", "0")
        print(f"fan{i} → automatico")
