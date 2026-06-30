# MAC FANCONTROL
# macpro-fanctrl

Programma per il controllo manuale e automatico delle ventole su **Mac Pro 5,1** ("cheesegrater") in ambiente Linux.

## Descrizione

I Mac Pro 5,1 in Linux tendono a mantenere le ventole a regimi elevati perché il driver `applesmc` non implementa la gestione termica avanzata presente in macOS. Questo tool permette di:

- Leggere tutti i sensori di temperatura (SMC + hwmon) e le velocità delle ventole
- Impostare manualmente la velocità delle ventole (singola o globale)
- Eseguire un **demone automatico** che regola i RPM in base ai sensori di temperatura configurati
- **Profili di curva** con interpolazione lineare a tratti o **controllo PID** (Proportional-Integral-Derivative)
- **Isteresi configurabile** per prevenire oscillazioni delle ventole
- **Slew rate limiting** per transizioni RPM graduali (senza sbalzi acustici)
- Installare/disinstallare un **servizio systemd** per l'avvio persistente
- Usare un'**interfaccia interattiva a terminale** o **interfaccia grafica (Tkinter)** con colorizzazione temperatura (verde/arancione/rosso)

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
│   ├── sensors.py              # Rilevamento sensori temperatura SMC + detect CPU
│   ├── non_smc.py              # Scanner sensori hwmon (coretemp, amdgpu, nvme)
│   ├── pid.py                  # Controllore PID per ventole
│   ├── fan.py                  # Operazioni ventole
│   ├── config.py               # Caricamento curva JSON + gestione profili
│   ├── display.py              # Output terminale + monitoraggio live
│   ├── utils.py                # Utility (root, PID, logging)
│   ├── daemon.py               # Demone curva automatica
│   ├── gui.py                  # GUI Tkinter
│   └── service.py              # Gestione servizio systemd
├── tests/
│   ├── test_config.py          # 15 test: validazione profili, safety, hysteresis
│   ├── test_daemon.py          # 19 test: interpolate, safety_check, fallback
│   ├── test_sensors.py         # 15 test: group_temps, TEMP_LABELS, TEMP_GROUPS
│   └── test_pid.py             # 15 test: risposta P/I/D, clamping, anti-windup
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
| `gui` | Interfaccia grafica (Tkinter): treeview ventole + sensori, profili integrati |
| `daemon` | Avvia il demone con la curva automatica (primo piano) |
| `daemon --background` | Avvia il demone in background (double-fork) |
| `daemon --debug` | Avvia il demone con logging DEBUG level |
| `gpu-info` | Mostra stato termico GPU completo (SMC + hwmon amdgpu) |
| `cpu-info` | Mostra CPU rilevate, sensori SMC e core temp hwmon |
| `profile list` | Elenca i profili disponibili |
| `profile switch <nome>` | Cambia il profilo attivo |
| `profile show` | Mostra i dettagli del profilo attivo (sensori e curve) |
| `profile export <nome> <file>` | Esporta un profilo in file JSON |
| `profile import <file>` | Importa un profilo da file JSON |
| `profile dual-auto [--apply]` | Rileva CPU count e suggerisce/applica profilo dual/single appropriato |
| `monitor` | Monitoraggio continuo con refresh ogni 5 secondi |
| `install-service` | Installa il servizio systemd per l'avvio automatico |
| `restart-service` | Riavvia il servizio systemd |
| `uninstall-service` | Rimuove il servizio systemd |
| `status` | Mostra stato del servizio e ultimi log |

### Profili predefiniti (8 totali)

| Profilo | Intervallo | Modalità | Descrizione |
|---|---|---|---|
| `silent` | 5s | curve | Ultra-silenzioso per idle, EXHAUST/INTAKE a 2800 RPM max |
| `quiet_daily` | 5s | curve | Bilanciato per uso quotidiano (DEFAULT) |
| `heavy_work` | 3s | curve | Soglie più aggressive per lavoro intensivo |
| `render_mode` | 2s | curve | Raffreddamento massimo, ramp aggressiva |
| `quiet_daily_dual` | 5s | curve | Dual CPU — baseline +400 RPM, BOOST max 5200 RPM |
| `heavy_work_dual` | 3s | curve | Dual CPU — soglie alte per carichi su due Xeon |
| `render_mode_dual` | 2s | curve | Dual CPU — raffreddamento massimo, EXHAUST 4500 RPM |
| `pid_quiet` | 3s | **pid** | Controllo PID: target 55°C, Kp=20, Ki=0.8, Kd=3.0 |

### Curve Complete per Profilo

