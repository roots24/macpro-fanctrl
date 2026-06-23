#!/usr/bin/env python3
"""
macpro-fan.py — Controllo ventole Mac Pro 5.1 in Linux.

Entry point principale del programma. Importa tutti i moduli del package
fanctrl e dispatcher il comando ricevuto da riga di comando.

Utilizzo:
    ./macpro-fan.py <comando> [opzioni]

Comandi:
    show                    Mostra ventole + temperature
    set <n|all> <rpm>       Imposta ventola manualmente
    auto                    Ripristina controllo automatico
    gui                     Interfaccia grafica (Tkinter)
    daemon [--background] [--debug]   Avvia demone curva automatica
    install-service         Installa e avvia systemd service
    uninstall-service       Ferma e rimuove systemd service
    status                  Stato service + log
    profile list            Elenca profili disponibili
    profile switch <nome>   Cambia profilo attivo
    profile show            Mostra dettagli profilo attivo
    profile export <nome> <file>  Esporta profilo in JSON
    profile import <file>       Importa profilo da JSON
    monitor                 Monitoraggio continuo (5s refresh)
    gpu-info                Mostra stato termico GPU (Radeon VII)

Profili predefiniti: silent, quiet_daily, heavy_work, render_mode (cap 4500 RPM, single-CPU sensor mapping).
"""

import argparse
import sys

from fanctrl.sensors import get_all_temps, group_temps, TEMP_LABELS
from fanctrl.fan import get_fan_info, set_fan, set_all_fans, auto, FanError
from fanctrl.display import show_fans, show_temps, cmd_monitor
from fanctrl.daemon import cmd_daemon, cmd_daemon_bg
from fanctrl.service import cmd_install_service, cmd_uninstall_service, cmd_status, cmd_service_restart
from fanctrl.utils import require_root
from fanctrl.config import list_profiles, switch_profile, get_active_profile, get_active_profile_config, export_profile, import_profile


def usage():
    print("Uso: macpro-fan.py <comando> [opzioni]")
    print()
    print("Comandi:")
    print("  show                    Mostra ventole + temperature")
    print("  set <n|all> <rpm>       Imposta ventola manualmente")
    print("  auto                    Ripristina controllo automatico")
    print("  gui                     Interfaccia grafica (Tkinter)")
    print("  daemon [--background] [--debug]   Avvia demone curva automatica")
    print("  install-service         Installa e avvia systemd service")
    print("  uninstall-service       Ferma e rimuove systemd service")
    print("  status                  Stato service + log")
    print("  profile list            Elenca profili disponibili")
    print("  profile switch <nome>   Cambia profilo attivo")
    print("  profile show            Mostra dettagli profilo attivo")
    print("  profile export <nome> <file>  Esporta profilo in JSON")
    print("  profile import <file>       Importa profilo da JSON")
    print("  monitor                 Monitoraggio continuo (5s refresh)")
    print("  gpu-info                Mostra stato termico GPU (Radeon VII)")
    sys.exit(1)


def cmd_profile_show():
    name, profile = get_active_profile_config()
    print(f"Profilo attivo: {name}")
    print(f"Intervallo: {profile.get('interval', 5)}s")
    print()
    for label, fconf in profile.get("fans", {}).items():
        sensors = ", ".join(fconf.get("sensors", []))
        curve_pts = "  ".join(f"{p[0]}°C→{p[1]}RPM" for p in fconf.get("curve", []))
        print(f"  {label}:")
        print(f"    Sensori: {sensors}")
        print(f"    Curva:   {curve_pts}")
        print()


def cmd_profile_list():
    profiles = list_profiles()
    active = get_active_profile()
    print("Profili disponibili:")
    for p in profiles:
        marker = " *" if p == active else "  "
        print(f"  {marker} {p}")


