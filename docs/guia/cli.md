# CLI (`tempest`)

A CLI `tempest` é o painel único do framework: cria o projeto, roda no simulador
com hot reload, empurra pro aparelho, gera o APK, e ainda embute lint/type/test.
Este guia é a **referência completa** — cada comando com o que faz, quando usar e
um exemplo pronto pra copiar.

Comece descobrindo tudo que existe:

```bash
tempest --help            # lista os comandos, agrupados por finalidade
tempest <comando> --help  # opções e argumentos de um comando específico
```

!!! tip "Prefixo `uv run`"
    Dentro de um projeto gerenciado por `uv`, rode `uv run tempest …` (usa o
    ambiente do projeto). Se o `tempest` já está no PATH (venv ativa / instalação
    global), o `uv run` é opcional. Os exemplos abaixo omitem o prefixo por
    brevidade.

## Mapa rápido

Os comandos se organizam em quatro grupos — o mesmo agrupamento que o
`tempest --help` mostra:

| Grupo | Comando | Faz |
|---|---|---|
| **Criar e desenvolver** | [`new`](#new) | Cria um app tempestroid na pasta atual. |
| | [`dev`](#dev) | Simulador Qt com hot reload. |
| | [`serve`](#serve) | Code-push por LAN pro aparelho (sem rebuild). |
| **Publicar e instalar** | [`deploy`](#deploy) | Roda o app no aparelho **offline** (sem SDK/NDK). |
| | [`install`](#install) | adb-instala o host pré-compilado. |
| | [`build`](#build) | Gera o APK/AAB distribuível (id próprio). |
| | [`run`](#run) | `build` + instala no aparelho + logs. |
| | [`icon`](#icon) | Gera ícone + splash de uma imagem. |
| | [`optimize`](#optimize) | Quantiza/converte um modelo ONNX pro dispositivo. |
| **Diagnosticar e inspecionar** | [`doctor`](#doctor) | Checa os pré-requisitos de build Android. |
| | [`setup`](#setup) | Instala/configura o SDK + NDK. |
| | [`spec`](#spec) | Imprime o contrato tipado (widgets/eventos) como JSON. |
| | [`clean`](#clean) | Limpa os caches de build em `~/.tempestroid`. |
| | [`version`](#version) | Mostra a versão do framework. |
| **Qualidade** | [`check`](#check) | Portão completo: lint + fmt-check + type + test. |
| | [`lint`](#lint) / [`fix`](#fix) | `ruff check` (só lê) / autofix + format. |
| | [`format`](#format) / [`fmt-check`](#fmt-check) | `ruff format` (escreve / só checa). |
| | [`type`](#type) | `pyright` estrito. |
| | [`test`](#test) / [`uitest`](#uitest) | `pytest` / teste de UI nativa. |

## Fluxo típico

```bash
tempest new                 # scaffold na pasta atual (id = nome da pasta)
tempest dev                 # simulador + hot reload (edita e salva → recarrega)
tempest deploy              # roda no aparelho conectado, offline (sem SDK/NDK)
tempest build apk           # APK distribuível com id próprio (JDK + SDK)
tempest run                 # build + instala + logs no aparelho
```

!!! info "`dev`/`serve` leem `[tool.tempest] app`"
    Rode-os sem argumento dentro do projeto — o caminho do app vem do
    `pyproject.toml`. Passe um caminho só pra sobrepor (ex.:
    `tempest dev examples/counter/app.py`).

---

## Criar e desenvolver

### `new`

Cria um app tempestroid executável **na pasta atual** (o `applicationId` deriva do
nome da pasta). Passe um nome pra criar numa subpasta.

```bash
tempest new                 # scaffold aqui
tempest new meu-app         # cria ./meu-app/
```

### `dev`

Sobe o **simulador Qt** com hot reload: editou e salvou, a UI recarrega
preservando o estado. É o loop de desenvolvimento do dia a dia (precisa do extra
`qt`).

```bash
tempest dev                             # lê [tool.tempest] app
tempest dev -d pixel-7                  # dimensiona a janela a um preset
```

- `--device` / `-d` — preset de aparelho (`pixel-7`, `galaxy-s24`, …) pra
  dimensionar a janela ao viewport real.

Veja o [cockpit do `tempest dev`](#cockpit-do-tempest-dev) pras teclas
interativas.

### `serve`

**Code-push por LAN**: empurra o código do projeto pro host já instalado no
aparelho e faz hot reload **sem rebuildar o APK**. Ideal pra iterar no hardware
real depois do primeiro `install`.

```bash
tempest install             # uma vez: instala o host no aparelho
tempest serve               # push + hot reload por LAN
```

- `--port` (padrão 8765), `--host` (padrão `0.0.0.0`), `--no-launch`.

---

## Publicar e instalar

Dois caminhos pro aparelho: **offline** (`deploy`/`serve`/`install`, sem SDK/NDK)
e **APK distribuível** (`build`/`run`, precisa de JDK + SDK). Veja
[Build, deploy e publicação](build.md) pra escolha.

### `deploy`

Roda o app inteiro no aparelho conectado **offline** — instala o host
empacotado, empurra o projeto e abre. Zero toolchain Android.

```bash
tempest deploy              # sem SDK/NDK
```

### `install`

adb-instala o **host pré-compilado** (o APK do host vem no pacote — instalação
offline e instantânea). Depois use `serve` pra empurrar apps.

```bash
tempest install                     # host embutido (offline)
tempest install ./meu-host.apk      # de um .apk local
tempest install --no-launch         # só instala
```

### `build`

Gera o artefato **distribuível** com o projeto inteiro embutido e
`applicationId` próprio (instala lado a lado com outros apps). Lê `[tool.tempest]`
do `pyproject.toml`.

```bash
tempest build apk               # APK debug per-app (JDK + SDK, sem NDK)
tempest build release-apk       # APK de release assinado (fora da Play)
tempest build prd               # AAB de release pra loja
```

- `--feature <cap>` (repetível) — embute uma capacidade pesada opcional:
  `vision`, `camera`, `qr`, `push`, `video`, `maps`. Cada opt-in exige um build
  **from-source** (SDK + NDK).
- `--from-source` — stagia o toolchain CPython completo em vez de reusar os
  nativos pré-compilados.
- `--app-id`, `--app-name`, `--app-version`, `--icon`, `--splash`, `--keystore`,
  `--output`.

!!! tip "App de visão (ONNX on-device)"
    Um app que usa `ort_vision_sdk`/`onnxruntime` precisa do stack de visão
    embutido — build assim:
    ```bash
    tempest setup --install                              # SDK + NDK
    tempest build apk --feature vision --from-source     # a CLI baixa o CPython sozinha
    ```
    Sem `--feature vision`, o app abre com a home **em branco** (as libs de visão
    não vão no APK lean). Desde a 0.15.4 a CLI busca o prefixo CPython Android
    automaticamente — não precisa stage manual.

### `run`

`build apk` + instala no aparelho + transmite os logs. O atalho pra ver o APK
real rodando.

```bash
tempest run
```

### `icon`

Gera `icon.png` (ícone do launcher) + `splash.png` (splash de boot) a partir de
uma imagem única (usa Pillow).

```bash
tempest icon logo.png
```

### `optimize`

Otimiza um **modelo ONNX** pro on-device: quantiza (INT8/fp16) e converte pro
formato ORT mobile, encolhendo o modelo que o app embarca. Roda no host, em tempo
de build (precisa do extra de visão).

```bash
tempest optimize model.onnx                 # INT8 + .ort (padrão)
tempest optimize model.onnx -q fp16         # fp16 em vez de int8
tempest optimize model.onnx --no-ort        # mantém .onnx, sem converter
```

- `--quantize` / `-q` — `int8` (padrão, ~4× menor), `fp16` ou `none`.
- `--no-ort` — pula a conversão pro formato mobile.
- `--out` — diretório de saída (padrão: ao lado do modelo).

---

## Diagnosticar e inspecionar

### `doctor`

Checa os **pré-requisitos de build/run Android** (JDK, android-host, SDK, adb,
dispositivo) e imprime um plano do que falta. A prontidão de build define o
código de saída; dispositivo ausente é só informativo (só `run`/`install` o
exigem).

```bash
tempest doctor
```

### `setup`

Configura o ambiente de build. Sem flag, diagnostica o que falta; com
`--install`, **instala o Android SDK + NDK** num diretório gerenciado (precisa de
um JDK).

```bash
tempest setup                       # diagnóstico + plano
tempest setup --install             # instala SDK + NDK
```

### `spec`

Imprime o **contrato tipado** do framework (widgets + eventos) como JSON — útil
pra ferramentas, geração de código e testes.

```bash
tempest spec > contract.json
```

### `clean`

Reseta os caches de build em `~/.tempestroid` (nativos extraídos do host, cópia
do host, clone do source). Resolve falhas por cache velho depois de um upgrade.

```bash
tempest clean                       # limpa caches
tempest clean --keystore            # também apaga a keystore de release
```

### `version`

Mostra a versão do framework (igual a `tempest --version`).

```bash
tempest version
```

---

## Qualidade

Wrappers finos sobre `ruff` / `pyright` / `pytest`, pra rodar o mesmo portão
localmente e na CI. Todos aceitam um caminho opcional (padrão: o projeto).

### `check`

**Portão completo**: `lint` + `fmt-check` + `type` + `test`, em sequência. Rode
antes de commitar.

```bash
tempest check
```

### `lint`

`ruff check` no alvo — só reporta, não altera.

```bash
tempest lint
```

### `fix`

Aplica **todos os autofixes do ruff + format** num passo.

```bash
tempest fix
tempest fix --unsafe        # inclui autofixes marcados como inseguros
```

### `format`

`ruff format` — escreve os arquivos.

```bash
tempest format
```

### `fmt-check`

`ruff format --check` — só leitura (falha se algo não está formatado).

```bash
tempest fmt-check
```

### `type`

`pyright` no alvo (type check estrito).

```bash
tempest type
```

### `test`

`pytest`, encaminhando o filtro de caminho opcional.

```bash
tempest test
tempest test tests/unit/test_state.py
```

### `uitest`

Roda um arquivo de **teste de UI nativa** estilo Playwright (driver F9): localiza
nós por key/texto/semântica, age com tap/fill e afirma com `expect_*`, com
auto-wait (sem sleeps fixos).

```bash
tempest uitest test_home.py                  # headless (in-process, sem renderer)
tempest uitest test_home.py -t emulator      # render Compose REAL num emulador
tempest uitest test_home.py -t emulator -j 4 # 4 instâncias isoladas em paralelo
```

- `--target` / `-t` — `headless` (agnóstico de renderer) ou `emulator` (render
  Compose real, tira screenshot por teste).
- `-j N` — sharding em N instâncias; `--isolate-adb` dá um servidor adb privado
  por agente.

O arquivo é um módulo de app (`view` + `make_state`) mais funções
`async def test_*(page)`.

## Cockpit do `tempest dev`

Comandos interativos enquanto o simulador roda:

| Tecla | Ação |
|---|---|
| `r` | Hot reload (estado preservado). |
| `R` | Hot restart (estado limpo). |
| `s` | Traz a janela à frente. |
| `q` | Encerra. |

Salvar o arquivo dispara o hot reload automaticamente; se a recarga for
incompatível com o estado vivo, o loop cai para um restart limpo. Uma gravação
ruim é capturada e impressa — o loop sobrevive.

!!! note "build / run precisam de JDK + Android SDK"
    `tempest build`/`run` rodam o Gradle reusando os nativos pré-compilados (o
    `android-host` vem no pacote), então precisam de **JDK + Android SDK** —
    **sem NDK, sem toolchain CPython, sem `git clone`** (exceto features opt-in
    via `--feature`, que exigem `--from-source` + NDK). Para rodar no aparelho
    **sem SDK**, use `tempest deploy`/`serve`. Veja
    [Build, deploy e publicação](build.md), a [instalação](../instalacao.md) e a
    [pesquisa de runtime](../research/android-runtime.md).

## Contrato do arquivo de app

Para `tempest dev`/`serve`, o módulo precisa expor:

- `make_state() -> S` — fábrica do estado inicial (chamada a cada hot restart).
- `view(app) -> Widget` — construtor da UI.

O carregador compila/executa o arquivo fresco a cada carga (sem reuso de `.pyc`),
então recargas sempre veem a última edição. Mantenha o módulo livre de imports de
Qt no nível de módulo (use `if __name__ == "__main__"`) para que o mesmo arquivo
rode no desktop e no dispositivo.
