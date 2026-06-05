# Build, deploy e publicação

Esta página mostra como sair do simulador e **rodar seu app num aparelho
Android** — desde o teste rápido no seu próprio celular até gerar um **APK
autocontido** que você manda para outra pessoa testar. Tudo a partir do seu
projeto em Python.

!!! tip "Comece pelo simulador"
    Para o ciclo de desenvolvimento (editar → ver), use `tempest dev` (o
    [simulador Qt](cli.md)). Esta página é sobre levar o mesmo app para o
    **dispositivo** e para um **APK distribuível**.

## Projetos multi-arquivo

Seu app raramente é um arquivo só: o `main.py` importa módulos e pacotes vizinhos
do seu projeto. O tempestroid trata isso de forma transparente.

A **raiz do projeto** é o diretório ancestral mais próximo do app que contém um
`pyproject.toml`. Toda a árvore importável a partir dela é empacotada e colocada
no `sys.path` — no simulador **e** no dispositivo — então:

```python
# main.py
from meu_pacote.widgets import cartao   # ✅ resolve igual no desktop e no device
```

resolve identicamente nos dois lados. O bundle **exclui** o que não é código de
app: `.venv`, `__pycache__`, `.git`, `dist`, `build`, caches de editor/lint.

!!! example "Layout típico de projeto"
    ```text
    meu-app/
    ├── pyproject.toml      # contém [tool.tempest] app = "main.py"
    ├── main.py             # define view(app) + make_state()
    └── meu_pacote/
        ├── __init__.py
        └── widgets.py      # importado por main.py
    ```

    O `pyproject.toml` ancora a raiz. Sem ele, a raiz vira o diretório do
    próprio `main.py` (modo arquivo-único).

```toml
# pyproject.toml
[tool.tempest]
app = "main.py"
```

Com `[tool.tempest] app` definido, `dev` / `deploy` / `serve` / `build` / `run`
dispensam o argumento de caminho dentro do projeto.

## Qual comando usar?

| Quero… | Comando | Precisa de quê? | Entrega |
|---|---|---|---|
| Rodar rápido no **meu** aparelho | `tempest deploy` | nada (só adb) | App rodando no device (efêmero) |
| Editar e ver ao vivo (hot reload) | `tempest serve` | nada (só adb) | Loop de code-push por LAN |
| **Mandar um APK** para alguém testar | `tempest build` | SDK build-tools | `.apk` autocontido e distribuível |
| Build + instalar + logs | `tempest run` | SDK build-tools + adb | Instala o APK e segue os logs |

!!! info "Duas filosofias"
    - **Push (efêmero)** (`deploy`/`serve`): um **host genérico** (CPython +
      framework) é instalado uma vez; seu código Python é empurrado por cima.
      Rápido, offline. Mas o app vive **dentro do host** — não é um artefato que
      você manda para outra pessoa.
    - **APK shippable** (`build`/`run`): **repackam o host pré-compilado** com seu
      projeto injetado (re-assinado via `zipalign`/`apksigner` do SDK). **Sem
      Gradle, NDK ou checkout `android-host`** — só o SDK build-tools. É o caminho
      que gera um `.apk` distribuível.

## Rodar no meu aparelho (sem toolchain)

Você **não** precisa de Android SDK/NDK nem do código-fonte `android-host` para
testar no seu próprio celular. Conecte o aparelho (`adb devices` deve listá-lo) e:

```bash
tempest deploy            # instala o host empacotado (1x) + empurra o projeto + abre
```

O `tempest deploy`:

1. Instala o **host pré-compilado** (baixado do release do GitHub no primeiro
   uso e cacheado) se ainda não estiver no aparelho. Execuções seguintes pulam.
2. Empacota seu projeto e empurra **uma vez** por um servidor efêmero.
3. Abre o app e **encerra**. O app continua rodando no aparelho.

