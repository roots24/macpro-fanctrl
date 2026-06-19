# MAC FANCONTROL
# macpro-fanctrl

Programma per il controllo manuale e automatico delle ventole su **Mac Pro 5,1** ("cheesegrater") in ambiente Linux.

## Descrizione

I Mac Pro 5,1 in Linux tendono a mantenere le ventole a regimi elevati perché il driver `applesmc` non implementa la gestione termica avanzata presente in macOS. Questo tool permette di:

- Leggere tutti i sensori di temperatura e le velocità delle ventole
- Impostare manualmente la velocità delle ventole (singola o globale)
- Eseguire un **demone automatico basato su curve PID-like** che regola i RPM in base ai sensori di temperatura configurati, usando interpolazione lineare a tratti
- **Profili di curva** predefiniti (silent, quiet_daily, heavy_work, render_mode) o personalizzati
- Installare/disinstallare un **servizio systemd** per l'avvio persistente
- Usare un'**interfaccia interattiva a terminale** o **interfaccia grafica (Tkinter)** con treeview dedicata sensori e colorizzazione temperatura (verde/arancione/rosso)

## Requisiti

- Mac Pro 5,1 con Linux
- Modulo kernel `applesmc` caricato (di solito automatico su hardware Apple)
- `sudo` / accesso root (necessario per scrivere su sysfs)

## Installazione

```bash
git clone <url-repo>
cd macpro-fanctrl
chmod +x macpro-fan.py
```

Nessun build necessario — Python 3 con libreria standard. Per la GUI serve `python3-tk` (`apt install python3-tk`).

## Struttura del progetto

```
macpro-fanctrl/
├── macpro-fan.py              # Entry point CLI
├── fanctrl/
│   ├── __init__.py             # Costanti condivise
│   ├── sysfs.py                # I/O sysfs (lettura/scrittura driver applesmc)
│   ├── sensors.py              # Rilevamento sensori temperatura
│   ├── fan.py                  # Operazioni ventole
│   ├── config.py               # Caricamento curva JSON + gestione profili
│   ├── display.py              # Output terminale + monitoraggio live
│   ├── utils.py                # Utility (root, PID, logging)
│   ├── daemon.py               # Demone curva automatica
│   ├── gui.py                  # GUI Tkinter
│   └── service.py              # Gestione servizio systemd
└── README.md
```

## Utilizzo

```
./macpro-fan.py <comando> [opzioni]
```

| Comando | Descrizione |
|---|---|
| `show` | Mostra tutte le ventole, sensori di temperatura e profilo attivo |
| `set <n> <rpm>` | Imposta manualmente la ventola N a un dato RPM |
| `set all <rpm>` | Imposta tutte le ventole allo stesso RPM |
| `auto` | Ripristina il controllo automatico hardware delle ventole |
| `gui` | Interfaccia grafica (Tkinter): treeview ventole + treeview sensori con colorizzazione temperatura, profili integrati |
| `daemon` | Avvia il demone con la curva automatica (primo piano) |
| `daemon --background` | Avvia il demone in background (double-fork) |
| `daemon --debug` | Avvia il demone con logging DEBUG level |
| `profile list` | Elenca i profili disponibili |
| `profile switch <nome>` | Cambia il profilo attivo |
| `profile show` | Mostra i dettagli del profilo attivo (sensori e curve) |
| `profile export <nome> <file>` | Esporta un profilo in file JSON |
| `profile import <file>` | Importa un profilo da file JSON |
| `monitor` | Monitoraggio continuo con refresh ogni 5 secondi |
| `install-service` | Installa il servizio systemd per l'avvio automatico |
| `restart-service` | Riavvia il servizio systemd |
| `uninstall-service` | Rimuove il servizio systemd |
| `status` | Mostra stato del servizio e ultimi log |

### Profili predefiniti

| Profilo | Intervallo | Descrizione |
|---|---|---|
| `silent` | 5s | Ultra-silenzioso per idle/light desktop, baseline RPM minimi |
| `quiet_daily` | 5s | Quiet Daily — bilanciato per uso quotidiano, cap 4500 RPM su tutte le zone |
| `heavy_work` | 3s | Heavy Work — soglie più aggressive per lavoro intensivo, cap 4500 RPM |
| `render_mode` | 2s | Render Mode — raffreddamento massimo, ramp aggressiva CPU/GPU, cap 4500 RPM |

### Esempi