#### silent (interval: 5s)
| Ventola | Sensori | Curva [°C→RPM] |
|---------|---------|----------------|
| BOOST | TCAC, TCAD | [[0,800],[35,1200],[45,1600],[55,2500],[65,4500]] |
| PCI | TMA1, TMA2, TMTG, edge, junction, mem | [[0,800],[35,1200],[50,1800],[65,3000],[75,4500]] |
| EXHAUST | Tp0C, Tp1C, TpPS | [[0,800],[30,1000],[40,1400],[50,2200],[60,**2800**]] |
| INTAKE | TCAG, TCBG, TN0D | [[0,800],[30,1000],[40,1400],[50,2200],[60,**2800**]] |

#### quiet_daily (interval: 5s) — DEFAULT
| Ventola | Sensori | Curva [°C→RPM] |
|---------|---------|----------------|
| BOOST | TCAC, TCAD | [[0,800],[35,1200],[45,2000],[55,3000],[65,4500]] |
| PCI | TMA1, TMA2, TMTG, edge, junction, mem | [[0,800],[35,1200],[50,2000],[65,3500],[75,4500]] |
| EXHAUST | Tp0C, Tp1C, TpPS | [[0,1000],[30,1000],[40,1500],[50,2500],[60,**2800**]] |
| INTAKE | TCAG, TCBG, TN0D | [[0,1000],[30,1000],[40,1500],[50,2500],[60,**2800**]] |

#### heavy_work (interval: 3s)
| Ventola | Sensori | Curva [°C→RPM] |
|---------|---------|----------------|
| BOOST | TCAC, TCAD | [[0,2000],[35,2000],[45,2800],[55,3500],[65,4500]] |
| PCI | TMA1, TMA2, TMTG, edge, junction, mem | [[0,1500],[35,1500],[50,2500],[65,4000],[75,4500]] |
| EXHAUST | Tp0C, Tp1C, TpPS | [[0,2000],[30,2000],[40,2500],[50,3500],[60,**2800**]] |
| INTAKE | TCAG, TCBG, TN0D | [[0,2000],[30,2000],[40,2500],[50,3500],[60,**2800**]] |

#### render_mode (interval: 2s)
| Ventola | Sensori | Curva [°C→RPM] |
|---------|---------|----------------|
| BOOST | TCAC, TCAD | [[0,3000],[35,3000],[45,3800],[55,4200],[65,4500]] |
| PCI | TMA1, TMA2, TMTG, edge, junction, mem | [[0,2500],[35,2500],[50,3500],[60,4200],[75,4500]] |
| EXHAUST | Tp0C, Tp1C, TpPS | [[0,3000],[30,3000],[40,3800],[50,4200],[60,**2800**]] |
| INTAKE | TCAG, TCBG, TN0D | [[0,3000],[30,3000],[40,3800],[50,4200],[60,**2800**]] |

#### quiet_daily_dual (interval: 5s) — Dual CPU
| Ventola | Sensori | Curva [°C→RPM] |
|---------|---------|----------------|
| BOOST | TCAC, TCAD, **TCBC, TCBD** | [[0,1200],[35,1500],[45,2500],[55,3500],[65,**5200**]] |
| PCI | TMA1, TMA2, TMTG, edge, junction, mem | [[0,1000],[35,1400],[50,2200],[65,3500],[75,4500]] |
| EXHAUST | Tp0C, Tp1C, TpPS | [[0,1200],[30,1400],[40,1800],[50,2500],[60,2800]] |
| INTAKE | TCAG, TCBG, TN0D | [[0,1200],[30,1400],[40,1800],[50,2500],[60,2800]] |

#### heavy_work_dual (interval: 3s) — Dual CPU
| Ventola | Sensori | Curva [°C→RPM] |
|---------|---------|----------------|
| BOOST | TCAC, TCAD, TCBC, TCBD | [[0,2200],[35,2500],[45,3200],[55,4000],[65,**5200**]] |
| PCI | TMA1, TMA2, TMTG, edge, junction, mem | [[0,1800],[35,2000],[50,2800],[65,4200],[75,4500]] |
| EXHAUST | Tp0C, Tp1C, TpPS | [[0,2200],[30,2400],[40,2800],[50,3500],[60,4500]] |
| INTAKE | TCAG, TCBG, TN0D | [[0,2200],[30,2400],[40,2800],[50,3500],[60,4500]] |