!!! warning "`deploy` não gera artefato"
    O app empurrado por `deploy` vive na sessão do host. Em um boot frio, ou no
    celular de outra pessoa, o host roda o demo embutido — **não** o seu app.
    Para algo distribuível, use [`tempest build`](#publicar-um-apk).

Para um **loop de hot reload** (editar + salvar → recarrega no device):

```bash
tempest install           # só adb-instala o host (offline/embutido)
tempest serve             # code-push por LAN: salvar qualquer arquivo recarrega
```

O `tempest install` resolve o APK do host nesta ordem: caminho/URL `.apk`
explícito → `TEMPESTROID_HOST_APK` → asset empacotado (só num checkout do código
estagiado com `make stage-host`) → download do release do GitHub
(`TEMPESTROID_HOST_APK_URL` para sobrescrever), cacheado em `~/.cache/tempestroid`.
O wheel do PyPI **não** embute o APK (~100 MB), então num install via PyPI o
download é o caminho normal (offline depois disso).

## Publicar um APK

Para gerar um `.apk` **autocontido** (roda sem dev server, dá para mandar para
qualquer pessoa):

```bash
tempest build                 # repackage do host pré-compilado com seu projeto
tempest build -o /tmp/app.apk # escolhe o caminho de saída
```

O resultado fica em `dist/<projeto>.apk` (ou em `-o`). O `tempest build` bundla
seu projeto, baixa/usa o **host pré-compilado** e injeta o bundle nele,
re-alinhando (`zipalign`) e re-assinando (`apksigner`, chave debug). O APK tem
seu projeto **assado dentro** — `adb install` em qualquer aparelho compatível e
o app abre direto, sem servidor. Assinado com a chave debug → instala como
qualquer build debug.

!!! note "`build` precisa só do SDK build-tools"
    `tempest build`/`run` usam apenas `zipalign` + `apksigner` do **Android SDK
    build-tools** — **sem Gradle, NDK ou checkout `android-host`**, então
    funcionam de um install via PyPI. Rode `tempest setup` para conferir o
    ambiente (`tempest setup --install` instala o SDK + build-tools).

## Configuração de ambiente

!!! tip "Deixe o `tempest setup` configurar para você"
    ```bash
    tempest setup            # diagnostica JDK/SDK/NDK/build-tools/toolchain + plano
    tempest setup --install  # instala o Android SDK + NDK (precisa de um JDK)
    ```
    `tempest setup` (sem flag) reporta o que falta e como resolver. Com
    `--install` ele baixa as command-line tools, aceita as licenças e instala
    `platform-tools` + `platforms;android-35` + `build-tools;35.0.0` +
    `ndk;27.3.13750724` num diretório gerenciado (`--sdk-dir` para escolher).
    O **JDK** e o `make toolchain` ficam guiados (não são instalados sozinhos).

Para os caminhos com toolchain (`build`/`run`), o host de build precisa de:

- **Android SDK + NDK.** Exporte `ANDROID_SDK_ROOT` apontando para o SDK (neste
  host de referência: `/usr/lib/android-sdk`, **não** o `ANDROID_HOME` obsoleto):

    ```bash
    export ANDROID_SDK_ROOT=/usr/lib/android-sdk
    ```

- **JDK 21** (`java -version`).
- **Gradle wrapper 8.11.1** (`android-host/gradlew`) — o Gradle global 9.x é
  incompatível com o AGP 8.7; **sempre** use o wrapper (os comandos do `tempest`
  já o fazem).
- A **toolchain Python estagiada**: CPython 3.14 + wheels nativos
  (`pydantic-core`) em `toolchain/dist/`. Gere com:

    ```bash
    make toolchain
    ```

No **aparelho**: ligue **Depuração USB**; em MIUI/HyperOS (Xiaomi/Redmi/POCO)
ligue também **"Instalar via USB"**, senão `adb install` falha com
`INSTALL_FAILED_USER_RESTRICTED`.

!!! tip "Diagnóstico em um comando"
    `tempest doctor` roda o *preflight* (árvore do host, SDK, `adb`, aparelho) e
    aponta o que falta antes de um build. Rodando em WSL? Veja o guia dedicado de
    [USB no dispositivo (WSL)](dispositivo-wsl.md).

## Mandar o APK para alguém testar

1. Gere: `tempest build` (ou `--release`).
2. Pegue o `.apk` em `android-host/app/build/outputs/apk/debug/app-debug.apk`.
3. Envie o arquivo (mensageiro, link, etc.).
4. A pessoa instala (`adb install app-debug.apk`, ou abrindo o `.apk` no aparelho
   com "fontes desconhecidas" liberado).

O app roda standalone — sem o seu computador, sem dev server.

## Recapitulando

- Apps são **multi-arquivo**: a árvore do projeto vai junto, no `sys.path`, no
  simulador e no dispositivo.
- `tempest deploy` / `serve` rodam no **seu** aparelho **sem toolchain** — ótimos
  para testar, mas não geram artefato.
- `tempest build` gera um **APK autocontido distribuível** — precisa de SDK/NDK +
  checkout do `android-host`.
- `tempest doctor` valida o ambiente; o [guia WSL](dispositivo-wsl.md) cobre a
  passagem de USB.
