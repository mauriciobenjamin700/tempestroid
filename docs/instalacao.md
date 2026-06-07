# Instalação

Há **dois públicos** para o tempestroid, e cada um instala de um jeito:

- **Você quer construir um app** com o framework → [Usuário final](#usuario-final).
- **Você quer contribuir** com o próprio framework (mexer no código deste
  repositório) → [Contribuidor](#contribuidor-este-repositorio).

Comece pela seção do seu caso — elas são independentes.

## Usuário final

Você só vai **usar** o framework para construir apps. Instale com `pip` (ou
`uv pip`). O **núcleo** depende apenas de `pydantic`:

```bash
pip install tempestroid
```

### Extras opcionais

Instale só o que o seu fluxo precisa:

```bash
pip install "tempestroid[qt]"      # simulador de desktop (PySide6 + qasync)
pip install "tempestroid[icons]"   # gerador de ícone/splash (tempest icon — Pillow)
```

| Extra | O que adiciona | Quando usar |
|---|---|---|
| (núcleo) | só `pydantic` | sempre — a árvore de widgets tipada |
| `qt` | `PySide6` + `qasync` | rodar/visualizar o app no **simulador de desktop** (`tempest dev`/`run`) |
| `icons` | `Pillow` | gerar `icon.png` + `splash.png` de uma imagem (`tempest icon`) |

!!! tip "Comece pelo simulador"
    Para experimentar sem nenhum aparelho Android, instale o extra `qt` e rode
    `tempest dev meuapp/app.py` — o app aparece numa janela de desktop com hot
    reload. Veja o [Começo rápido](inicio-rapido.md).

### Build para Android

Gerar o **APK** (`tempest build apk`) precisa apenas de um **JDK** e do
**Android SDK** — **não** precisa de NDK, nem do toolchain do CPython, nem de
clonar este repositório. O projeto `android-host` que gera o APK **já vem dentro
do pacote** instalado pelo `pip`.

```bash
pip install tempestroid          # já traz o android-host embarcado
tempest setup --install          # instala o Android SDK (se faltar)
tempest doctor                   # diagnostica o que falta (JDK, SDK, adb, device)
tempest new meuapp && cd meuapp
tempest build apk                # APK próprio (instala lado a lado com outros)
```

!!! info "JDK + SDK, e só"
    O APK reusa os binários nativos já compilados do host (CPython embutido), por
    isso dispensa NDK/toolchain. `tempest doctor` separa o que é necessário para
    **buildar** (JDK + SDK) do que é só para **rodar/instalar** (adb + aparelho).
    Detalhes em [Build, deploy e publicação](guia/build.md).

| Alvo | Precisa de |
|---|---|
| Simulador (desktop) | Python ≥ 3.11 + extra `qt` |
| Build do APK | JDK + Android SDK (`tempest setup --install`) — sem NDK/toolchain |
| Instalar/rodar no aparelho | o acima + `adb` + um device conectado |

## Contribuidor (este repositório)

Você vai mexer no **código do framework**. O fluxo usa
[uv](https://docs.astral.sh/uv/); um único comando instala tudo:

```bash
git clone https://github.com/mauriciobenjamin700/tempestroid
cd tempestroid
uv sync        # núcleo + ferramental de dev + simulador Qt + docs
```

Além das dependências de runtime, o `uv sync` instala:

- o grupo de dev (`ruff`, `pyright`, `pytest`, `pytest-asyncio`);
- o simulador Qt (`PySide6`, `qasync`) — faz parte do loop de dev/teste;
- o site de documentação (`mkdocs-material` + o plugin de idiomas).

### Portões de qualidade

Rode antes de cada commit (ou use o `Makefile`):

```bash
make gate        # ruff + pyright(strict) + pytest + mkdocs --strict + convenções
make quick       # versão rápida (sem pytest)
make docs-sync   # confere README/CLI/tabela de fases em sincronia
```

### Documentação

O site (este conteúdo) é construído com MkDocs Material, instalado pelo
`uv sync`:

```bash
uv run mkdocs serve              # servidor local com hot reload em http://127.0.0.1:8000
uv run mkdocs build --strict     # build de produção; falha em qualquer aviso
```

O cabeçalho tem um **seletor de idioma PT-BR / EN-US** (plugin
`mkdocs-static-i18n`).