#### render_mode_dual (interval: 2s) — Dual CPU
| Ventola | Sensori | Curva [°C→RPM] |
|---------|---------|----------------|
| BOOST | TCAC, TCAD, TCBC, TCBD | [[0,3200],[35,3500],[45,4200],[55,4800],[65,**5200**]] |
| PCI | TMA1, TMA2, TMTG, edge, junction, mem | [[0,2800],[35,3000],[50,3800],[60,4500],[75,4500]] |
| EXHAUST | Tp0C, Tp1C, TpPS | [[0,3200],[30,3400],[40,4000],[50,4500],[60,4500]] |
| INTAKE | TCAG, TCBG, TN0D | [[0,3200],[30,3400],[40,4000],[50,4500],[60,4500]] |

### GPU Passthrough Profile
Quando la Radeon VII è rilevata sotto carico (TeGG/TeRG > 45°C), il demone applica automaticamente un moltiplicatore +15% ai RPM minimi della zona PCI per garantire raffreddamento adeguato alla GPU.

### PID Control Mode
Il profilo `pid_quiet` usa un controllore PID invece dell'interpolazione lineare:

| Ventola | Target | Kp | Ki | Kd | Range RPM |
|---------|--------|----|----|----|-----------|
| BOOST | 55°C | 20 | 0.8 | 3.0 | 800–4500 |
| PCI | 55°C | 18 | 0.6 | 2.5 | 800–4500 |
| EXHAUST | 50°C | 15 | 0.5 | 2.0 | 800–2800 |
| INTAKE | 50°C | 15 | 0.5 | 2.0 | 800–2800 |

Il PID risponde in modo continuo alla temperatura corrente e alla sua derivata, eliminando gli scalini tipici delle curve a tratti. L'isteresi è disabilitata automaticamente in modalità PID.

### Esempi

