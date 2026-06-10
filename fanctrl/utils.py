"""
`fanctrl/utils.py` — Funzioni di utilità trasversali.

Fornisce utility usate da più moduli del package:
  - Verifica privilegi di root (require_root)
  - Gestione PID file per il demone (write_pidfile / read_pidfile / remove_pidfile / is_daemon_running)
  - Configurazione del sistema di logging (setup_logging)
  - Risoluzione del path dello script principale (get_script_path)
"""

import logging
import logging.handlers
import os
import sys

from fanctrl import PIDFILE_PATH, LOG_PATH


def require_root():
    """
    Verifica che il processo abbia privilegi di root (UID 0).

    Se l'utente non è root, stampa un messaggio di errore e termina
    il programma con sys.exit(1). Deve essere chiamata all'inizio
    di ogni comando che scrive su sysfs.
    """
    if os.geteuid() != 0:
        print("Questo comando richiede privilegi di root. Esegui con sudo.")
        sys.exit(1)


def write_pidfile():
    """
    Scrive il PID del processo corrente in PIDFILE_PATH.

    Il file viene usato da is_daemon_running() per verificare se
    il demone è attivo, e da remove_pidfile() per la pulizia.
    """
    with open(PIDFILE_PATH, "w") as f:
        f.write(str(os.getpid()))


def read_pidfile():
    """
    Legge il PID salvato in PIDFILE_PATH.

    Returns:
        int | None: Il PID letto, oppure None se il file non esiste
                    o contiene un valore non valido.
    """
    try:
        with open(PIDFILE_PATH) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def remove_pidfile():
    """
    Rimuove PIDFILE_PATH se esiste.

    Va chiamata in fase di arresto del demone (tramite atexit
    o signal handler) per garantire una pulizia corretta.
    """
    if os.path.exists(PIDFILE_PATH):
        os.remove(PIDFILE_PATH)


def is_daemon_running():
    """
    Verifica se il demone è attualmente in esecuzione.

    Legge il PID da PIDFILE_PATH e usa os.kill(pid, 0) per
    verificare l'esistenza del processo. Se il processo non esiste
    più, rimuove automaticamente il PID file.

    Returns:
        bool: True se il demone è in esecuzione, False altrimenti.
    """
    pid = read_pidfile()
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        remove_pidfile()
        return False


def setup_logging(background=False, debug=False):
    """
    Configura il logger 'macpro-fan' con output su file o stdout.

    In modalità background (background=True) scrive su LOG_PATH
    (/var/log/macpro-fan.log) con rotazione automatica (5MB max, 3 backup).
    Altrimenti su stdout (stretto dal terminale per il foreground).

    Supporta level DEBUG quando debug=True.

    Args:
        background (bool): Se True, usa RotatingFileHandler; altrimenti StreamHandler.
        debug (bool): Se True, setta logger level a DEBUG.

    Returns:
        logging.Logger: Logger configurato.
    """
    logger = logging.getLogger("macpro-fan")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()
    if background:
        handler = logging.handlers.RotatingFileHandler(
            LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3
        )
    else:
        handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(handler)
    return logger


def get_script_path():
    """
    Restituisce il path assoluto dello script principale in esecuzione.

    Usa sys.modules['__main__'].__file__ per risalire al file .py
    avviato dall'utente, che viene usato come target per il
    servizio systemd e per il Popen del demone in background.

    Returns:
        str: Path assoluto del main script.
    """
    main = sys.modules.get("__main__")
    if main and hasattr(main, "__file__"):
        return os.path.abspath(main.__file__)
    return os.path.abspath(sys.argv[0])
