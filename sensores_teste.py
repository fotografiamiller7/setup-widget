"""Teste rápido: lista todos os sensores que o LibreHardwareMonitor consegue ler."""
import os, sys
import clr  # pythonnet

LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib")
sys.path.append(LIB)
clr.AddReference(os.path.join(LIB, "LibreHardwareMonitorLib.dll"))

from LibreHardwareMonitor.Hardware import Computer  # noqa: E402

pc = Computer()
pc.IsCpuEnabled = True
pc.IsGpuEnabled = True
pc.IsMemoryEnabled = True
pc.IsMotherboardEnabled = True
pc.IsStorageEnabled = True
pc.IsNetworkEnabled = False
pc.Open()

def dump(hw, indent=0):
    hw.Update()
    print(" " * indent + f"[{hw.HardwareType}] {hw.Name}")
    for s in hw.Sensors:
        v = s.Value
        print(" " * (indent + 4) + f"{str(s.SensorType):<12} {str(s.Name):<32} {v}")
    for sub in hw.SubHardware:
        dump(sub, indent + 4)

if len(sys.argv) > 1:  # saída para arquivo (útil ao rodar elevado)
    sys.stdout = open(sys.argv[1], "w", encoding="utf-8")
import ctypes
print("ADMIN:", bool(ctypes.windll.shell32.IsUserAnAdmin()))
for hw in pc.Hardware:
    dump(hw)
pc.Close()
sys.stdout.flush()
