"""
`fanctrl/service.py` — Gestione del servizio systemd.

Fornisce funzioni per installare, disinstallare e controllare
lo stato del servizio systemd che avvia il demone automaticamente
all'avvio del sistema.

Il servizio usa ExecStart per lanciare lo script principale
con il comando 'daemon' (in primo piano, systemd gestisce
il background).
"""

import os
import subprocess
import sys

from fanctrl import SERVICE_NAME, SERVICE_PATH
from fanctrl.utils import require_root, get_script_path


def cmd_install_service():
    """
    Installa e avvia il servizio systemd.

    Crea il file /etc/systemd/system/macpro-fan.service con il
    template appropriato, poi esegue systemctl daemon-reload,
    enable e start.

    Il service unit include:
    - StandardOutput/StandardError=journal per logging centralizzato
    - UMask=0027 per permessi sicuri sui file creati
    - RestartSec=3 per recovery più rapida
    - After=sysinit.target per avvio dopo inizializzazione sistema

    Richiede privilegi di root.
    """
    require_root()
    script_path = get_script_path()
    python_path = sys.executable
    template = f"""\
[Unit]
Description=MacPro 5.1 Fan Curve Daemon — Controllo ventole automatico
Documentation=https://github.com/macpro-fanctrl
After=sysinit.target multi-user.target
Wants=applesmc.service

[Service]
Type=simple
ExecStart={python_path} {script_path} daemon
Restart=on-failure
RestartSec=3
StandardOutput=journal
StandardError=journal
UMask=0027
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
    with open(SERVICE_PATH, "w") as f:
        f.write(template)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "--now", SERVICE_NAME], check=True)
    print(f"Service {SERVICE_NAME} installato e avviato.")
    print(f"Service file: {SERVICE_PATH}")
    print("Logging: journalctl -u macpro-fan")


def cmd_uninstall_service():
    """
    Ferma e rimuove il servizio systemd.

    Disabilita e ferma il servizio, rimuove il file unit,
    e ricarica la configurazione systemd.

    Richiede privilegi di root.
    """
    require_root()
    subprocess.run(
        ["systemctl", "disable", "--now", SERVICE_NAME],
        capture_output=True,
    )
    if os.path.exists(SERVICE_PATH):
        os.remove(SERVICE_PATH)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    print(f"Service {SERVICE_NAME} rimosso.")


def cmd_status():
    """
    Mostra lo stato del servizio systemd e le ultime 20 righe di log.

    Non richiede privilegi di root (systemctl status funziona
    anche per utenti non privilegiati per i servizi di sistema).
    """
    result = subprocess.run(["systemctl", "status", SERVICE_NAME], capture_output=True, text=True)
    if result.returncode == 0:
        print(result.stdout)
    else:
        # Service non attivo o non trovato
        lines = result.stderr.decode() if result.stderr else result.stdout.decode()
        for line in lines.splitlines():
            print(line)

    print("\n--- Ultime righe di log ---")
    subprocess.run(["journalctl", "-u", SERVICE_NAME, "-n", "20", "--no-pager"])


def cmd_service_restart():
    """
    Riavvia il servizio systemd.

    Richiede privilegi di root.
    """
    require_root()
    subprocess.run(["systemctl", "restart", SERVICE_NAME], check=True)
    print(f"Service {SERVICE_NAME} riavviato.")
