"""
`fanctrl/sysfs.py` — Interfaccia a basso livello con il driver applesmc.

Fornisce le funzioni di lettura e scrittura dei file sysfs esposti dal
modulo kernel `applesmc` in `/sys/devices/platform/applesmc.768/...`.

Tutte le funzioni gestiscono gli errori I/O (FileNotFoundError,
PermissionError, OSError) restituendo valori predefiniti o None,
permettendo ai chiamanti di operare in modo robusto anche in
presenza di hardware parziale o permessi insufficienti.
"""

import os

from fanctrl import SMC


def read_sysfs(path):
    """
    Legge il contenuto di un file sysfs.

    Tenta di aprire e leggere il file specificato da `path`.
    In caso di errore (file inesistente, permessi negati, errore I/O)
    restituisce una stringa vuota invece di sollevare eccezioni.

    Args:
        path (str): Path assoluto del file sysfs da leggere.

    Returns:
        str: Contenuto del file con spazi iniziali/finali rimossi,
             oppure stringa vuota in caso di errore.
    """
    try:
        with open(path) as f:
            return f.read().strip()
    except (FileNotFoundError, PermissionError, OSError):
        return ""


def write_sysfs(path, val):
    """
    Scrive un valore in un file sysfs.

    Args:
        path (str): Path assoluto del file sysfs da scrivere.
        val (str): Valore da scrivere (%d o %s).

    Raises:
        OSError: Se il file non è scrivibile o permessi insufficienti.
    """
    with open(path, "w") as f:
        f.write(str(val))


def read_temp(label_key):
    """
    Legge la temperatura di un sensore label_key espresso in millesimi di °C.

    Converte il valore raw in °C dividendo per 1000. Filtra valori
    anomali (< -50°C) restituendo None.

    Args:
        label_key (str): Chiave del sensore (es. "TCAC", "TA0P").

    Returns:
        int | None: Temperatura in °C, oppure None se il sensore non
                    è presente, non è leggibile o restituisce un valore
                    anomalo.
    """
    path = f"{SMC}/{label_key}_input"
    try:
        raw = read_sysfs(path)
        temp = int(raw) // 1000
        return temp if temp > -50 else None
    except (FileNotFoundError, ValueError):
        return None