```bash
# Mostra lo stato corrente
sudo ./macpro-fan.py show

# Cambia profilo
sudo ./macpro-fan.py profile switch heavy_work

# Mostra dettagli profilo attivo
sudo ./macpro-fan.py profile show

# Rileva CPU e suggerisce profilo
sudo ./macpro-fan.py profile dual-auto --apply

# Elenca profili disponibili
sudo ./macpro-fan.py profile list

# Mostra info CPU (singola/duale + coretemp hwmon)
sudo ./macpro-fan.py cpu-info

# Mostra info GPU completa (SMC + hwmon)
sudo ./macpro-fan.py gpu-info

# Monitoraggio live (refresh ogni 5s)
sudo ./macpro-fan.py monitor

# Imposta ventola #2 a 2000 RPM
sudo ./macpro-fan.py set 2 2000

# Ripristina controllo automatico
sudo ./macpro-fan.py auto

# Avvia il demone in primo piano con debug logging
sudo ./macpro-fan.py daemon --debug

# Avvia il demone con controllo PID
sudo ./macpro-fan.py profile switch pid_quiet
sudo ./macpro-fan.py daemon

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

Il file di configurazione si trova in `~/.config/macpro-fan/curve.json`, generato automaticamente al primo avvio con tutti i profili predefiniti.

### Struttura del file

```json
{
  "active_profile": "quiet_daily",
  "profiles": {
    "quiet_daily": {
      "interval": 5,
      "control_mode": "curve",
      "safety": {
        "system_max_temp": 95,
        "system_fallback_rpm": "max",
        "gpu_sensors": ["TeGG", "TeRG"],
        "gpu_max_temp": 90
      },
      "hysteresis": { "enabled": true, "deadband": 3 },
      "slew_rate": { "max_rpm_change_per_cycle": 500 },
      "fans": {
        "BOOST": { "sensors": ["TCAC","TCAD"], "curve": [[0,800],[35,1200],[45,2000],[55,3000],[65,4500]] },
        "PCI": { "sensors": ["TMA1","TMA2","TMTG","edge","junction","mem"], "curve": [[0,800],[35,1200],[50,2000],[65,3500],[75,4500]] },
        "EXHAUST": { "sensors": ["Tp0C","Tp1C","TpPS"], "curve": [[0,1000],[30,1000],[40,1500],[50,2500],[60,2800]] },
        "INTAKE": { "sensors": ["TCAG","TCBG","TN0D"], "curve": [[0,1000],[30,1000],[40,1500],[50,2500],[60,2800]] }
      }
    }
  }
}
```

- `active_profile`: profilo correntemente attivo
- `control_mode`: `"curve"` (interpolazione lineare) o `"pid"` (controllo PID)
- `safety`: soglie di sicurezza (system_max_temp, gpu_max_temp, gpu_sensors, system_fallback_rpm)
- `hysteresis`: banda morta in °C per evitare oscillazioni ventola
- `slew_rate`: variazione RPM massima per ciclo per transizioni graduali
- `profiles`: dizionario di profili, ognuno con `interval` (secondi) e `fans`

Il demone supporta **hot-reload**: modifica `curve.json` mentre è in esecuzione e la curva verrà ricaricata automaticamente al ciclo successivo.

### Migrazione automatica

Se si aggiorna il programma da una versione precedente, il vecchio formato `curve.json` viene automaticamente convertito al nuovo formato con profili. I campi `safety`, `hysteresis`, `slew_rate` e `control_mode` vengono aggiunti automaticamente ai profili esistenti con valori predefiniti.

## Hardware Supportato

### Mac Pro 5,1 + Xeon W5690 + Radeon VII (Configurazione Attuale)
- **Modello**: Mac Pro 5,1 ("Cheesegrater")
- **CPU**: Intel Xeon W5690 (Westmere-EP, 6 core / 12 thread @ 3.47 GHz, TDP 130W)
- **GPU**: AMD Radeon VII (Vega 20, HBM2, TBP ~290W)
- **Bus PCIe**: PCIe 2.0 x16 per GPU
- **RAM**: DDR3 ECC registrata

### Dual CPU Support
Il progetto supporta configurazioni dual-CPU con profili dedicati:
- Rilevamento automatico CPU count (`detect_cpu_count()`)
- Profili con sensori CPU A + B (TCAC, TCAD + TCBC, TCBD)
- Baseline RPM +400–500 per zona (260W TDP combinato)
- BOOST max 5200 RPM (capienza hardware)

### Sensori Non-SMC (hwmon)
| Sorgente | Driver | Sensori | Integrazione |
|----------|--------|---------|-------------|
| CPU Cores | coretemp | Per-core temperature (PECI) | `cpu-info`, `gpu-info` |
| GPU | amdgpu | Fan RPM, edge/junction/mem °C, power W, clock MHz | Curva PCI + `gpu-info` |
| NVMe | nvme | Composite + individual sensor °C | `gpu-info` |

### Mappatura Sensori GPU (Radeon VII)
| Sensore | Descrizione | OK | WARN | CRIT |
|---------|-------------|----|------|------|
| `TeGG` | GPU Heatsink 1 | <60°C | 60-75°C | >75°C |
| `TeGP` | GPU Proximity Global | <60°C | 60-75°C | >75°C |
| `TeRG` | GPU Heatsink 2 | <60°C | 60-75°C | >75°C |
| `TeRP` | GPU Proximity Global 2 | <60°C | 60-75°C | >75°C |

### Mappatura Sensori CPU (Xeon W5690)
| Sensore | Descrizione | OK | WARN | CRIT |
|---------|-------------|----|------|------|
| `TCAC` | CPU A Core | <40°C | 40-60°C | >60°C |
| `TCAD` | CPU A Diode | <40°C | 40-60°C | >60°C |
| `TCBC` | CPU B Core (dual) | <40°C | 40-60°C | >60°C |
| `TCBD` | CPU B Diode (dual) | <40°C | 40-60°C | >60°C |

## Dettagli tecnici

- Lingua: **Python 3** (solo libreria standard, Tkinter per la GUI)
- Architettura: **multi-modulo** — package `fanctrl/` con 12 moduli separati
- Interfaccia SMC: **sysfs** del kernel Linux (`/sys/devices/platform/applesmc.768`)
- Interfaccia hwmon: **sysfs** (`/sys/class/hwmon/`) per coretemp, amdgpu, nvme
- Demone in background: **double-fork** (`os.fork()` + `os.setsid()`) per il distacco completo dal terminale
- Il controllo automatico hardware viene ripristinato all'uscita (SIGINT)
- Rilevamento dinamico del numero di ventole
- PID file in `/var/run/macpro-fan.pid` per il rilevamento dello stato del demone
- Logging su file `/var/log/macpro-fan.log` in modalità background (rotazione 5MB/3 backup)
- Hot-reload della configurazione (`curve.json`)
- Gestione errori I/O sysfs con skip gracefully
- Safety threshold configurabile (default 95°C) — max RPM automatic
- Debounce 0.15s su scritture sysfs

## Test

```bash
python3 -m unittest tests/*.py -v
```

64 test che coprono: validazione profili, interpolazione, safety check, fallback sensors, controllore PID, raggruppamento sensori.

## Note

Tutti i comandi che scrivono su sysfs richiedono **root**. I comandi `show`, `profile list`, `profile show`, `cpu-info` (parziale) e `status` possono funzionare senza privilegi per la sola lettura.

anteprima 
![alt text](<Screenshot From 2026-06-23 20-32-47.png>)
<video controls src="Screencast From 2026-06-23 20-34-31.mp4" title="Title"></video>