```bash
# Mostra lo stato corrente
sudo ./macpro-fan.py show

# Cambia profilo
sudo ./macpro-fan.py profile switch heavy_work

# Mostra dettagli profilo attivo
sudo ./macpro-fan.py profile show

# Elenca profili disponibili
sudo ./macpro-fan.py profile list

# Monitoraggio live (refresh ogni 5s)
sudo ./macpro-fan.py monitor

# Imposta ventola #2 a 2000 RPM
sudo ./macpro-fan.py set 2 2000

# Ripristina controllo automatico
sudo ./macpro-fan.py auto

# Avvia il demone in primo piano con debug logging
sudo ./macpro-fan.py daemon --debug

# Avvia l'interfaccia grafica
sudo ./macpro-fan.py gui

# Esporta profilo per backup/condivisione
./macpro-fan.py profile export quiet_daily ~/quiet_daily-profile.json

# Importa profilo personalizzato
./macpro-fan.py profile import ~/custom-profile.json

# Installa come servizio di avvio
sudo ./macpro-fan.py install-service

# Riavvia il service
sudo ./macpro-fan.py restart-service

# Logging service
journalctl -u macpro-fan
```

## Configurazione

Il file di configurazione si trova in `~/.config/macpro-fan/curve.json`, generato automaticamente al primo avvio con tutti e 3 i profili predefiniti.

### Struttura del file

```json
{
  "active_profile": "quiet_daily",
  "profiles": {
    "silent": {
      "interval": 5,
      "fans": {
        "BOOST":   { "sensors": ["TCAC","TCAD"],         "curve": [[0,800],[35,1200],[45,1600],[55,2500],[65,4500]] },
        "PCI":     { "sensors": ["TMA1","TMA2","TMTG"],  "curve": [[0,800],[35,1200],[50,1800],[65,3000],[75,4500]] },
        "EXHAUST": { "sensors": ["Tp0C","Tp1C","TpPS"],  "curve": [[0,800],[30,1000],[40,1400],[50,2200],[60,4500]] },
        "INTAKE":  { "sensors": ["TCAG","TCBG","TN0D"],  "curve": [[0,800],[30,1000],[40,1400],[50,2200],[60,4500]] }
      }
    },
    "quiet_daily": { ... },
    "heavy_work": { ... },
    "render_mode": { ... }
  }
}
```

- `active_profile`: profilo correntemente attivo
- `profiles`: dizionario di profili, ognuno con `interval` (secondi) e `fans` (mappa ventola → sensori + curva)
- Ogni curva è una lista di coppie `[temperatura_C, RPM]` con interpolazione lineare

Il demone supporta **hot-reload**: modifica `curve.json` mentre è in esecuzione e la curva verrà ricaricata automaticamente al ciclo successivo, inclusi cambio di profilo e intervallo.

### Migrazione automatica

Se si aggiorna il programma da una versione precedente, il vecchio formato `curve.json` (con `fans` a livello radice) viene automaticamente convertito al nuovo formato con profili, preservando le personalizzazioni dell'utente nel profilo `quiet_daily`.

## Changelog

### Fix: exit code 0 trattato come errore in GUI

- **gui.py**: `_toggle_profile_daemon()` — condizione `proc.poll() is not None` → `proc.poll() is not None and proc.poll() != 0`; il demone double-fork (`daemon.py`) esce con code 0 (successo) mentre il daemon vero continua in background, la GUI ora distingue exit code 0 da errori reali

### X5690 Single-CPU Profile Alignment