def main():
    parser = argparse.ArgumentParser(
        description="MacPro 5.1 Fan Control — Controllo ventole in Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Comandi:
  show                    Mostra ventole + temperature
  set <n|all> <rpm>       Imposta ventola manualmente
  auto                    Ripristina controllo automatico
  gui                     Interfaccia grafica (Tkinter)
  daemon [--background] [--debug]   Avvia demone curva automatica
  install-service         Installa e avvia systemd service
  uninstall-service       Ferma e rimuove systemd service
  status                  Stato service + log
  profile list            Elenca profili disponibili
  profile switch <nome>   Cambia profilo attivo
  profile show            Mostra dettagli profilo attivo
  profile export <nome> <file>  Esporta profilo in JSON
  profile import <file>       Importa profilo da JSON
   monitor                 Monitoraggio continuo (5s refresh)
   gpu-info                Mostra stato termico GPU (Radeon VII)

Profili predefiniti: silent, quiet_daily, heavy_work, render_mode (cap 4500 RPM, single-CPU sensor mapping).
"""
    )
    parser.add_argument("command", choices=[
        "show", "set", "auto", "gui", "daemon",
        "install-service", "restart-service", "uninstall-service", "status",
        "profile", "monitor", "gpu-info"
    ], help="Comando da eseguire")

    # Sub-args per daemon
    parser.add_argument("--background", action="store_true", help="Avvia daemon in background")
    parser.add_argument("--debug", action="store_true", help="Abilita logging DEBUG level")

    # Sub-args per set
    parser.add_argument("fan", nargs="?", help="Numero ventola o 'all'")
    parser.add_argument("rpm", type=int, nargs="?", help="RPM target")

    args = parser.parse_args()

    cmd = args.command

    if cmd == "show":
        show_fans()
        show_temps()

    elif cmd == "set":
        if not args.fan or args.rpm is None:
            print("Uso: macpro-fan.py set <fan#|all> <rpm>")
            sys.exit(1)
        require_root()
        try:
            if args.fan == "all":
                set_all_fans(args.rpm)
            else:
                set_fan(int(args.fan), args.rpm)
        except FanError as e:
            print(f"ERRORE: {e}")
            sys.exit(1)

    elif cmd == "auto":
        require_root()
        auto()

    elif cmd == "gui":
        from fanctrl.gui import cmd_gui
        cmd_gui()

    elif cmd == "daemon":
        if args.background:
            cmd_daemon_bg()
        else:
            cmd_daemon(debug=args.debug)

    elif cmd == "install-service":
        cmd_install_service()

    elif cmd == "uninstall-service":
        cmd_uninstall_service()

    elif cmd == "restart-service":
        cmd_service_restart()

    elif cmd == "status":
        cmd_status()

    elif cmd == "profile":
        if len(sys.argv) < 3:
            print("Uso: macpro-fan.py profile list|switch <nome>|show|export <file>|import <file>")
            sys.exit(1)
        subcmd = sys.argv[2]
        if subcmd == "list":
            cmd_profile_list()
        elif subcmd == "switch":
            if len(sys.argv) != 4:
                print("Uso: macpro-fan.py profile switch <nome>")
                sys.exit(1)
            require_root()
            switch_profile(sys.argv[3])
        elif subcmd == "show":
            cmd_profile_show()
        elif subcmd == "export":
            if len(sys.argv) != 4:
                print("Uso: macpro-fan.py profile export <nome> <file>")
                sys.exit(1)
            export_profile(sys.argv[3], sys.argv[4])
        elif subcmd == "import":
            if len(sys.argv) != 3:
                print("Uso: macpro-fan.py profile import <file>")
                sys.exit(1)
            import_profile(sys.argv[3])
        else:
            print("Uso: macpro-fan.py profile list|switch <nome>|show|export <file>|import <file>")
            sys.exit(1)

    elif cmd == "monitor":
        cmd_monitor()

    elif cmd == "gpu-info":
        all_temps = get_all_temps()
        gpu_keys = ["TeGG", "TeGP", "TeRG", "TeRP", "Te1P", "Te1F", "Te1S", "Te2P", "Te2F", "Te2S", "Te3P", "Te3F", "Te3S", "Te4P", "Te4F", "Te4S", "Te5P", "Te5F", "Te5S"]
        print("GPU (Radeon VII) Sensori:")
        print(f"{'Sensore':<8} {'Temp °C':>7} {'Descrizione':<30}")
        print("-" * 45)
        for key in gpu_keys:
            temp = all_temps.get(key)
            desc = TEMP_LABELS.get(key, key)
            if temp is not None:
                status = "OK" if temp < 60 else ("WARN" if temp <= 75 else "CRIT")
                print(f"{key:<8} {temp:>7}°C  {desc:<30} [{status}]")
            else:
                print(f"{key:<8} {'N/A':>7}  {desc:<30}")


if __name__ == "__main__":
    main()
