# Setup Widget

Widget de métricas do PC para a área de trabalho do Windows: CPU, GPU, RAM, discos, ventoinhas e rede, atualizado a cada segundo. Fica atrás das janelas, como parte do desktop, e não aparece na barra de tarefas.

Feito em Python (tkinter) com [LibreHardwareMonitor](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor) para ler os sensores e o driver [PawnIO](https://pawnio.eu/) para acesso ao hardware.

## O que mostra

| Seção | Métricas |
|---|---|
| CPU | uso (barra + histórico), temperatura, clock, potência |
| GPU | uso, temperatura, hot spot, VRAM, ventoinha, potência, clock |
| Memória | RAM usada / total |
| Discos | uso por partição e temperatura de cada SSD/HD |
| Ventoinhas | RPM das ventoinhas da placa-mãe |
| Rede | download / upload |

As cores mudam de verde para laranja e vermelho conforme uso ou temperatura sobem.

Testado em: Ryzen 5 5600X, Radeon RX 6600, ASUS B550-F, Windows 11. Deve funcionar com Intel/NVIDIA também, pois o LibreHardwareMonitor cobre ambos.

## Instalação

Requisitos: Windows 10/11 e [Python 3.10+](https://www.python.org/downloads/) (marque "Add to PATH").

```powershell
git clone https://github.com/fotografiamiller7/setup-widget.git
cd setup-widget
powershell -ExecutionPolicy Bypass -File setup.ps1
```

O `setup.ps1` instala `pythonnet` e `psutil`, baixa as DLLs do LibreHardwareMonitor do NuGet para a pasta `lib/` e instala o driver PawnIO pelo winget (pede permissão de administrador).

## Uso

- Abra com **Iniciar Widget.vbs** (pede UAC: a temperatura da CPU e as ventoinhas só são lidas como administrador).
- Para abrir sozinho no logon, sem UAC a cada boot: execute `instalar_inicializacao.ps1` (cria a tarefa agendada `SetupWidget`). `remover_inicializacao.ps1` desfaz.
- **Arraste** com o botão esquerdo; a posição é salva.
- **Botão direito** abre o menu: sempre no topo, opacidade, tamanho, resetar posição, fechar.

## Personalizar

Edite `config.json` (criado após o primeiro uso) ou `DEFAULT_CFG` em `widget.py`:

- `interval_ms`: intervalo de atualização.
- `show`: liga/desliga seções (`cpu`, `gpu`, `ram`, `disk`, `fans`, `net`).
- Cores e fontes ficam no topo da seção "Interface" em `widget.py`.

## Diagnóstico

```powershell
python sensores_teste.py
```

Lista todos os sensores detectados. Sem admin, a temperatura da CPU, as ventoinhas e a temperatura dos discos aparecem zeradas ou ausentes.

## Licença

MIT. O LibreHardwareMonitor é MPL 2.0 e o PawnIO é um projeto separado com licença própria.
