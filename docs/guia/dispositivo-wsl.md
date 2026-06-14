# Rodar no dispositivo a partir do WSL

Guia para conectar um aparelho Android físico a uma sessão **WSL 2** (Windows),
compilar o host `android-host/` e instalar/rodar o app no dispositivo. Cobre o
*setup* do **usbipd-win** (passagem de USB para o WSL) e o contorno do `adb` sob
o modo de rede **mirrored** do WSL.

## Pré-requisitos

No **host de build** (WSL):

- Android SDK + NDK. Neste host vivem em `/usr/lib/android-sdk` (não no
  `ANDROID_HOME` obsoleto), então exporte `ANDROID_SDK_ROOT=/usr/lib/android-sdk`.
- JDK 21 (`java -version`).
- Gradle **wrapper 8.11.1** (`android-host/gradlew`) — o Gradle global 9.x é
  incompatível com o AGP 8.7; sempre use o wrapper.
- A *toolchain* Python estagiada (`make toolchain`): CPython 3.14 + wheels +
  `toolchain/dist/`. Veja o [runbook Android](../research/android-runbook.md).

No **aparelho**:

- **Opções do desenvolvedor** → **Depuração USB** ligada.
- Em MIUI/HyperOS (Xiaomi/Redmi/POCO): também ligue **"Instalar via USB"**, senão
  o `adb install` falha com `INSTALL_FAILED_USER_RESTRICTED`.

No **Windows**:

- **usbipd-win** instalado (passo abaixo).

## 1. Instalar o usbipd-win (Windows)

Em um **PowerShell como administrador**:

```powershell
winget install usbipd
```

