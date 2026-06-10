"""
`fanctrl/daemon.py` — Demone di controllo automatico ventole basato su curva.

Implementa il cuore dell'automazione: un ciclo che periodicamente legge
i sensori di temperatura, calcola l'RPM target per ogni gruppo ventola
tramite interpolazione lineare sulla temperatura massima dei sensori
associati, e scrive i valori su sysfs.

Supporta:
  - Esecuzione in primo piano (cmd_daemon)
  - Esecuzione in background con double-fork (cmd_daemon_bg)
  - Hot-reload della configurazione (curve.json)
  - Logging strutturato su file o stdout
"""

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


def interpolate(curve, temp):
    """
    Calcola l'RPM target per una data temperatura tramite interpolazione
    lineare a tratti.

    La curva è una lista di punti [temperatura_C, RPM]. Per temperature
    fuori dal range definito, clamp al primo/ultimo punto.

    Validazione: se curva vuota o con <2 punti, restituisce fallback 800 RPM.
    Punti vengono ordinati automaticamente per temperatura.

    Args:
        curve (list[list[int, int]]): Lista di punti [temp, rpm].
             Esempio: [[0, 800], [50, 800], [60, 1200], [70, 2000]]
        temp (int): Temperatura corrente in °C.

    Returns:
        int: RPM target calcolato (arrotondato all'intero), o 800 come fallback.
    """
    if not curve or len(curve) < 2:
        return 800  # fallback min RPM
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
    """
    Verifica se qualche sensore supera la threshold di sicurezza.

    Args:
        all_temps (dict): Mappa {chiave: temperatura_C} da get_all_temps().
        max_safe (int): Threshold massima in °C (default 95).

    Returns:
        bool: True se almeno un sensore > max_safe, False altrimenti.
    """
    for temp in all_temps.values():
        if temp > max_safe:
            return True
    return False


def _cleanup_daemon():
    set_auto()
    remove_pidfile()


def _signal_handler(signum, frame):
    raise KeyboardInterrupt


def cmd_daemon(debug=False):
    """
    Avvia il demone di controllo ventole in primo piano.

    Args:
        debug (bool): Se True, abilita logging DEBUG level.
    """
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

    last_rpm = {}
    try:
        while True:
            try:
                mtime = os.path.getmtime(CONFIG_PATH)
                if mtime != config_mtime:
                    full_config = load_config()
                    config_mtime = mtime
                    profile_name, profile = get_active_profile_config()
                    interval = profile.get("interval", 5)
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

            # Safety threshold: se temp > 95°C → tutte ventole a max RPM della curva
            safety_active = safety_check(all_temps, max_safe=95)
            if safety_active:
                logger.warning(f"SAFETY: temperature critiche rilevate! Max temps: {', '.join(f'{k}={v}°C' for k, v in sorted(all_temps.items(), key=lambda x: x[1], reverse=True)[:5])}")

            for label, fconf in profile["fans"].items():
                fan_num = fan_map.get(label)
                if fan_num is None:
                    continue

                sensor_temps = [
                    all_temps.get(s)
                    for s in fconf["sensors"]
                    if all_temps.get(s) is not None
                ]
                if safety_active:
                    # Usa ultimo punto della curva (max RPM)
                    target = interpolate(fconf["curve"], 9999)
                    key = f"fan{fan_num}"
                    if last_rpm.get(key) != target:
                        try:
                            write_sysfs(f"{SMC}/fan{fan_num}_manual", "1")
                            write_sysfs(f"{SMC}/fan{fan_num}_output", str(target))
                            actual = read_sysfs(f"{SMC}/fan{fan_num}_input")
                            logger.info(f"{label} [SAFETY] → {target} RPM [{actual}]")
                            last_rpm[key] = target
                        except OSError as e:
                            logger.error(f"Errore scrittura {label}: {e}")
                    continue

                if not sensor_temps:
                    # Fallback: usa primo punto della curva (min RPM)
                    target = interpolate(fconf["curve"], 0)
                    key = f"fan{fan_num}"
                    if last_rpm.get(key) != target:
                        try:
                            write_sysfs(f"{SMC}/fan{fan_num}_manual", "1")
                            write_sysfs(f"{SMC}/fan{fan_num}_output", str(target))
                            actual = read_sysfs(f"{SMC}/fan{fan_num}_input")
                            logger.info(f"{label} [fallback] → {target} RPM [{actual}] (no sensors)")
                            last_rpm[key] = target
                        except OSError as e:
                            logger.error(f"Errore scrittura {label}: {e}")
                    continue

                max_temp = max(sensor_temps)
                target = interpolate(fconf["curve"], max_temp)

                key = f"fan{fan_num}"
                if last_rpm.get(key) != target:
                    try:
                        write_sysfs(f"{SMC}/fan{fan_num}_manual", "1")
                        write_sysfs(f"{SMC}/fan{fan_num}_output", str(target))
                        actual = read_sysfs(f"{SMC}/fan{fan_num}_input")
                        logger.info(f"{label} ({max_temp}°C) → {target} RPM [{actual}]")
                        last_rpm[key] = target
                    except OSError as e:
                        logger.error(f"Errore scrittura {label}: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Daemon fermato.")
        _cleanup_daemon()


def cmd_daemon_bg():
    """
    Avvia il demone di controllo ventole in background.

    Usa la tecnica del double-fork:
    1. Primo fork: il processo padre termina (ritorno al terminale)
    2. setsid(): crea una nuova sessione, distacco dal terminale
    3. Secondo fork: garantisce che il processo non possa riacquisire
       un terminale
    4. Reindirizza stdin/stdout/stderr al logger su file
    5. Scrive il PID file per il monitoraggio

    Il processo figlio esegue cmd_daemon() che resta in esecuzione
    fino a Ctrl+C o SIGTERM.
    """
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
