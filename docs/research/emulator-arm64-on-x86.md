# Emulando o ambiente real via emuladores — o que dá e o que não dá

Investigação (2026-07-07) sobre validar tempestroid **sem dispositivo físico**,
usando emuladores no host WSL x86_64. Conclusões fundamentadas em teste empírico.

## TL;DR

- **x86_64 emulador = o caminho de validação funcional.** Boota com aceleração
  KVM, roda o framework inteiro (IR, renderer Compose, ponte JNI, code-push) e a
  **stack de visão** (numpy + ort_vision_sdk + AAR onnxruntime). Operacionalizado
  em `toolchain/emulator_verify.sh` (`make emulator-verify`, `VISION=1` inclui a
  stack de visão). **Nenhum device físico necessário** para provar lógica.
- **arm64 emulador NO host x86_64 = impossível pelo tooling suportado.** O
  launcher do Android Studio emulator (v35.5) **bloqueia explicitamente**:

  ```text
  PANIC: Avd's CPU Architecture 'arm64' is not supported by the QEMU2 emulator
  on x86_64 host.
  ```

  Isso apesar de `qemu-system-aarch64` estar bundled em
  `emulator/qemu/linux-x86_64/` — esse binário existe para hosts **arm64** (Apple
  Silicon, Linux arm64), não para emular arm64 sobre x86.
- **Execução arm64 fiel exige um host arm64.** Device físico, Apple Silicon,
  Linux arm64, ou um **runner arm64 na CI** (GitHub hospeda runners arm64). Não há
  atalho no host x86.

## O que foi testado

| Tentativa | Resultado |
|---|---|
| x86_64 AVD (`pixel8_api34`) headless + KVM | ✅ boota, roda apps + visão |
| Baixar `system-images;android-33;aosp_atd;arm64-v8a` + criar AVD | ✅ baixa/cria |
| Bootar o AVD arm64 no host x86_64 | ❌ `PANIC: arm64 not supported ... on x86_64 host` |
| `qemu-user` (rodar CPython aarch64 direto) | ❌ não instalado; sem sudo passwordless; **e** os `.so` do wheel são **bionic/Android**, não carregam sob qemu-user glibc |

## Por que qemu-user não resolve

As wheels Android (`numpy-*-android_24_arm64_v8a.whl`, `pydantic_core`, os `.so`
do CPython) são linkadas contra a **bionic libc** do Android e usam o linker
`/system/bin/linker64`. `qemu-aarch64` user-mode espera um userland Linux/glibc
padrão — não a bionic com o layout do Android. Rodar binários Android bionic sob
qemu-user é notoriamente frágil (linker path, propriedades do sistema) e não é um
caminho de validação confiável.

## Estratégia recomendada

1. **Validação funcional → x86_64 emulador** (`make emulator-verify [VISION=1]`).
   Cobre tudo que é lógica de framework + o caminho de imports/inferência. Barato,
   acelerado, sem device. **Já roda na CI**:
   `.github/workflows/android-emulator.yml` job `emulator-vision` builda os wheels
   x86_64, sobe o emulador headless (KVM via `reactivecircus/android-emulator-runner`)
   e roda `VISION=1 emulator_verify.sh` ponta-a-ponta (screenshot como artifact).
   Dispara em `workflow_dispatch`, push→main no surface nativo, e cron semanal.
2. **Validação de ABI dos wheels compilados → estrutural + arm64 real.**
   - Estrutural (feito no host x86, **na CI**): o job `wheels-abi` cross-compila
     numpy arm64-v8a + x86_64 e afirma o ELF machine dos `.so` (0xB7 / 0x3E),
     pegando regressão de packaging/ABI sem host arm64.
   - **Build arm64 completo na CI**: `build-arm64-apk` (runner x86_64) cross-compila
     os wheels arm64 + o `.so` do host + a APK arm64 de visão e sobe como artifact
     — pega regressão de BUILD arm64 a cada trigger.
   - Runtime arm64: **device físico** (`tempest serve`/`deploy`) ou um **host arm64
     com virtualização**. É o único jeito de executar o código aarch64.

## arm64 runtime na CI — o que trava (investigado a fundo)

Fechar o *runtime* arm64 na CI (não só o build) esbarra em limites de
infraestrutura dos runners hospedados do GitHub — **nenhum é culpa do código**:

- **NDK é x86_64-host-only.** O NDK não tem toolchain linux-aarch64; o `clang` é
  x86_64 e dá `Exec format error` num runner arm64. ⇒ **build arm64 SEMPRE num host
  x86_64** (cross), runtime noutro lugar. Por isso o split
  `build-arm64-apk` (x86) → artifact → job de runtime.
- **Runner arm64 Linux hospedado (`ubuntu-24.04-arm`) não expõe `/dev/kvm`**
  (`Failed to open the device 'kvm': Invalid argument`). Sem KVM o emulador arm64
  só roda em **TCG** (software) — lento demais/instável, boot estoura o timeout.
- **Runner macOS Apple Silicon (`macos-latest` = macos-26)**: tem virtualização
  nativa (HVF), o emulador arm64 (36.6.11) **inicia**, mas **trava no backend
  gráfico gfxstream/swiftshader headless** (`startOpenglesRendererImpl` pendura;
  a porta 5554 nunca abre). Regressão da imagem de runner/emulador, não do app.

**Estado:** o job `emulator-vision-arm64` (macOS) fica `continue-on-error` — é
best-effort e volta a passar sozinho quando a imagem do runner estabilizar. As
formas **garantidas** de runtime arm64 hoje: (a) **device físico** (mecanismo
`tempest serve`/`deploy` já provado), ou (b) **runner self-hosted arm64 com KVM**.
A cobertura verde na CI (ABI + build arm64 + runtime x86_64) já pega
regressão de packaging/ABI/lógica sem depender disso.
3. **Não perder tempo tentando arm64-em-x86** — o PANIC é definitivo.

## Reprodução (x86_64, com visão)

```bash
pkill -9 adb 2>/dev/null                       # desagarra server travado se preciso
export ANDROID_SDK_ROOT=/usr/lib/android-sdk
make numpy-x86 2>/dev/null || bash toolchain/build_numpy_x86.sh   # wheel numpy x86 (1x)
VISION=1 make emulator-verify APP=examples/visionsmoke/app.py
# → boota o emulador, stage vision, builda APK x86 com --feature vision,
#   instala, tempest serve, screenshot. Tela: "VISION OK — numpy … ort_vision_sdk …"
```
