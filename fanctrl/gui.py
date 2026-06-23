import os
import signal
import subprocess
import sys
import time

from fanctrl import CONFIG_PATH
from fanctrl.sensors import get_all_temps, group_temps, TEMP_LABELS, TEMP_GROUPS, GPU_SENSOR_KEYS
from fanctrl.fan import get_fan_info, get_fan_count, set_fan, set_all_fans, auto, FanError
from fanctrl.config import load_config, list_profiles, switch_profile, get_active_profile
from fanctrl.utils import require_root, is_daemon_running, get_script_path, read_pidfile, remove_pidfile

try:
    import tkinter as tk
    import tkinter.font as tkfont
    from tkinter import ttk
    _TK_AVAILABLE = True
except ImportError:
    _TK_AVAILABLE = False


class FanControlGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("MacPro 5.1 Fan Control")
        self.root.resizable(True, True)

        self.config = load_config()
        self.profile_names = list_profiles()

        families = tkfont.families()
        mono_family = next((f for f in ["DejaVu Sans Mono", "Liberation Mono", "Courier New", "Courier"] if f in families), "Courier")
        sans_family = next((f for f in ["DejaVu Sans", "Liberation Sans", "Arial", "Helvetica"] if f in families), "Helvetica")

        style = ttk.Style()
        for t in ["clam", "alt", "default"]:
            if t in style.theme_names():
                style.theme_use(t)
                break
        style.configure(".", font=(sans_family, 13))
        style.configure("Treeview", font=(mono_family, 14), rowheight=36)
        style.configure("Treeview.Heading", font=(sans_family, 13, "bold"))
        style.configure("TLabel", font=(sans_family, 13))
        style.configure("TButton", font=(sans_family, 13))
        style.configure("TEntry", font=(sans_family, 13))
        style.configure("TCombobox", font=(sans_family, 13))
        style.configure("Bold.TLabel", font=(sans_family, 13, "bold"))
        style.configure("Status.TLabel", font=(sans_family, 13))
        style.configure("Header.TLabel", font=(sans_family, 18, "bold"))
        style.configure("Title.TLabel", font=(sans_family, 15, "bold"))
        style.map("Treeview.tag_safe", foreground=[("active", "green")])
        style.map("Treeview.tag_warn", foreground=[("active", "#FFA500")])
        style.map("Treeview.tag_danger", foreground=[("active", "red")])

        self._build_widgets()
        self._refresh_loop()

    def _build_widgets(self):
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        header = ttk.Label(main, text="MacPro 5.1 Fan Control",
                           style="Header.TLabel")
        header.pack(pady=(0, 14))

        columns = ("label", "rpm", "min_rpm", "max_rpm", "mode")
        self.tree = ttk.Treeview(main, columns=columns, show="headings",
                                 height=8)
        self.tree.heading("label", text="Ventola")
        self.tree.heading("rpm", text="RPM")
        self.tree.heading("min_rpm", text="Min")
        self.tree.heading("max_rpm", text="Max")
        self.tree.heading("mode", text="Modo")

        self.tree.column("label", width=130)
        self.tree.column("rpm", width=110, anchor=tk.CENTER)
        self.tree.column("min_rpm", width=100, anchor=tk.CENTER)
        self.tree.column("max_rpm", width=100, anchor=tk.CENTER)
        self.tree.column("mode", width=90, anchor=tk.CENTER)

        self.tree.pack(fill=tk.BOTH, pady=(0, 12))

        columns = ("key", "temp", "desc")
        self.sensor_tree = ttk.Treeview(main, columns=columns, show="headings", height=10)
        self.sensor_tree.heading("key", text="Sensore")
        self.sensor_tree.heading("temp", text="Temp °C")
        self.sensor_tree.heading("desc", text="Descrizione")

        self.sensor_tree.column("key", width=80, anchor=tk.CENTER)
        self.sensor_tree.column("temp", width=120, anchor=tk.CENTER)
        self.sensor_tree.column("desc", width=300, anchor=tk.W)

        self.sensor_tree.pack(fill=tk.BOTH, pady=(0, 12))

        ctrl = ttk.Frame(main)
        ctrl.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(ctrl, text="Ventola #:").grid(row=0, column=0, padx=4, pady=2)
        self.fan_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self.fan_var, width=4).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(ctrl, text="RPM:").grid(row=0, column=2, padx=4, pady=2)
        self.rpm_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self.rpm_var, width=6).grid(row=0, column=3, padx=4, pady=2)
        ttk.Button(ctrl, text="Set", command=self._set_single).grid(row=0, column=4, padx=6, pady=2)

        ttk.Label(ctrl, text="Tutte RPM:").grid(row=0, column=5, padx=(18, 4), pady=2)
        self.all_rpm_var = tk.StringVar()
        ttk.Entry(ctrl, textvariable=self.all_rpm_var, width=6).grid(row=0, column=6, padx=4, pady=2)
        ttk.Button(ctrl, text="Set Tutte", command=self._set_all).grid(row=0, column=7, padx=6, pady=2)

        ttk.Button(ctrl, text="Auto", command=self._set_auto).grid(row=0, column=8, padx=(18, 4), pady=2)
        self.profile_btn = ttk.Button(ctrl, text="Start Profili",
                                      command=self._toggle_profile_daemon)
        self.profile_btn.grid(row=0, column=9, padx=4, pady=2)

        sep = ttk.Separator(main, orient=tk.HORIZONTAL)
        sep.pack(fill=tk.X, pady=(0, 10))

        profile_frame = ttk.Frame(main)
        profile_frame.pack(fill=tk.X, pady=(0, 12))

        ttk.Label(profile_frame, text="Profilo:", style="Bold.TLabel").pack(side=tk.LEFT, padx=(0, 8))
        self.profile_var = tk.StringVar()
        self.profile_combo = ttk.Combobox(profile_frame, textvariable=self.profile_var,
                                          values=self.profile_names, state="readonly", width=14)
        self.profile_combo.pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(profile_frame, text="Applica", command=self._apply_profile).pack(side=tk.LEFT)

        self.status_var = tk.StringVar()
        status_bar = ttk.Label(main, textvariable=self.status_var,
                               relief=tk.SUNKEN, anchor=tk.W,
                               style="Status.TLabel")
        status_bar.pack(fill=tk.X, pady=(0, 6))

        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill=tk.X)
        ttk.Button(btn_frame, text="Esci", command=self.root.destroy).pack(side=tk.RIGHT)

    def _refresh_loop(self):
        """Refresh loop resilient con wrapper try/except."""
        try:
            fans = get_fan_info()
            all_temps = get_all_temps()
            groups = group_temps(all_temps)
            pid_on = is_daemon_running()
            profile_name = get_active_profile()

            for row in self.tree.get_children():
                self.tree.delete(row)
            for f in fans:
                mode = "MAN" if f["manual"] else "AUTO"
                self.tree.insert("", tk.END, values=(
                    f["label"], f["rpm"], f["min"], f["max"], mode
                ))

            for row in self.sensor_tree.get_children():
                self.sensor_tree.delete(row)

            ambient_temp = all_temps.get("TA0P")
            if ambient_temp is not None:
                tag = "safe" if ambient_temp < 40 else ("warn" if ambient_temp <= 60 else "danger")
                self.sensor_tree.insert("", tk.END, values=("AMB", f"{ambient_temp}°C", "Ambient"), tags=(tag,), open=True)

            for cat_name in ["CPU", "GPU", "MCP", "HDD", "PWR", "MEM", "PCIe"]:
                keys = TEMP_GROUPS.get(cat_name, [])
                max_temp = groups.get(cat_name)
                if max_temp is None:
                    continue
                if cat_name == "GPU":
                    tag = "safe" if max_temp < 60 else ("warn" if max_temp <= 75 else "danger")
                else:
                    tag = "safe" if max_temp < 40 else ("warn" if max_temp <= 60 else "danger")
                cat_id = self.sensor_tree.insert("", tk.END, values=(cat_name, f"{max_temp}°C", ""), tags=(tag,), open=False)
                for key in keys:
                    temp = all_temps.get(key)
                    if temp is None:
                        continue
                    desc = TEMP_LABELS.get(key, key)
                    if cat_name == "GPU" and key in GPU_SENSOR_KEYS:
                        child_tag = "safe" if temp < 60 else ("warn" if temp <= 75 else "danger")
                    else:
                        child_tag = "safe" if temp < 40 else ("warn" if temp <= 60 else "danger")
                    self.sensor_tree.insert(cat_id, tk.END, values=(key, f"{temp}°C", desc), tags=(child_tag,))

            # GPU idle/load detection
            gpu_temps = [all_temps.get(k) for k in ["TeGG", "TeRG"] if all_temps.get(k) is not None]
            if gpu_temps:
                max_gpu_temp = max(gpu_temps)
                if max_gpu_temp > 45:
                    gpu_status = "CARICO"
                elif max_gpu_temp > 30:
                    gpu_status = "IDLE"
                else:
                    gpu_status = "OFF"
            else:
                gpu_status = "N/A"

            pid_str = "ON" if pid_on else "OFF"
            self.status_var.set(f"Profilo: {profile_name}  |  PID: {pid_str}  |  GPU: {gpu_status}")

            self.profile_btn.config(text="Stop Profili" if pid_on else "Start Profili")

            self.profile_names = list_profiles()
            self.profile_combo["values"] = self.profile_names
            if profile_name in self.profile_names:
                self.profile_var.set(profile_name)

        except Exception as e:
            self.status_var.set(f"Errore refresh: {e}")
        finally:
            self.root.after(5000, self._refresh_loop)

    def _apply_profile(self):
        name = self.profile_var.get()
        if name:
            result = switch_profile(name)
            if result:
                self.status_var.set(f"Profilo cambiato a: {name}")

    def _check_root(self):
        if os.geteuid() != 0:
            self.status_var.set("Errore: esegui la GUI con sudo")
            return False
        return True

    def _set_single(self):
        if not self._check_root():
            return
        try:
            fan = int(self.fan_var.get())
            rpm = int(self.rpm_var.get())
        except ValueError:
            self.status_var.set("Errore: inserisci numeri validi")
            return
        # Validazione RPM contro range ventola
        fans = get_fan_info()
        for f in fans:
            if f["num"] == fan:
                if rpm < f["min"] or rpm > f["max"]:
                    self.status_var.set(f"RPM {rpm} fuori range [{f['min']}, {f['max']}] per {f['label']}")
                    return
                break
        else:
            self.status_var.set(f"Errore: ventola #{fan} non trovata")
            return
        if rpm < 0:
            self.status_var.set("Errore: RPM deve essere positivo")
            return
        if is_daemon_running():
            self._stop_daemon()
        try:
            set_fan(fan, rpm)
            self.status_var.set(f"Fan {fan} → {rpm} RPM")
        except FanError as e:
            self.status_var.set(f"Errore: {e}")

    def _set_all(self):
        if not self._check_root():
            return
        try:
            rpm = int(self.all_rpm_var.get())
        except ValueError:
            self.status_var.set("Errore: inserisci un numero valido")
            return
        if rpm < 0:
            self.status_var.set("Errore: RPM deve essere positivo")
            return
        # Validazione contro ventola con min più alto
        fans = get_fan_info()
        max_min = max((f["min"] for f in fans), default=0)
        if rpm < max_min:
            self.status_var.set(f"RPM {rpm} troppo basso (min sistema: {max_min})")
            return
        if is_daemon_running():
            self._stop_daemon()
        try:
            set_all_fans(rpm)
            self.status_var.set(f"Tutte → {rpm} RPM")
        except FanError as e:
            self.status_var.set(f"Errore: {e}")

    def _stop_daemon(self):
        pid = read_pidfile()
        if pid:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
            remove_pidfile()
        time.sleep(0.3)
        r = subprocess.run(["systemctl", "stop", "macpro-fan"],
                            capture_output=True, timeout=10)
        if not is_daemon_running():
            self.profile_btn.config(text="Start Profili")
            self.status_var.set("Profili fermati")
        else:
            self.status_var.set("Errore: impossibile fermare il demone")

    def _set_auto(self):
        if not self._check_root():
            return
        if is_daemon_running():
            self._stop_daemon()
        auto()
        self.status_var.set("Ventole in automatico")

    def _toggle_profile_daemon(self):
        if is_daemon_running():
            self._stop_daemon()
        else:
            if os.geteuid() != 0:
                self.status_var.set("Errore: esegui la GUI con sudo per avviare i profili")
                return
            script = get_script_path()
            cmd = [sys.executable, script, "daemon", "--background"]
            proc = subprocess.Popen(cmd)
            time.sleep(0.5)
            if proc.poll() is not None and proc.poll() != 0:
                self.status_var.set(f"Errore avvio profili (exit code {proc.poll()})")
            else:
                time.sleep(0.5)
                if is_daemon_running():
                    self.profile_btn.config(text="Stop Profili")
                    self.status_var.set("Profili avviati in background")
                else:
                    self.status_var.set("Profili non partiti - controlla i log")


def cmd_gui():
    if not _TK_AVAILABLE:
        print("ERRORE: Tkinter non disponibile.")
        print()
        print("  Per usare l'interfaccia grafica installa python3-tk:")
        print()
        print("    Debian/Ubuntu:  sudo apt install python3-tk")
        print("    Fedora:         sudo dnf install python3-tkinter")
        print("    Arch:           sudo pacman -S tk")
        print()
        sys.exit(1)
    root = tk.Tk()
    FanControlGUI(root)
    root.mainloop()