Se o `winget` não achar, baixe o `.msi` do
[release oficial](https://github.com/dorssel/usbipd-win/releases/latest),
instale e **feche/reabra o PowerShell** (o `PATH` é atualizado).

## 2. Anexar o aparelho ao WSL (Windows)

Com o cabo conectado e a depuração USB ligada, no PowerShell admin:

```powershell
usbipd list
```

```text
Connected:
BUSID  VID:PID    DEVICE                     STATE
1-7    2717:ff08  Redmi 12                   Not shared
...
```

Pegue o `BUSID` do aparelho (ex.: `1-7`), então:

```powershell
usbipd bind --busid 1-7
usbipd attach --wsl --busid 1-7
```

- `bind` só na **primeira vez** (marca o device como compartilhável).
- `attach` toda vez que reconectar o cabo (anexa o device ao WSL).

Confira no WSL que o kernel viu o device:

```bash
dmesg | grep -i "Product:\|SerialNumber:" | tail -3
# usb 1-1: Product: Redmi 12
# usb 1-1: SerialNumber: 0d474c147d75
```

## 3. Contorno do adb sob rede *mirrored*

Sob o modo de rede **mirrored** do WSL 2, `adb start-server` **trava**: o
*handshake* de prontidão do daemon pelo *loopback* `127.0.0.1:5037` não completa
(o `adb devices`/`adb kill-server` ficam pendurados e expiram).

Contorno: suba o servidor **em primeiro plano** (`nodaemon`) como um processo de
fundo persistente e deixe os comandos do cliente conversarem com ele:

```bash
# 1. inicie o servidor em background (deixe rodando):
ANDROID_SDK_ROOT=/usr/lib/android-sdk \
  /usr/lib/android-sdk/platform-tools/adb nodaemon server &

# 2. agora o cliente responde normalmente:
adb devices -l
# List of devices attached
# 0d474c147d75   device  product:fire_global model:23053RN02A ...
```

Se o `adb` ficar preso de novo, mate todos os processos e repita:

```bash
pkill -9 adb
```

## 4. Compilar e instalar

A partir da raiz do repositório:

```bash
export ANDROID_SDK_ROOT=/usr/lib/android-sdk
make apk            # ./gradlew :app:assembleDebug — gera app-debug.apk (~49 MB)
make install        # adb install -r do APK no device
# ou os dois de uma vez:
make apk-install
```

Equivalente cru (com o serial explícito, útil com o servidor `nodaemon`):

```bash
cd android-host && ANDROID_SDK_ROOT=/usr/lib/android-sdk ./gradlew :app:assembleDebug
adb -s 0d474c147d75 install -r app/build/outputs/apk/debug/app-debug.apk
```

> O build estagia o Python a partir de `toolchain/dist/` (symlink ou cópia) e o
> `tempestroid` puro a partir de `../tempestroid` (excluindo `renderers/qt`). O
> APK extrai a stdlib na **primeira execução**, então o primeiro boot é lento
> (dezenas de segundos).

## 5. Rodar e capturar

```bash
adb -s 0d474c147d75 shell am start -n org.tempestroid.host/.MainActivity
# espere o boot do interpretador (~20 s na primeira vez), depois:
adb -s 0d474c147d75 exec-out screencap -p > shot.png
adb -s 0d474c147d75 logcat -d | grep -iE "tempestroid|python|FATAL"
```

Sem `tempest_dev_url` e sem `tempest_app.py` empacotado, a Activity roda a **demo
embutida** (`MainActivity.DEVICE_DEMO`).

### Modo dev (code-push por LAN)

```bash
adb reverse tcp:8765 tcp:8765
tempest serve examples/device_counter/app.py
adb shell am start -n org.tempestroid.host/.MainActivity \
  --es tempest_dev_url http://localhost:8765
```

## Solução de problemas

| Sintoma | Causa / correção |
|---|---|
| `adb start-server`/`devices` trava | Rede *mirrored* do WSL — use o servidor `nodaemon` em background (§3). |
| `vhci_hcd: urb->status -104` no `dmesg` | Reset da conexão usbip — refaça `usbipd attach`, troque a porta USB/cabo. |
| `INSTALL_FAILED_USER_RESTRICTED` | Ligue **"Instalar via USB"** nas Opções do desenvolvedor (MIUI/HyperOS). |
| Gradle falha com erro de AGP | Use o **wrapper 8.11.1** (`./gradlew`), não o Gradle global. |
| `dir _*` some do APK | O `ignoreAssetsPattern` padrão do AGP dropa dirs `_*`; já sobrescrito em `app/build.gradle.kts`. |
| `usbipd` não reconhecido | usbipd-win não instalado — veja §1; reabra o PowerShell após instalar. |

---

## Sem hardware físico — emulador headless x86_64 (Trilho F7/F8)

O aparelho físico no WSL é frágil (o usbipd cai, a MIUI exige *toggles*, a tela
bloqueia). O caminho recomendado para validar o lado nativo **sem hardware** é um
**emulador headless x86_64**, que cobre tudo que o device cobre — boot do CPython,
ponte JNI, renderizador Compose e capacidades nativas — e roda em CI.

!!! info "Preview-first"
    O **simulador Qt** (`make run` / `make dev`) é a sua visualização instantânea
    de iteração de UI. O **emulador** é a verificação de verdade do lado nativo.
    Itere no Qt; suba ao emulador só para confirmar Compose/JNI/nativas — não fique
    esperando o AVD a cada mudança de tela.

### Pré-requisito: KVM

```bash
[ -r /dev/kvm ] && [ -w /dev/kvm ] && echo "KVM OK" || echo "sem KVM"
```

Sem `/dev/kvm` (CI sem virtualização aninhada) o emulador é lento demais — use uma
**farm de device na nuvem** (Firebase Test Lab / Genymotion SaaS / BrowserStack)
como contingência. Os scripts F8 detectam a ausência de KVM e avisam.

### 1. Provisionar o AVD (reprodutível)

```bash
make provision-avd          # cria o AVD pinado (idempotente; FORCE=1 recria)
```

Instala a *system image* exata (`android-34`, `google_apis`, `x86_64`) e cria o
AVD `pixel8_api34`. Rodar de novo é *no-op* — o time inteiro tem o **mesmo** AVD.

### 2. Salvar o *snapshot* golden (boot rápido)

```bash
make emulator-snapshot      # boota uma vez (gravável) e salva o snapshot 'golden'
```

A partir daí `make emulator` **restaura do snapshot em segundos** (estado limpo
conhecido) em vez de *cold-boot*. Re-rode quando a *system image* ou o host mudar.

### 3. Bootar + verificar

```bash
make emulator               # boot rápido pelo snapshot 'golden' (cai pra cold-boot se não houver)
make emulator-verify APP=examples/counter/app.py   # boot → stage x86 → APK x86 → install → serve → screenshot
VISUAL=1 make emulator-verify APP=examples/counter/app.py  # + regressão visual contra o golden versionado
```

O `emulator-verify` faz **gating de prontidão real** (`sys.boot_completed=1` +
*bootanim* parado + `pm` respondendo) e **auto-recupera** um AVD travado uma vez
antes de desistir — toda chamada `adb` é *time-bounded* (helpers `device_loop.sh`
do F5), então um emulador preso nunca pendura o harness.

### 4. Regressão visual

`VISUAL=1` compara o screenshot capturado contra um *golden* versionado em
`docs/assets/emulator/golden/<exemplo>.png` (tolerância padrão 2%, via
`toolchain/visual_regression.py` — Pillow). Um *golden* ausente é **criado** na
primeira execução (baseline). Complementa os *goldens* JVM do Roborazzi (F7-camada
B) e a conformância (fase D): aqueles pinam a tradução de `Style`; este pina o
render ponta-a-ponta no emulador.

### 5. Pool de N emuladores em paralelo (experimental)

```bash
make emulator-pool N=3      # sharda a galeria de exemplos entre 3 instâncias isoladas
```

Cada instância é **isolada** (porta/serial próprios, `-read-only` a partir do
snapshot golden), então N emuladores compartilham a imagem base sem corromper o
estado um do outro; um que trave é recuperado sem derrubar os demais. O tempo de
validação cai ~linearmente com cores/RAM. **Experimental — ainda não validado num
emulador bootando; valide ponta-a-ponta antes de confiar em CI.**

### 6. Espelhamento ao vivo (`scrcpy`)

```bash
make mirror                 # espelha o emulador/device numa janela do host (precisa WSLg)
```

`scrcpy` mostra e clica o lado nativo ao vivo. No WSL precisa de **WSLg** (X). Não
substitui o screenshot do `emulator-verify` — é para inspeção interativa.

### Robustez de GPU no WSL

O padrão é `-gpu swiftshader_indirect` (render por software, estável headless).
Se a tela vier preta/corrompida, tente `-gpu guest` ou `-gpu host` (este exige
WSLg). Gotcha separado do simulador desktop: o Qt no WSL precisa de
`QT_QPA_PLATFORM=xcb` (bug do backend wayland) — emulador e simulador têm gotchas
de GPU distintos.

### Solução de problemas (emulador)

| Sintoma | Causa / correção |
|---|---|
| `make emulator` faz cold-boot toda vez | Sem snapshot `golden` — rode `make emulator-snapshot` uma vez. |
| AVD nunca fica pronto | `emulator-verify` auto-recupera uma vez; persistindo, `emulator -avd <AVD> -wipe-data` (destrutivo) e re-snapshot. |
| `adb` trava sob carga | Helpers `device_loop.sh` dão *timeout* em toda chamada; o `emulator-verify` chama `adb_unwedge` (mata o processo do server + reinicia *nodaemon*) — `adb kill-server` **também trava** quando o server está *wedged*, por isso não o use. |
| snapshot save falha | Boot tem que ser **gravável** — `emulator-snapshot` já usa `EMU_READONLY=0`; não salve com `-read-only`. |
| sem `/dev/kvm` | Sem aceleração — use farm na nuvem; não insista no emulador local. |
