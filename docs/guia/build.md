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
| **Mandar um APK** para alguém testar | `tempest build apk` | JDK + Android SDK | `.apk` com `applicationId` próprio (**N apps lado a lado**) |
| Distribuir **fora da Play** (site, link) | `tempest build release-apk` | JDK + SDK + keystore | `.apk` de release assinado com a **sua** chave |
| Build + instalar + logs no device | `tempest run` | JDK + SDK + adb | Instala o APK e segue os logs |
| Publicar na Play Store | `tempest build prd` | JDK + SDK + keystore | `.aab` de release assinado |
| Iterar num app só, **sem instalar SDK** | `tempest build --fast` | só SDK build-tools | `.apk` (id compartilhado, 1 app) |

!!! info "Como funciona (sem toolchain pesada)"
    `tempest build apk` roda o **Gradle** (que carimba o `applicationId` + todas as
    *provider authorities* por app → **instalam lado a lado sem colisão**), mas
    **reusa os nativos do host pré-compilado** (`libpython`, a stdlib, o JNI) que
    já vêm no pacote. Logo precisa só de **JDK + Android SDK** — **sem NDK, sem
    compilar CPython**. O projeto `android-host` vem **dentro do wheel**, então
    funciona de um `pip install` puro, **sem `git clone`**.

    - `deploy`/`serve`: empurram seu código pra um **host genérico** já instalado
      (rápido, offline) — o app vive dentro do host, não é um artefato distribuível.
    - `--fast`: repackage do host pré-compilado **sem SDK nenhum** (só build-tools),
      mas com id compartilhado `org.tempestroid.host` → **1 app por device**.
    - `--from-source`: build pesado, estagiando a toolchain CPython (raramente
      necessário).

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
    Para algo distribuível, use [`tempest build apk`](#gerar-um-apk-tempest-build-apk).

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

## Gerar um APK (`tempest build apk`)

Para um `.apk` **autocontido** (roda sem dev server, com o **id próprio** do seu
projeto → instala lado a lado com qualquer outro app tempestroid):

```bash
tempest build apk          # lê o [tool.tempest], gera dist/<projeto>.apk
tempest build apk -o /tmp/app.apk
```

A identidade e o visual vêm do **`[tool.tempest]`** no `pyproject.toml` — sem
flag-soup:

```toml
[tool.tempest]
app = "app.py"
id = "com.suaempresa.todolist"   # applicationId; derivado do projeto se omitido
name = "Todo List"               # rótulo sob o ícone
icon = "icone.png"               # opcional
splash = "splash.png"            # opcional
splash_bg = "#0b0f14"            # opcional
version = "1.0.0"                # opcional (default 1.0.0)
```

O resultado fica em `dist/<projeto>.apk`, assinado com a chave debug →
`adb install` em qualquer aparelho e abre direto, sem servidor. Cada projeto sai
com seu **próprio `applicationId`**, então **N apps instalam lado a lado** (nunca
um sobre o outro). As flags `--app-id`/`--app-name`/`--icon`/… sobrescrevem o
config por build.

!!! info "Devo definir o `id` ou o framework gera sozinho?"
    **Os dois — mas, para algo real, defina o seu.** Omitido → o framework
    **deriva** `com.example.<projeto>` só pra você buildar na hora. Esse
    `com.example.*` é **placeholder, não publicável** (a Play rejeita). Regra:
    **teste com o derivado; defina o seu `id`** (domínio reverso, ex.
    `com.suaempresa.app`) **e mantenha o mesmo pra sempre** — mudá-lo vira outro
    app aos olhos do Android/Play. O `id` é independente do pacote Java/JNI
    interno (`org.tempestroid.host`), então escolher o seu não quebra a ponte.

!!! note "Precisa só de JDK + Android SDK (sem NDK, sem toolchain)"
    `tempest build apk` roda o Gradle **reusando os nativos do host pré-compilado**
    (libpython/JNI/stdlib que já vêm no pacote) → **não compila CPython, não usa
    NDK**. O `android-host` vem **dentro do wheel**, então funciona de um `pip
    install` puro, **sem `git clone`**. Rode `tempest setup --install` uma vez pro
    SDK (o JDK é pré-requisito). Sem JDK/SDK, o build **cai pro `--fast`** (id
    compartilhado) com aviso, em vez de falhar.

## Ícone e tela de carregamento (splash)

Todo APK já sai com um **ícone tempestroid** e uma **splash** padrão que cobre o
boot do interpretador Python (alguns segundos). Para personalizar por app:

```bash
tempest build --icon icone.png \
  --splash splash.png \
  --splash-bg "#0b0f14"
```

!!! tip "Gere os dois a partir de UMA imagem com `tempest icon`"
    Não quer dimensionar à mão? Aponte para um logo e o CLI gera os dois PNGs:

    ```bash
    tempest icon logo.png --out assets
    # → assets/icon.png (quadrado) + assets/splash.png (centralizado, fundo transparente)
    tempest build --icon assets/icon.png --splash assets/splash.png --splash-bg "#0b0f14"
    ```

    Precisa do Pillow: `pip install tempestroid[icons]` (ou `uv add tempestroid[icons]`).

- `--icon icone.png` — o ícone de launcher (o que aparece na gaveta de apps).
  **Só no build Gradle** (o default): o ícone é um recurso *compilado*, e um
  repackage `--fast` não reescreve o `resources.arsc`, então com `--fast` o app
  mantém o ícone padrão (o CLI avisa).
- `--splash splash.png` — a imagem mostrada centralizada enquanto o Python sobe.
- `--splash-bg "#rrggbb"` — a cor de fundo da splash (default `#0b0f14`).

### Ícone adaptativo (a máscara do launcher)

Um PNG quadrado simples não recebe a máscara do launcher (cantos arredondados /
squircle). Para um **ícone adaptativo** de verdade — duas camadas, frente +
fundo, que o launcher mascara como um app nativo — gere a camada de frente e
passe-a no build:

```bash
tempest icon logo.png --adaptive --out assets
# → também escreve assets/ic_launcher_foreground.png (a marca centrada na zona segura)
tempest build --adaptive-icon assets/ic_launcher_foreground.png --icon-bg "#0b0f14"
```

- `--adaptive-icon fg.png` — a camada de **frente** (a marca, com margem da zona
  segura). **Só no build Gradle** (recurso compilado; `--fast` mantém o ícone
  padrão e avisa).
- `--icon-bg "#rrggbb"` — a cor de **fundo** do ícone adaptativo (default branco).

!!! info "O que o build gera"
    Emite um adaptive icon Android real: `res/drawable/ic_launcher_foreground.png`
    + `res/values/ic_launcher_background.xml` (a cor) + os
    `res/mipmap-anydpi-v26/ic_launcher{,_round}.xml` que redirecionam o
    `@mipmap/ic_launcher` para eles no Android 8+ (API 26). Em versões antigas o
    PNG quadrado (`--icon`) continua valendo.

!!! tip "A splash cobre o boot do CPython"
    O interpretador leva alguns segundos para iniciar. A splash é desenhada pela
    Activity a partir de **assets** e fica na tela **até o primeiro `mount`** do
    seu app — então o usuário vê sua marca, não uma tela em branco. Como vive em
    assets (caminho estável), `--splash`/`--splash-bg` funcionam em **todos** os
    caminhos de build, inclusive `--fast`.

## Distribuir fora da Play (`tempest build release-apk` → APK assinado)

Para mandar o app por um **site, loja alternativa ou link direto** — sem passar
pela Play Store — você quer um **APK de release assinado com a sua própria
chave** (não o debug-signed do `tempest build apk`, que serve só para teste). É o
`tempest build release-apk`: roda o Gradle `assembleRelease` com a sua keystore.

```bash
tempest build release-apk                          # usa [tool.tempest] id/name/version
tempest build release-apk --keystore release.jks   # sua keystore (senão gera em ~/.tempestroid/release.jks)
tempest build release-apk --app-id com.acme.app --app-version 1.2.0
# → dist/<projeto>-release.apk
```

Confira a assinatura com o `apksigner` do SDK:

```bash
apksigner verify --print-certs dist/<projeto>-release.apk
```

!!! warning "Build real obrigatório (sem fallback `--fast`)"
    Diferente do `tempest build apk`, o `release-apk` **não** cai no repackage
    `--fast` quando o toolchain falta — um APK assinado de release exige o Gradle
    de verdade. Sem JDK + SDK, ele falha com erro (resolva o toolchain com
    `tempest setup --install`).

!!! note "Mesma keystore do `prd`"
    Reaproveita a keystore e o aviso do `prd` abaixo: **guarde a chave** e
    **defina o seu `id`** antes de distribuir.

## Publicar na Play Store (`tempest build prd` → AAB)

A Play Store exige um **Android App Bundle** (`.aab`), assinado de release.
`tempest build prd` gera isso via Gradle `bundleRelease`, lendo o `[tool.tempest]`
e usando uma keystore (a sua via `--keystore`, ou uma gerada e cacheada):

```bash
tempest build prd                          # usa [tool.tempest] id/name/version
tempest build prd --keystore release.jks   # sua keystore (senão gera em ~/.tempestroid/release.jks)
# → dist/<projeto>-release.aab  (sobe no Play Console)
```

!!! warning "Guarde a keystore + defina o seu id"
    A keystore de release assina seu app. **Perdê-la impede atualizar o app na
    Play** depois — faça backup da `--keystore` (ou da gerada em
    `~/.tempestroid/release.jks`). E defina o seu `id` no `[tool.tempest]` — o
    placeholder `com.example.*` não publica.

!!! note "Mesma base leve do `apk`"
    Como o `apk`, o `prd` reusa os nativos do host pré-compilado → **só JDK +
    Android SDK**, sem NDK nem toolchain CPython. (Se algum dia precisar buildar a
    toolchain do zero, há a flag avançada `--from-source`.)

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

`tempest build apk`/`prd`/`run` precisam de:

- **JDK** (`java -version`) — pré-requisito (guiado, não instalado pelo CLI).
- **Android SDK.** `tempest setup --install` instala/configura; ou exporte
  `ANDROID_SDK_ROOT` para um SDK existente. **NDK não é necessário** (o build
  reusa os nativos pré-compilados).

!!! note "Caminho avançado `--from-source`"
    Só se você passar `--from-source` o build estagia a toolchain pesada (CPython
    3.14 + wheels nativos via `make toolchain`) e precisa do **NDK** + do Gradle
    wrapper 8.11.1. No fluxo normal (prebuilt) nada disso é preciso.

No **aparelho**: ligue **Depuração USB**; em MIUI/HyperOS (Xiaomi/Redmi/POCO)
ligue também **"Instalar via USB"**, senão `adb install` falha com
`INSTALL_FAILED_USER_RESTRICTED`.

!!! tip "Diagnóstico em um comando"
    `tempest doctor` roda o *preflight* (árvore do host, SDK, `adb`, aparelho) e
    aponta o que falta antes de um build. Rodando em WSL? Veja o guia dedicado de
    [USB no dispositivo (WSL)](dispositivo-wsl.md).

## Mandar o APK para alguém testar

1. Gere: `tempest build apk`.
2. Pegue o `.apk` em `dist/<projeto>.apk`.
3. Envie o arquivo (mensageiro, link, etc.).
4. A pessoa instala (`adb install <projeto>.apk`, ou abrindo o `.apk` no aparelho
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
