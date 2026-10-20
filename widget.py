"""
Setup Widget - painel de métricas do PC na área de trabalho.

Mostra CPU (uso, temperatura, clock, potência), GPU (uso, temperatura, VRAM,
ventoinha, potência), RAM, discos e rede. Fica sempre atrás das outras janelas,
como um widget de desktop. Arraste com o botão esquerdo; botão direito abre o menu.

Para ler a temperatura da CPU e sensores da placa-mãe é preciso executar como
administrador (use "Iniciar Widget.vbs" ou a tarefa agendada criada por
instalar_inicializacao.ps1) e ter o driver PawnIO instalado.
"""
import ctypes
import json
import os
import sys
import time
import tkinter as tk
from collections import deque

import psutil

BASE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(BASE, "lib")
CFG_PATH = os.path.join(BASE, "config.json")

# ----------------------------------------------------------------------------
# Configuração
# ----------------------------------------------------------------------------
DEFAULT_CFG = {
    "x": None, "y": None,            # posição (None = canto superior direito)
    "opacity": 0.88,
    "interval_ms": 1000,
    "always_on_top": False,
    "scale": 1.0,
    "show": {"cpu": True, "gpu": True, "ram": True, "disk": True, "fans": True, "net": True},
}


def load_cfg():
    cfg = dict(DEFAULT_CFG)
    try:
        with open(CFG_PATH, "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_cfg(cfg):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


# ----------------------------------------------------------------------------
# Sensores (LibreHardwareMonitor via pythonnet) com fallback para psutil
# ----------------------------------------------------------------------------
class Sensores:
    def __init__(self):
        self.ok = False
        self.pc = None
        self.erro = ""
        try:
            import clr  # pythonnet
            sys.path.append(LIB)
            clr.AddReference(os.path.join(LIB, "LibreHardwareMonitorLib.dll"))
            from LibreHardwareMonitor.Hardware import Computer
            pc = Computer()
            pc.IsCpuEnabled = True
            pc.IsGpuEnabled = True
            pc.IsMemoryEnabled = True
            pc.IsMotherboardEnabled = True
            pc.IsStorageEnabled = True
            pc.IsNetworkEnabled = False
            pc.Open()
            self.pc = pc
            self.ok = True
        except Exception as e:  # noqa: BLE001
            self.erro = str(e)
        self._net_prev = (psutil.net_io_counters(), time.time())

    def _coletar(self, hw, out):
        hw.Update()
        tipo = str(hw.HardwareType)
        for s in hw.Sensors:
            v = s.Value
            if v is None:
                continue
            out.append((tipo, str(hw.Name), str(s.SensorType), str(s.Name), float(v)))
        for sub in hw.SubHardware:
            self._coletar(sub, out)

    def ler(self):
        d = {
            "cpu_load": None, "cpu_temp": None, "cpu_clock": None, "cpu_power": None,
            "gpu_name": "", "gpu_load": None, "gpu_temp": None, "gpu_hot": None,
            "gpu_fan": None, "gpu_power": None, "gpu_clock": None,
            "vram_used": None, "vram_total": None,
            "ram_used": None, "ram_total": None, "ram_pct": None,
            "mb_temp": None, "fans": [], "disks": [],
            "net_up": 0.0, "net_down": 0.0,
        }
        lhm = []
        if self.ok:
            try:
                for hw in self.pc.Hardware:
                    self._coletar(hw, lhm)
            except Exception:  # noqa: BLE001
                pass

        disk_temps = {}
        for tipo, hwname, stype, sname, v in lhm:
            if tipo == "Cpu":
                if stype == "Load" and sname == "CPU Total":
                    d["cpu_load"] = v
                elif stype == "Temperature" and ("Tctl" in sname or "Package" in sname or sname == "CPU Package"):
                    if v > 0:
                        d["cpu_temp"] = v
                elif stype == "Temperature" and d["cpu_temp"] is None and v > 0 and "Core" in sname:
                    d["cpu_temp"] = v
                elif stype == "Clock" and "Average" in sname and "Effective" not in sname and v > 0:
                    d["cpu_clock"] = v
                elif stype == "Clock" and d["cpu_clock"] is None and sname.startswith("Core #1") and "Effective" not in sname and v > 0:
                    d["cpu_clock"] = v
                elif stype == "Power" and sname == "Package" and v > 0:
                    d["cpu_power"] = v
            elif tipo.startswith("Gpu"):
                d["gpu_name"] = hwname
                if stype == "Load" and sname == "GPU Core":
                    d["gpu_load"] = v
                elif stype == "Temperature" and sname == "GPU Core":
                    d["gpu_temp"] = v
                elif stype == "Temperature" and "Hot Spot" in sname:
                    d["gpu_hot"] = v
                elif stype == "Fan" and "GPU" in sname:
                    d["gpu_fan"] = v
                elif stype == "Power" and ("Package" in sname or sname == "GPU Power"):
                    d["gpu_power"] = v
                elif stype == "Clock" and sname == "GPU Core":
                    d["gpu_clock"] = v
                elif stype == "SmallData" and sname == "GPU Memory Used":
                    d["vram_used"] = v
                elif stype == "SmallData" and sname == "GPU Memory Total":
                    d["vram_total"] = v
            elif tipo == "Motherboard" or tipo == "SuperIO":
                if stype == "Temperature" and d["mb_temp"] is None and v > 0 and ("Motherboard" in sname or "System" in sname):
                    d["mb_temp"] = v
                elif stype == "Temperature" and sname.startswith("CPU") and d["cpu_temp"] is None and v > 0:
                    d["cpu_temp"] = v
                elif stype == "Fan" and v > 0:
                    d["fans"].append((sname, v))
            elif tipo == "Storage":
                if stype == "Temperature" and v > 0 and "Warning" not in sname and "Critical" not in sname:
                    disk_temps.setdefault(hwname, v)

        # psutil: fallback e complementos
        if d["cpu_load"] is None:
            d["cpu_load"] = psutil.cpu_percent(interval=None)
        if d["cpu_clock"] is None:
            try:
                d["cpu_clock"] = psutil.cpu_freq().current
            except Exception:  # noqa: BLE001
                pass
        vm = psutil.virtual_memory()
        d["ram_used"] = vm.used / 2**30
        d["ram_total"] = vm.total / 2**30
        d["ram_pct"] = vm.percent

        # discos
        for p in psutil.disk_partitions(all=False):
            if "fixed" not in p.opts.lower() and p.fstype == "":
                continue
            try:
                u = psutil.disk_usage(p.mountpoint)
            except Exception:  # noqa: BLE001
                continue
            d["disks"].append((p.device.rstrip("\\"), u.used / 2**30, u.total / 2**30, u.percent))
        d["disk_temps"] = disk_temps

        # rede
        now = time.time()
        cur = psutil.net_io_counters()
        prev, t0 = self._net_prev
        dt = max(now - t0, 1e-3)
        d["net_up"] = (cur.bytes_sent - prev.bytes_sent) / dt
        d["net_down"] = (cur.bytes_recv - prev.bytes_recv) / dt
        self._net_prev = (cur, now)
        return d

    def fechar(self):
        try:
            if self.pc:
                self.pc.Close()
        except Exception:  # noqa: BLE001
            pass


# ----------------------------------------------------------------------------
# Utilidades Win32 (manter o widget atrás das janelas, sem aparecer na barra)
# ----------------------------------------------------------------------------
user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
HWND_BOTTOM = 1
HWND_NOTOPMOST = -2
HWND_TOPMOST = -1
SWP_NOMOVE, SWP_NOSIZE, SWP_NOACTIVATE = 0x0002, 0x0001, 0x0010


def hwnd_de(root):
    return user32.GetParent(root.winfo_id()) or root.winfo_id()


def esconder_da_barra(root):
    h = hwnd_de(root)
    st = user32.GetWindowLongW(h, GWL_EXSTYLE)
    st = (st | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
    user32.SetWindowLongW(h, GWL_EXSTYLE, st)


def mandar_para_fundo(root):
    user32.SetWindowPos(hwnd_de(root), HWND_BOTTOM, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def mandar_para_topo(root, topo):
    user32.SetWindowPos(hwnd_de(root), HWND_TOPMOST if topo else HWND_NOTOPMOST, 0, 0, 0, 0,
                        SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


# ----------------------------------------------------------------------------
# Interface
# ----------------------------------------------------------------------------
BG = "#0f1115"
BG2 = "#171a21"
FG = "#e6e6e6"
DIM = "#8a8f98"
ACC = "#4cc2ff"
OK = "#53d769"
WARN = "#ffb347"
HOT = "#ff5c5c"
FONT = "Segoe UI"
MONO = "Consolas"


def cor_por_pct(p):
    if p is None:
        return DIM
    return OK if p < 60 else WARN if p < 85 else HOT


def cor_por_temp(t, hot=85, warn=70):
    if t is None:
        return DIM
    return OK if t < warn else WARN if t < hot else HOT


def fmt_bytes_s(b):
    if b >= 1024**2:
        return f"{b/1024**2:5.1f} MB/s"
    if b >= 1024:
        return f"{b/1024:5.0f} KB/s"
    return f"{b:5.0f}  B/s"


class Barra(tk.Canvas):
    """Barra horizontal de progresso com histórico (sparkline)."""

    def __init__(self, master, width=220, height=10, **kw):
        super().__init__(master, width=width, height=height, bg=BG2, highlightthickness=0, **kw)
        self.w, self.h = width, height
        self.hist = deque(maxlen=60)

    def set(self, pct, cor):
        self.delete("all")
        pct = 0 if pct is None else max(0, min(100, pct))
        self.hist.append(pct)
        # sparkline de fundo
        n = len(self.hist)
        if n > 1:
            pts = []
            for i, v in enumerate(self.hist):
                x = self.w * i / (self.hist.maxlen - 1)
                y = self.h - (self.h * v / 100)
                pts += [x, y]
            self.create_line(*pts, fill="#2b3240", width=1)
        self.create_rectangle(0, 0, self.w * pct / 100, self.h, fill=cor, outline="")


class Widget:
    def __init__(self):
        self.cfg = load_cfg()
        self.sens = Sensores()
        self.root = tk.Tk()
        r = self.root
        r.title("Setup Widget")
        r.overrideredirect(True)
        r.configure(bg=BG)
        r.attributes("-alpha", self.cfg["opacity"])
        self.scale = float(self.cfg.get("scale", 1.0))
        r.tk.call("tk", "scaling", 1.33 * self.scale)

        self.frame = tk.Frame(r, bg=BG, padx=14, pady=10)
        self.frame.pack()
        self._construir()

        # drag
        self._drag = None
        for w in (r, self.frame):
            w.bind("<ButtonPress-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)
            w.bind("<ButtonRelease-1>", self._drag_end)
            w.bind("<Button-3>", self._menu)
        self._bind_filhos(self.frame)

        r.update_idletasks()
        self._posicionar()
        esconder_da_barra(r)
        self._aplicar_camada()
        # reaplica a posição depois que o Windows terminar de mapear a janela
        r.after(150, self._posicionar)
        r.after(600, self._posicionar)
        self._tick()

    # --- construção ---------------------------------------------------------
    def _bind_filhos(self, w):
        for c in w.winfo_children():
            c.bind("<ButtonPress-1>", self._drag_start)
            c.bind("<B1-Motion>", self._drag_move)
            c.bind("<ButtonRelease-1>", self._drag_end)
            c.bind("<Button-3>", self._menu)
            self._bind_filhos(c)

    def _titulo(self, txt):
        f = tk.Frame(self.frame, bg=BG)
        f.pack(fill="x", pady=(8, 2))
        tk.Label(f, text=txt, bg=BG, fg=ACC, font=(FONT, 9, "bold")).pack(side="left")
        tk.Frame(f, bg="#262b36", height=1).pack(side="left", fill="x", expand=True, padx=(8, 0), pady=6)
        return f

    def _linha(self, master, esquerda, direita="", fg=FG, mono=True):
        f = tk.Frame(master, bg=BG)
        f.pack(fill="x")
        a = tk.Label(f, text=esquerda, bg=BG, fg=DIM, font=(FONT, 9), anchor="w")
        a.pack(side="left")
        b = tk.Label(f, text=direita, bg=BG, fg=fg, font=(MONO if mono else FONT, 10, "bold"), anchor="e")
        b.pack(side="right")
        return a, b

    def _construir(self):
        show = self.cfg["show"]
        cab = tk.Frame(self.frame, bg=BG)
        cab.pack(fill="x")
        tk.Label(cab, text="◉ SETUP", bg=BG, fg=FG, font=(FONT, 11, "bold")).pack(side="left")
        self.lbl_hora = tk.Label(cab, text="", bg=BG, fg=DIM, font=(MONO, 10))
        self.lbl_hora.pack(side="right")

        if show["cpu"]:
            self._titulo("CPU · Ryzen 5 5600X")
            self.barra_cpu = Barra(self.frame)
            self.barra_cpu.pack(fill="x", pady=(2, 4))
            _, self.cpu_uso = self._linha(self.frame, "Uso")
            _, self.cpu_temp = self._linha(self.frame, "Temperatura")
            _, self.cpu_clock = self._linha(self.frame, "Clock")
            _, self.cpu_pow = self._linha(self.frame, "Potência")

        if show["gpu"]:
            self.tit_gpu = self._titulo("GPU · Radeon RX 6600")
            self.barra_gpu = Barra(self.frame)
            self.barra_gpu.pack(fill="x", pady=(2, 4))
            _, self.gpu_uso = self._linha(self.frame, "Uso")
            _, self.gpu_temp = self._linha(self.frame, "Temperatura")
            _, self.gpu_hot = self._linha(self.frame, "Hot spot")
            _, self.gpu_vram = self._linha(self.frame, "VRAM")
            _, self.gpu_fan = self._linha(self.frame, "Ventoinha")
            _, self.gpu_pow = self._linha(self.frame, "Potência / Clock")

        if show["ram"]:
            self._titulo("MEMÓRIA")
            self.barra_ram = Barra(self.frame)
            self.barra_ram.pack(fill="x", pady=(2, 4))
            _, self.ram_txt = self._linha(self.frame, "RAM")

        if show["disk"]:
            self._titulo("DISCOS")
            self.disk_frame = tk.Frame(self.frame, bg=BG)
            self.disk_frame.pack(fill="x")
            self.disk_rows = {}
            self.disk_temp_rows = {}

        if show.get("fans", True):
            self.tit_fans = self._titulo("VENTOINHAS")
            self.fan_frame = tk.Frame(self.frame, bg=BG)
            self.fan_frame.pack(fill="x")
            self.fan_rows = {}
            self.fan_vazio = tk.Label(self.fan_frame, text="(requer admin)", bg=BG, fg=DIM, font=(FONT, 8))
            self.fan_vazio.pack(anchor="w")

        if show["net"]:
            self._titulo("REDE")
            _, self.net_down = self._linha(self.frame, "↓ Download")
            _, self.net_up = self._linha(self.frame, "↑ Upload")

        self.lbl_aviso = tk.Label(self.frame, text="", bg=BG, fg=WARN, font=(FONT, 8), wraplength=230, justify="left")
        self.lbl_aviso.pack(fill="x", pady=(6, 0))
        if not self.sens.ok:
            self.lbl_aviso.config(text="Sensores indisponíveis (LibreHardwareMonitor): " + self.sens.erro[:120])
        elif not is_admin():
            self.lbl_aviso.config(text="Sem admin: temperatura da CPU e sensores da placa-mãe ficam indisponíveis. "
                                       "Abra pelo 'Iniciar Widget.vbs'.")

    # --- posição / camada ---------------------------------------------------
    def _posicionar(self):
        r = self.root
        w, h = r.winfo_width(), r.winfo_height()
        sw = r.winfo_screenwidth()
        x = self.cfg["x"] if self.cfg["x"] is not None else sw - w - 24
        y = self.cfg["y"] if self.cfg["y"] is not None else 24
        r.geometry(f"+{int(x)}+{int(y)}")
        user32.SetWindowPos(hwnd_de(r), 0, int(x), int(y), 0, 0, SWP_NOSIZE | SWP_NOACTIVATE | 0x0004)

    def _aplicar_camada(self):
        if self.cfg["always_on_top"]:
            self.root.attributes("-topmost", True)
            mandar_para_topo(self.root, True)
        else:
            self.root.attributes("-topmost", False)
            mandar_para_topo(self.root, False)
            mandar_para_fundo(self.root)

    # --- drag ---------------------------------------------------------------
    def _drag_start(self, e):
        self._drag = (e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y())

    def _drag_move(self, e):
        if self._drag:
            self.root.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _drag_end(self, _e):
        self._drag = None
        self.cfg["x"], self.cfg["y"] = self.root.winfo_x(), self.root.winfo_y()
        save_cfg(self.cfg)

    # --- menu ---------------------------------------------------------------
    def _menu(self, e):
        m = tk.Menu(self.root, tearoff=0, bg=BG2, fg=FG, activebackground=ACC, activeforeground="#000")
        m.add_checkbutton(label="Sempre no topo", onvalue=True, offvalue=False,
                          variable=tk.BooleanVar(value=self.cfg["always_on_top"]), command=self._toggle_topo)
        op = tk.Menu(m, tearoff=0, bg=BG2, fg=FG)
        for v in (0.6, 0.75, 0.88, 1.0):
            op.add_command(label=f"{int(v*100)}%", command=lambda v=v: self._set_opacidade(v))
        m.add_cascade(label="Opacidade", menu=op)
        esc = tk.Menu(m, tearoff=0, bg=BG2, fg=FG)
        for v in (0.85, 1.0, 1.15, 1.3):
            esc.add_command(label=f"{int(v*100)}%", command=lambda v=v: self._set_escala(v))
        m.add_cascade(label="Tamanho", menu=esc)
        m.add_command(label="Resetar posição", command=self._reset_pos)
        m.add_separator()
        m.add_command(label="Abrir pasta do widget", command=lambda: os.startfile(BASE))
        m.add_command(label="Fechar", command=self.fechar)
        m.tk_popup(e.x_root, e.y_root)

    def _toggle_topo(self):
        self.cfg["always_on_top"] = not self.cfg["always_on_top"]
        save_cfg(self.cfg)
        self._aplicar_camada()

    def _set_opacidade(self, v):
        self.cfg["opacity"] = v
        self.root.attributes("-alpha", v)
        save_cfg(self.cfg)

    def _set_escala(self, v):
        self.cfg["scale"] = v
        save_cfg(self.cfg)
        self.root.destroy()
        os.execl(sys.executable, sys.executable, *sys.argv)

    def _reset_pos(self):
        self.cfg["x"] = self.cfg["y"] = None
        save_cfg(self.cfg)
        self._posicionar()

    # --- atualização --------------------------------------------------------
    def _tick(self):
        try:
            d = self.sens.ler()
            self._render(d)
        except Exception as e:  # noqa: BLE001
            self.lbl_aviso.config(text=f"Erro: {e}"[:160])
        if not self.cfg["always_on_top"]:
            mandar_para_fundo(self.root)
        self.root.after(int(self.cfg["interval_ms"]), self._tick)

    @staticmethod
    def _v(v, fmt, suf=""):
        return "--" if v is None else fmt.format(v) + suf

    def _render(self, d):
        self.lbl_hora.config(text=time.strftime("%H:%M:%S"))
        show = self.cfg["show"]
        if show["cpu"]:
            self.barra_cpu.set(d["cpu_load"], cor_por_pct(d["cpu_load"]))
            self.cpu_uso.config(text=self._v(d["cpu_load"], "{:.0f}", " %"), fg=cor_por_pct(d["cpu_load"]))
            self.cpu_temp.config(text=self._v(d["cpu_temp"], "{:.0f}", " °C"), fg=cor_por_temp(d["cpu_temp"], 90, 75))
            self.cpu_clock.config(text=self._v(d["cpu_clock"], "{:.0f}", " MHz"))
            self.cpu_pow.config(text=self._v(d["cpu_power"], "{:.0f}", " W"))
        if show["gpu"]:
            self.barra_gpu.set(d["gpu_load"], cor_por_pct(d["gpu_load"]))
            self.gpu_uso.config(text=self._v(d["gpu_load"], "{:.0f}", " %"), fg=cor_por_pct(d["gpu_load"]))
            self.gpu_temp.config(text=self._v(d["gpu_temp"], "{:.0f}", " °C"), fg=cor_por_temp(d["gpu_temp"], 90, 75))
            self.gpu_hot.config(text=self._v(d["gpu_hot"], "{:.0f}", " °C"), fg=cor_por_temp(d["gpu_hot"], 105, 90))
            if d["vram_used"] is not None and d["vram_total"]:
                self.gpu_vram.config(text=f"{d['vram_used']/1024:.1f} / {d['vram_total']/1024:.0f} GB")
            else:
                self.gpu_vram.config(text="--")
            self.gpu_fan.config(text=self._v(d["gpu_fan"], "{:.0f}", " RPM"))
            self.gpu_pow.config(text=f"{self._v(d['gpu_power'], '{:.0f}', ' W')}  {self._v(d['gpu_clock'], '{:.0f}', ' MHz')}")
        if show["ram"]:
            self.barra_ram.set(d["ram_pct"], cor_por_pct(d["ram_pct"]))
            self.ram_txt.config(text=f"{d['ram_used']:.1f} / {d['ram_total']:.0f} GB  ({d['ram_pct']:.0f} %)",
                                fg=cor_por_pct(d["ram_pct"]))
        if show["disk"]:
            for dev, used, total, pct in d["disks"]:
                if dev not in self.disk_rows:
                    a, b = self._linha(self.disk_frame, dev)
                    self.disk_rows[dev] = b
                    self._bind_filhos(self.disk_frame)
                self.disk_rows[dev].config(text=f"{used:.0f} / {total:.0f} GB  {pct:.0f} %", fg=cor_por_pct(pct))
            for nome, t in d.get("disk_temps", {}).items():
                if nome not in self.disk_temp_rows:
                    _, b = self._linha(self.disk_frame, nome[:26])
                    self.disk_temp_rows[nome] = b
                    self._bind_filhos(self.disk_frame)
                self.disk_temp_rows[nome].config(text=f"{t:.0f} °C", fg=cor_por_temp(t, 65, 55))
        if show.get("fans", True):
            ativos = [(n, v) for n, v in d["fans"] if v > 0]
            if ativos and self.fan_vazio.winfo_ismapped():
                self.fan_vazio.pack_forget()
            for nome, rpm in ativos:
                if nome not in self.fan_rows:
                    _, b = self._linha(self.fan_frame, nome)
                    self.fan_rows[nome] = b
                    self._bind_filhos(self.fan_frame)
                self.fan_rows[nome].config(text=f"{rpm:.0f} RPM")
        if show["net"]:
            self.net_down.config(text=fmt_bytes_s(d["net_down"]))
            self.net_up.config(text=fmt_bytes_s(d["net_up"]))

    def fechar(self):
        self.sens.fechar()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def instancia_unica():
    """Impede abrir o widget duas vezes (mutex global do Windows)."""
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW(None, False, "Global\\SetupWidget_Instancia")
    return kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


if __name__ == "__main__":
    if not instancia_unica():
        sys.exit(0)
    Widget().run()
