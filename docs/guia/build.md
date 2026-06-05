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
| **Mandar um APK** para alguém testar | `tempest build` | SDK + NDK + toolchain (auto) | `.apk` com `applicationId` próprio (lado a lado) |
| Iterar rápido num app só, sem toolchain | `tempest build --fast` | só SDK build-tools | `.apk` (id compartilhado, 1 app) |
| Build + instalar + logs | `tempest run` | SDK build-tools + adb | Instala o APK e segue os logs |

!!! info "Duas filosofias"
    - **Push (efêmero)** (`deploy`/`serve`): um **host genérico** (CPython +
      framework) é instalado uma vez; seu código Python é empurrado por cima.
      Rápido, offline. Mas o app vive **dentro do host** — não é um artefato que
      você manda para outra pessoa.
    - **APK shippable** (`build`/`run`): gera um `.apk` distribuível com seu
      projeto **assado dentro**. Por padrão via **Gradle** (`assembleDebug`), com
      `applicationId` próprio (apps lado a lado); com `--fast`, **repacka o host
      pré-compilado** (só SDK build-tools, id compartilhado, 1 app).

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
tempest build                              # Gradle: APK com applicationId próprio
tempest build --app-id com.suaempresa.app  # define o id (recomendado para algo real)
tempest build -o /tmp/app.apk              # escolhe o caminho de saída
```

O resultado fica em `dist/<projeto>.apk` (ou em `-o`). Por padrão o `tempest
build` roda o Gradle (`assembleDebug`) e carimba cada app com seu **próprio
`applicationId`** + rótulo de launcher, para que dois apps tempestroid **instalem
lado a lado** em vez de um sobrescrever o outro. Assinado com a chave debug →
`adb install` em qualquer aparelho compatível e o app abre direto, sem servidor.

!!! info "Devo definir o `--app-id` ou o framework gera sozinho?"
    **Os dois — mas, para algo real, defina o seu.**

    - Você passa `--app-id com.suaempresa.app` → é esse o `applicationId` (e
      `--app-name "Meu App"` para o nome sob o ícone).
    - Você **omite** → o framework **deriva** `com.example.<nome-do-projeto>`, só
      para você conseguir buildar e instalar na hora, sem decidir nada.

    O id derivado `com.example.*` é um **placeholder, não publicável** — a Play
    Store rejeita `com.example.*`. Regra prática: **teste com o derivado; defina o
    seu `--app-id`** (domínio reverso da sua empresa, ex. `com.suaempresa.app`)
    **assim que o app for pra valer**, e **mantenha o mesmo id para sempre** —
    mudá-lo cria outro app aos olhos do Android/da Play (perde updates e dados).
    O id é independente do pacote Java/JNI interno (`org.tempestroid.host`), então
    escolher o seu não quebra a ponte.

!!! note "O `build` padrão usa o toolchain; `--fast` dispensa (1 app)"
    O `tempest build` padrão roda o Gradle, então precisa de SDK **+ NDK** +
    checkout `android-host` + toolchain CPython — o CLI **prepara o que faltar**.
    Para iterar rápido num **único** app sem o toolchain, use `tempest build
    --fast`: pula o Gradle e **repacka o host pré-compilado** (só os SDK
    build-tools, funciona de um install via PyPI). Trade-off: o `--fast` mantém o
    id compartilhado `org.tempestroid.host` (um repackage não reescreve o package
    do manifesto binário), então serve para **um app por vez**, não para vários
    lado a lado. Rode `tempest setup --install` para o SDK/NDK.

## Publicar na Play Store (`--release` → AAB)

A Play Store exige um **Android App Bundle** (`.aab`), assinado de release, com o
seu próprio `applicationId`. `tempest build --release` gera isso via Gradle
`bundleRelease` e **prepara o ambiente que faltar** (SDK/NDK, checkout do source,
toolchain CPython, keystore):

```bash
tempest build main.py --release \
  --app-id com.suaempresa.todo \
  --app-version 1.0.0 \
  --version-code 1 \
  --keystore release.jks          # omita → gera uma em ~/.tempestroid/release.jks
# → dist/<projeto>-release.aab  (sobe no Play Console)
```

!!! warning "Guarde a keystore"
    A keystore de release assina seu app. **Perdê-la impede atualizar o app na
    Play** depois. Faça backup da `--keystore` (ou da gerada em
    `~/.tempestroid/release.jks`). Use seu **próprio** `--app-id` — o placeholder
    `com.example.*` não publica.

!!! info "O `--release` precisa do toolchain completo"
    Diferente do APK debug (repackage), o AAB é build de fonte: precisa de
    SDK **+ NDK** + checkout do `android-host` + toolchain CPython staged. O CLI
    instala/clona/staga o que faltar (o staging do CPython é pesado: download +
    build de wheels nativos).

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
