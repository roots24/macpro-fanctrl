"""
Modulo `fanctrl` — Controllo ventole Mac Pro 5.1 in Linux.

Questo package raggruppa le funzionalità di lettura/scrittura del driver
`applesmc` tramite sysfs, esposizione dei sensori di temperatura,
controllo manuale e automatico delle ventole, interfaccia interattiva TUI,
interfaccia grafica (Tkinter) e gestione del servizio systemd.

Costanti:
    SMC (str): Path del dispositivo applesmc in sysfs.
    CONFIG_DIR (str): Directory utente per la configurazione.
    CONFIG_PATH (str): Path completo del file curve.json.
    PIDFILE_PATH (str): Path del PID file per il demone in background.
    LOG_PATH (str): Path del file di log per il demone in background.
    SERVICE_NAME (str): Nome del servizio systemd.
    SERVICE_PATH (str): Path del file unit systemd.
"""

import os

SMC = "/sys/devices/platform/applesmc.768"

CONFIG_DIR = os.path.expanduser("~/.config/macpro-fan")
CONFIG_PATH = os.path.join(CONFIG_DIR, "curve.json")

PIDFILE_PATH = "/var/run/macpro-fan.pid"
LOG_PATH = "/var/log/macpro-fan.log"

SERVICE_NAME = "macpro-fan"
SERVICE_PATH = f"/etc/systemd/system/{SERVICE_NAME}.service"