- **config.py**: renaming profili `media` → `quiet_daily`, `alta` → `heavy_work`, `massima` → `render_mode`; aggiunto 4° profilo `silent` (ultra-silenzioso idle/light desktop)
- **config.py**: curve update per tutti i profili con cap 4500 RPM su tutte le zone (allineamento wiki mac-pro-5,1-x5690-profile)
- **config.py**: sensor mapping single-CPU — BOOST zone usa solo ["TCAC", "TCAD"] (CPU #1), rimossi sensori CPU B; EXHAUST zone usa ["Tp0C", "Tp1C", "TpPS"]; INTAKE zone usa ["TCAG", "TCBG", "TN0D"]
- **config.py**: fan zone labels aligned wiki — BOOSTA → BOOST, PS → EXHAUST, INTAKE sensors updated (CPU chamber ambient + MCP)
- **config.py**: active profile default changed to `quiet_daily`
- **README.md**: aggiornata tabella profili, esempio config JSON, changelog entry
- **macpro-fan.py**: docstring e argparse epilog aggiornati con nuovi nomi profili

### Versione attuale — Miglioramenti applicati

- **gui.py**: pulsante "Curva ON/OFF" rinominato in "Start Profili/Stop Profili", metodo `_toggle_curve` → `_toggle_profile_daemon`, status messages aggiornati da "curva" a "profili"
- **daemon.py**: aggiunta validazione curve (`interpolate()` fallback 800 RPM se curva invalida), punti ordinati automaticamente
- **daemon.py**: safety threshold — se temp > 95°C tutte ventole a max RPM della curva, log warning con top 5 temperature
- **daemon.py**: fallback RPM (min curve) quando sensors di una ventola unavailable
- **daemon.py**: supporto `--debug` flag per logging DEBUG level
- **utils.py**: RotatingFileHandler con rotazione log (5MB max, 3 backup files)
- **utils.py**: supporto `debug=False/True` parameter in `setup_logging()`
- **config.py**: `validate_profile()` — validazione curve ≥2 punti ordinati, RPM non negativi
- **config.py**: backup config (`curve.json.bak`) prima di ogni lettura/migrazione
- **config.py**: auto-recovery profilo invalido → sostituisce con default
- **config.py**: nuovi comandi `export_profile()` e `import_profile()` per backup/condivisione profili
- **fanctrl/fan.py**: debounce writes (0.15s intervallo minimo) per evitare writes ridondanti su sysfs
- **fanctrl/fan.py**: validazione min > max sensore anomalo
- **fanctrl/sensors.py**: cache sensori disponibili (`_scan_available_sensors()`) per performance
- **fanctrl/sensors.py**: `get_sensor_debug_info()` — debug info sensors found vs mapped
- **fanctrl/gui.py**: validazione RPM entry contro range ventola (min/max)
- **fanctrl/gui.py**: validazione RPM positivo, min sistema per "set all"
- **fanctrl/gui.py**: refresh loop resilient (`_refresh_loop()`) con try/except wrapper — non si ferma se GUI crash
- **service.py**: service unit robusto — StandardOutput=journal, UMask=0027, RestartSec=3, Wants=applesmc.service
- **service.py**: nuovo comando `restart-service`
- **macpro-fan.py**: argparse CLI con help strutturato e validazione input
- **macpro-fan.py**: nuovi comandi `profile export`, `profile import`, `restart-service`

### Migliorie precedenti (README originale)

- **daemon.py**: rimossa clamp ridondante dopo `interpolate()` (già clamps by design)
- **gui.py**: cambiato a `subprocess.Popen` per lancio daemon background — evita `TimeoutExpired` che blocca la GUI
- **gui.py**: treeview sensori con raggruppamento gerarchico per categoria (AMB + CPU/GPU/MCP/HDD/PWR/MEM/PCIe), collapsed default, user expand/collapse via click
- **gui.py**: colorizzazione temperatura su righe sensori usando tags `style.map()` — verde `<40°C`, arancione `40-60°C`, rosso `>60°C`
- **sensors.py**: aggiunti gruppi `MEM` e `PCIe` per 20+ sensori precedentemente in "Altro"
- **display.py**: clear screen portabile usando `subprocess.run(["clear"])` invece di codici escape ANSI `\033[H\033[J`

## Dettagli tecnici

- Lingua: **Python 3** (solo libreria standard, Tkinter per la GUI)
- Architettura: **multi-modulo** — package `fanctrl/` con 10 moduli separati
- Interfaccia: **sysfs** del kernel Linux (`/sys/devices/platform/applesmc.768`)
- Demone in background: **double-fork** (`os.fork()` + `os.setsid()`) per il distacco completo dal terminale
- Il controllo automatico hardware viene ripristinato all'uscita (SIGINT)
- Rilevamento dinamico del numero di ventole
- PID file in `/var/run/macpro-fan.pid` per il rilevamento dello stato del demone
- Logging su file `/var/log/macpro-fan.log` in modalità background (con rotazione 5MB/3 backup)
- Hot-reload della configurazione (`curve.json`)
- Gestione errori I/O sysfs con skip gracefully dei sensori/ventole non disponibili
- Safety threshold 95°C → max RPM automatic

## Note

Tutti i comandi che scrivono su sysfs richiedono **root**. I comandi `show`, `profile list`, `profile show` e `status` possono funzionare senza privilegi per la sola lettura.
